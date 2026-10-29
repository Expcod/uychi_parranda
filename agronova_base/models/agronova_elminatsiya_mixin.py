# -*- coding: utf-8 -*-
"""Ichki marja elminatsiyasi — umumiy tuzilma.

## Muammo

Loyihada **ikki qatlamli hisob** ishlaydi:

* **boshqaruv qatlami** — bo'lim mahsulotni keyingi bo'limga tasdiqlangan
  ichki narxda «sotadi», shu orqali uning haqiqiy natijasi ko'rinadi;
* **moliyaviy qatlam** — korxona uchun bu shunchaki mahsulotning bir
  bo'limdan ikkinchisiga o'tishi, hech qanday foyda hosil bo'lmagan.

Ona tovuq 1 200 so'mga tushgan tuxumni Inkubatsiyaga 1 500 so'mdan bersa,
Ona tovuqda 300 so'm ichki marja paydo bo'ladi. Ammo tuxum hali korxona
ichida — sotilmagan. Konsolidatsiyalangan hisobotga bu 300 so'm **foyda
sifatida kirmasligi kerak**, aks holda korxona o'ziga o'zi sotib foyda
«ishlab chiqargan» bo'lib chiqadi.

Marja **faqat mahsulot tashqariga sotilganda** haqiqiy bo'ladi.

## Yechim

Oy oxirida hujjat ochiladi. Davr ichidagi ichki sotuvlar yig'iladi, har
biri uchun **qabul qiluvchi bo'lim omborida qancha qolgani** ko'rsatiladi
va shu qoldiqqa to'g'ri keladigan marja teskari yoziladi.

## Nega partiyaga emas, alohida analitik hisobga

Teskari qator partiyaning analitik hisobiga yozilsa, bo'limning o'z
hisobotidan ichki foyda yo'qolib ketadi — ikki qatlamli hisobning maqsadi
buziladi. Shuning uchun elminatsiya **«Konsolidatsiya» rejasidagi alohida
analitik hisobga** tushadi:

* bo'lim hisoboti (partiya rejasi) — ichki marja **bor**;
* konsolidatsiyalangan hisobot (barcha rejalar) — marja **o'zaro yo'qoladi**.

## Nega buxgalteriya provodkasi yozilmaydi

Ichki sotuvning o'zi `account.move` yaratmaydi — u faqat boshqaruv hisobi
qatori. Demak moliyaviy defterda yo'q qilinadigan foyda ham yo'q.

## Meros oluvchi model nima beradi

* `qator_ids` — o'z qator modeliga One2many;
* `_elm_ichki_sotuv_model()`, `_elm_sequence()`, `_elm_hisob_nomi()`;
* qator modelida `ichki_sotuv_id` va undan keladigan related maydonlar
  (`date`, `miqdor`, `summa`, `ichki_marja`).
"""
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class AgroNovaElminatsiyaMixin(models.AbstractModel):
    _name = 'agronova.elminatsiya.mixin'
    _description = "AgroNova — ichki marja elminatsiyasi"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'davr_boshi desc, id desc'

    name = fields.Char(
        "Hujjat", default=lambda self: _("Yangi"), copy=False, readonly=True,
        index=True)
    davr_boshi = fields.Date(
        "Davr boshi", required=True, tracking=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1))
    davr_oxiri = fields.Date(
        "Davr oxiri", required=True, tracking=True,
        default=lambda self: (
            fields.Date.context_today(self).replace(day=1)
            + relativedelta(months=1, days=-1)))
    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)

    jami_ichki_sotuv = fields.Monetary(
        "Ichki sotuv summasi", compute='_compute_jami', store=True)
    jami_marja = fields.Monetary(
        "Davrdagi ichki marja", compute='_compute_jami', store=True,
        help="Davr ichida shakllangan butun ichki marja.")
    jami_elminatsiya = fields.Monetary(
        "Elminatsiya qilinadi", compute='_compute_jami', store=True,
        help="Shundan realizatsiya qilinmagani — konsolidatsiyada teskari "
             "yoziladigan qism.")
    realizatsiya_marja = fields.Monetary(
        "Realizatsiya qilingan marja", compute='_compute_jami', store=True,
        help="Qabul qiluvchi bo'lim tashqariga sotib ulgurgan qismi — bu "
             "haqiqiy foyda, teskari yozilmaydi.")

    holat = fields.Selection(
        [('draft', "Qoralama"), ('posted', "Tasdiqlangan"),
         ('storno', "Storno")],
        string="Holati", default='draft', required=True, tracking=True,
        copy=False)
    analytic_account_id = fields.Many2one(
        'account.analytic.account', string="Elminatsiya hisobi", readonly=True,
        copy=False, help="Teskari qatorlar shu analitik hisobga tushadi.")
    analytic_line_ids = fields.Many2many(
        'account.analytic.line', string="Analitik qatorlar", copy=False,
        readonly=True)
    izoh = fields.Text("Izoh")

    _davr_togri = models.Constraint(
        'CHECK (davr_oxiri >= davr_boshi)',
        "Davr oxiri boshidan oldin bo'lishi mumkin emas.")

    # ------------------------------------------------------------- ilgaklar
    def _elm_ichki_sotuv_model(self):
        """Qaysi modeldagi ichki sotuvlar yig'iladi."""
        raise NotImplementedError

    def _elm_sequence(self):
        """Hujjat raqami uchun ketma-ketlik kodi."""
        raise NotImplementedError

    def _elm_hisob_nomi(self):
        """Konsolidatsiya rejasidagi analitik hisob nomi."""
        return _("Elminatsiya")

    def _elm_plan_xmlid(self):
        """«Konsolidatsiya» rejasining xmlid'i, bo'lsa."""
        return None

    def _elm_qator_matni(self, q):
        """Analitik qator nomi. Model turini ham qo'shishi mumkin."""
        return _("Elminatsiya: %(hujjat)s (%(miqdor)s / %(jami)s)",
                 hujjat=q.ichki_sotuv_id.name, miqdor=q.qolgan_miqdor,
                 jami=q.miqdor)

    # --------------------------------------------------------------- compute
    @api.depends('qator_ids.summa', 'qator_ids.ichki_marja',
                 'qator_ids.elminatsiya_summa')
    def _compute_jami(self):
        for rec in self:
            rec.jami_ichki_sotuv = sum(rec.qator_ids.mapped('summa'))
            rec.jami_marja = sum(rec.qator_ids.mapped('ichki_marja'))
            rec.jami_elminatsiya = sum(
                rec.qator_ids.mapped('elminatsiya_summa'))
            rec.realizatsiya_marja = rec.jami_marja - rec.jami_elminatsiya

    @api.model_create_multi
    def create(self, vals_list):
        kod = self._elm_sequence()
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _("Yangi"):
                vals['name'] = (self.env['ir.sequence'].next_by_code(kod)
                                or _("Yangi"))
        return super().create(vals_list)

    def write(self, vals):
        if not set(vals) <= {'holat', 'analytic_line_ids',
                             'analytic_account_id', 'izoh', 'message_ids',
                             'message_follower_ids', 'activity_ids'}:
            for rec in self:
                if rec.holat != 'draft':
                    raise UserError(_(
                        "«%s» elminatsiyasi tasdiqlangan — tahrirlanmaydi. "
                        "Avval storno qiling.", rec.display_name))
        return super().write(vals)

    # ------------------------------------------------------- analitik hisob
    def _elminatsiya_hisobi(self):
        """Korxonaning yagona elminatsiya analitik hisobi.

        Har hujjatga alohida hisob ochilmaydi — konsolidatsiyalangan
        hisobotda hammasi bitta satrda ko'rinsin.
        """
        self.ensure_one()
        Analytic = self.env['account.analytic.account'].sudo()
        plan = self.env['agronova.analitik.mixin']._agronova_get_plan(
            xmlid=self._elm_plan_xmlid(), name="Konsolidatsiya")
        if not plan:
            raise UserError(_("«Konsolidatsiya» analitik rejasi topilmadi."))
        nom = self._elm_hisob_nomi()
        hisob = Analytic.search([
            ('plan_id', '=', plan.id),
            ('name', '=', nom),
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        if not hisob:
            hisob = Analytic.create({
                'name': nom,
                'plan_id': plan.id,
                'company_id': self.company_id.id,
            })
        return hisob

    # ------------------------------------------------------------- yig'ish
    def _ichki_sotuvlar(self):
        """Davrdagi, hali elminatsiya qilinmagan ichki sotuvlar."""
        self.ensure_one()
        Qator = self.env[self.qator_ids._name].sudo()
        band = Qator.search([
            ('elminatsiya_id.holat', '!=', 'storno'),
            ('elminatsiya_id', '!=', self.id),
        ]).mapped('ichki_sotuv_id')
        return self.env[self._elm_ichki_sotuv_model()].search([
            ('holat', '=', 'done'),
            ('company_id', '=', self.company_id.id),
            ('date', '>=', self.davr_boshi),
            ('date', '<=', self.davr_oxiri),
            ('id', 'not in', band.ids),
        ], order='date')

    def action_yigish(self):
        """Davrdagi ichki sotuvlarni qatorlarga yig'adi."""
        for rec in self:
            if rec.holat != 'draft':
                raise UserError(_(
                    "«%s» tasdiqlangan — qayta yig'ib bo'lmaydi.",
                    rec.display_name))
            sotuvlar = rec._ichki_sotuvlar()
            if not sotuvlar:
                raise UserError(_(
                    "%(dan)s — %(gacha)s oralig'ida elminatsiya qilinmagan "
                    "ichki sotuv topilmadi.",
                    dan=rec.davr_boshi, gacha=rec.davr_oxiri))
            rec.qator_ids.unlink()
            rec.qator_ids = [
                (0, 0, {
                    'ichki_sotuv_id': s.id,
                    # Konservativ boshlang'ich holat: realizatsiya
                    # isbotlanmaguncha butun miqdor qabul qiluvchi bo'lim
                    # omborida turibdi deb hisoblanadi. Hisobchi qancha
                    # sotilganini bilsa — qoldiqni kamaytiradi.
                    'qolgan_miqdor': s.dona,
                })
                for s in sotuvlar
            ]
        return True

    # --------------------------------------------------------------- holat
    def action_tasdiqlash(self):
        for rec in self:
            if rec.holat != 'draft':
                raise UserError(_("«%s» allaqachon tasdiqlangan.",
                                  rec.display_name))
            if not rec.qator_ids:
                raise UserError(_(
                    "«%s» hujjatida qator yo'q — avval «Yig'ish» tugmasini "
                    "bosing.", rec.display_name))
            hisob = rec._elminatsiya_hisobi()
            plan_ustuni = hisob.plan_id._column_name()
            Line = rec.env['account.analytic.line'].sudo()
            lines = Line
            for q in rec.qator_ids:
                if rec.currency_id.is_zero(q.elminatsiya_summa):
                    continue
                lines |= Line.create({
                    'name': rec._elm_qator_matni(q),
                    'date': rec.davr_oxiri,
                    # Realizatsiya qilinmagan foyda teskari yoziladi.
                    'amount': -q.elminatsiya_summa,
                    'company_id': rec.company_id.id,
                    # Bu tannarx emas — birlik tannarxini oshirmasligi kerak.
                    'agronova_tannarx_bazasi': False,
                    plan_ustuni: hisob.id,
                })
            rec.write({
                'analytic_account_id': hisob.id,
                'analytic_line_ids': [(6, 0, lines.ids)],
                'holat': 'posted',
            })
            rec.message_post(body=_(
                "Elminatsiya tasdiqlandi: %(summa)s so'm realizatsiya "
                "qilinmagan ichki marja konsolidatsiyadan chiqarildi.",
                summa=rec.jami_elminatsiya))
        return True

    def action_storno(self):
        """Teskari qator yozadi — yozuvlar o'chirilmaydi (TZ talabi)."""
        for rec in self:
            if rec.holat != 'posted':
                raise UserError(_(
                    "Faqat tasdiqlangan elminatsiya storno qilinadi."))
            bugun = fields.Date.context_today(rec)
            for line in rec.analytic_line_ids:
                line.sudo().copy({
                    'name': _("STORNO: %s", line.name),
                    'amount': -line.amount,
                    'date': bugun,
                })
            rec.holat = 'storno'
        return True

    def action_qoralamaga(self):
        for rec in self:
            if rec.holat != 'storno':
                raise UserError(_(
                    "Qoralamaga faqat storno qilingan hujjat qaytariladi."))
            rec.holat = 'draft'
        return True

    def action_open_analytic(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("«%s» analitik qatorlari", self.name),
            'res_model': 'account.analytic.line',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.analytic_line_ids.ids)],
        }


class AgroNovaElminatsiyaQatorMixin(models.AbstractModel):
    """Bitta ichki sotuv bo'yicha realizatsiya qilinmagan marja.

    Meros oluvchi model `elminatsiya_id`, `ichki_sotuv_id`, `currency_id`
    va ichki sotuvdan keladigan `miqdor`, `summa`, `ichki_marja`
    maydonlarini e'lon qiladi.
    """
    _name = 'agronova.elminatsiya.qator.mixin'
    _description = "AgroNova — elminatsiya qatori"
    _order = 'date, id'

    # Abstrakt modelda ham valyuta maydoni bo'lishi shart, aks holda
    # Monetary maydonni sozlab bo'lmaydi. Konkret model uni hujjatga
    # bog'langan `related` bilan qayta e'lon qiladi.
    currency_id = fields.Many2one('res.currency', string="Valyuta")

    qolgan_miqdor = fields.Integer(
        "Qabul qiluvchida qolgan", required=True,
        help="Berilgan miqdordan qanchasi qabul qiluvchi bo'lim omborida "
             "hali turibdi (tashqariga sotilmagan). Shu qismga to'g'ri "
             "keladigan marja realizatsiya qilinmagan hisoblanadi.\n"
             "Boshlang'ich qiymat — butun miqdor: realizatsiya "
             "isbotlanmaguncha foyda haqiqiy emas.")
    sotilgan_miqdor = fields.Integer(
        "Realizatsiya qilingan", compute='_compute_elminatsiya', store=True)
    realizatsiya_foiz = fields.Float(
        "Realizatsiya (%)", compute='_compute_elminatsiya', store=True)
    elminatsiya_summa = fields.Monetary(
        "Elminatsiya summasi", compute='_compute_elminatsiya', store=True,
        help="Ichki marja × qolgan miqdor / berilgan miqdor.")
    izoh = fields.Char("Izoh")

    _qolgan_manfiy_emas = models.Constraint(
        'CHECK (qolgan_miqdor >= 0)',
        "Qolgan miqdor manfiy bo'lishi mumkin emas.")

    @api.depends('miqdor', 'qolgan_miqdor', 'ichki_marja')
    def _compute_elminatsiya(self):
        for q in self:
            q.sotilgan_miqdor = max(q.miqdor - q.qolgan_miqdor, 0)
            q.realizatsiya_foiz = (
                q.sotilgan_miqdor / q.miqdor * 100.0 if q.miqdor else 0.0)
            # Marja manfiy bo'lsa (ichki narx tannarxdan past) ham shu
            # nisbatda teskari yoziladi — realizatsiya qilinmagan zarar ham
            # konsolidatsiyaga kirmasligi kerak.
            q.elminatsiya_summa = (
                q.ichki_marja * q.qolgan_miqdor / q.miqdor
                if q.miqdor else 0.0)

    @api.constrains('qolgan_miqdor', 'miqdor')
    def _tekshir_qolgan(self):
        for q in self:
            if q.qolgan_miqdor > q.miqdor:
                raise ValidationError(_(
                    "«%(hujjat)s»: qolgan miqdor (%(qolgan)s) berilgan "
                    "miqdordan (%(miqdor)s) ko'p bo'lishi mumkin emas.",
                    hujjat=q.ichki_sotuv_id.name or '',
                    qolgan=q.qolgan_miqdor, miqdor=q.miqdor))

    @api.constrains('ichki_sotuv_id')
    def _tekshir_takror(self):
        for q in self:
            takror = self.sudo().search([
                ('ichki_sotuv_id', '=', q.ichki_sotuv_id.id),
                ('elminatsiya_id.holat', '!=', 'storno'),
                ('id', '!=', q.id),
            ], limit=1)
            if takror:
                raise ValidationError(_(
                    "«%(hujjat)s» ichki sotuvi «%(elm)s» hujjatida "
                    "allaqachon elminatsiya qilingan.",
                    hujjat=q.ichki_sotuv_id.name or '',
                    elm=takror.elminatsiya_id.display_name))
