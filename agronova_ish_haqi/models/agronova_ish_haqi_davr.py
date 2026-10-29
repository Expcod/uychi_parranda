# -*- coding: utf-8 -*-
"""Oylik ish haqi hisoblash hujjati (TZ M09).

## Nima uchun `hr_payroll` emas

Odooning payroll moduli mamlakat lokalizatsiyasi bilan keladi — unda
soliqlar, ushlanmalar va hisoblash qoidalari tayyor bo'ladi. O'zbekiston
uchun bunday lokalizatsiya **mavjud emas**, ya'ni barcha qoidani baribir
o'zimiz yozishimiz kerak edi. Odooning qoida dvigateli esa Python
parchalari bilan ishlaydi: brigadir ham, ishchi ham uni o'qiy olmaydi.

TZ M09 talab qiladigan hisob esa sodda va aniq: uch xil tarif, ishlagan
kun yoki soat, avans, jarima, bonus va xodim bilan qolgan hisob-kitob.
Shuning uchun to'g'ridan-to'g'ri shu model yozildi.

`hr_payroll` o'chirilmagan — shunchaki ishlatilmaydi.

## Oqim

    Tarif (xodim kartochkasida)
        + davomat yoki qo'lda kiritilgan kun/soat
        = hisoblangan
        − avans − jarima + bonus
        = qo'lga tegadigan summa

Tasdiqlanganda ikki narsa yoziladi:

* **xodim balansiga** harakat qatorlari (`agronova.ish_haqi.harakat`);
* **buxgalteriya provodkasi**: Dt ish haqi xarajati / Kt xodimga qarz.

Avans va jarima hozircha provodkaga kirmaydi — ular pul harakati bilan
bog'lanmagan (kassa moduli hali qurilmagan), faqat xodim balansida
qayd etiladi. Kassa tayyor bo'lgach shu yerga ulanadi.

## Tannarxga taqsimlash bu yerda emas

Ish haqini sex va partiyalarga bo'lish alohida hujjatning ishi
(`agronova.ona_tovuq.ish_haqi` va boshqa bo'lim modullari). U summani shu
yerdan oladi. Agar bu hujjat ham analitik qator yozsa, xarajat ikki
marta sanalgan bo'lardi.
"""
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .agronova_ish_haqi_tarif import TUR as TARIF_TUR

MANBA = [
    ('davomat', "Davomatdan"),
    ('qolda', "Qo'lda kiritilgan"),
]


class AgroNovaIshHaqiDavr(models.Model):
    _name = 'agronova.ish_haqi.davr'
    _description = "Ish haqi — oylik hisoblash"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'davr_boshi desc, id desc'

    name = fields.Char("Hujjat", default=lambda s: _("Yangi"), copy=False,
                       readonly=True, index=True)
    davr_boshi = fields.Date(
        "Davr boshi", required=True, tracking=True,
        default=lambda s: fields.Date.context_today(s).replace(day=1))
    davr_oxiri = fields.Date(
        "Davr oxiri", required=True, tracking=True,
        default=lambda s: (fields.Date.context_today(s).replace(day=1)
                           + relativedelta(months=1, days=-1)))
    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True,
        default=lambda s: s.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)
    department_ids = fields.Many2many(
        'hr.department', string="Bo'limlar",
        help="Bo'sh bo'lsa — korxonaning barcha xodimlari.")

    qator_ids = fields.One2many(
        'agronova.ish_haqi.davr.qator', 'davr_id', string="Qatorlar", copy=False)
    xodim_soni = fields.Integer("Xodimlar", compute='_compute_jami', store=True)
    jami_hisoblangan = fields.Monetary("Hisoblangan", compute='_compute_jami',
                                       store=True)
    jami_bonus = fields.Monetary("Bonus", compute='_compute_jami', store=True)
    jami_avans = fields.Monetary("Avans", compute='_compute_jami', store=True)
    jami_jarima = fields.Monetary("Jarima", compute='_compute_jami', store=True)
    jami_qolga = fields.Monetary("Qo'lga tegadi", compute='_compute_jami',
                                 store=True)

    holat = fields.Selection(
        [('draft', "Qoralama"), ('posted', "Tasdiqlangan"),
         ('storno', "Storno")],
        string="Holati", default='draft', required=True, tracking=True,
        copy=False)
    move_id = fields.Many2one('account.move', string="Provodka", readonly=True,
                              copy=False)
    harakat_ids = fields.One2many(
        'agronova.ish_haqi.harakat', 'davr_id', string="Balans harakatlari",
        readonly=True)
    izoh = fields.Text("Izoh")

    _davr_togri = models.Constraint(
        'CHECK (davr_oxiri >= davr_boshi)',
        "Davr oxiri boshidan oldin bo'lishi mumkin emas.")

    # --------------------------------------------------------------- compute
    @api.depends('qator_ids.hisoblangan', 'qator_ids.bonus',
                 'qator_ids.avans', 'qator_ids.jarima', 'qator_ids.qolga')
    def _compute_jami(self):
        for d in self:
            q = d.qator_ids
            d.xodim_soni = len(q)
            d.jami_hisoblangan = sum(q.mapped('hisoblangan'))
            d.jami_bonus = sum(q.mapped('bonus'))
            d.jami_avans = sum(q.mapped('avans'))
            d.jami_jarima = sum(q.mapped('jarima'))
            d.jami_qolga = sum(q.mapped('qolga'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _("Yangi"):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'agronova.ish_haqi.davr') or _("Yangi")
        return super().create(vals_list)

    def write(self, vals):
        if not set(vals) <= {'holat', 'move_id', 'izoh', 'message_ids',
                             'message_follower_ids', 'activity_ids'}:
            for d in self:
                if d.holat != 'draft':
                    raise UserError(_(
                        "«%s» tasdiqlangan — tahrirlanmaydi. Avval storno "
                        "qiling.", d.display_name))
        return super().write(vals)

    # ------------------------------------------------------------- yig'ish
    def _xodimlar(self):
        self.ensure_one()
        domain = [('company_id', '=', self.company_id.id)]
        if self.department_ids:
            domain.append(('department_id', 'in', self.department_ids.ids))
        return self.env['hr.employee'].sudo().search(domain)

    def _davr_kunlari(self):
        self.ensure_one()
        return (self.davr_oxiri - self.davr_boshi).days + 1

    def _davomat(self, employee):
        """Davrdagi ishlagan kun va soat. Davomat yo'q bo'lsa `(0, 0)`."""
        self.ensure_one()
        Att = self.env.get('hr.attendance')
        if Att is None:
            return 0, 0.0
        yozuvlar = Att.sudo().search([
            ('employee_id', '=', employee.id),
            ('check_in', '>=', fields.Datetime.to_datetime(self.davr_boshi)),
            ('check_in', '<=', fields.Datetime.to_datetime(
                self.davr_oxiri).replace(hour=23, minute=59, second=59)),
        ])
        kunlar = {y.check_in.date() for y in yozuvlar if y.check_in}
        return len(kunlar), sum(yozuvlar.mapped('worked_hours'))

    def action_yigish(self):
        """Xodimlarni yig'adi va tarif bo'yicha hisoblaydi."""
        for d in self:
            if d.holat != 'draft':
                raise UserError(_("Faqat qoralama hujjat qayta yig'iladi."))
            d.qator_ids.unlink()
            Tarif = d.env['agronova.ish_haqi.tarif']
            vals = []
            tarifsiz = d.env['hr.employee']
            for emp in d._xodimlar():
                tarif = Tarif.amaldagi(emp, d.davr_oxiri)
                if not tarif:
                    tarifsiz |= emp
                    continue
                kun, soat = d._davomat(emp)
                manba = 'davomat' if (kun or soat) else 'qolda'
                if manba == 'qolda':
                    # Davomat tizimi hali ma'lumot bermayapti — norma
                    # bo'yicha to'ldiriladi, hisobchi kerak bo'lsa tuzatadi.
                    kun = tarif.norma_kun
                    soat = 0.0
                vals.append({
                    'employee_id': emp.id,
                    'tarif_id': tarif.id,
                    'manba': manba,
                    'ishlagan_kun': kun,
                    'ishlagan_soat': soat,
                })
            if not vals:
                raise UserError(_(
                    "Bu korxonada tarifi belgilangan xodim topilmadi. "
                    "Avval xodim kartochkasida tarif oching."))
            d.qator_ids = [(0, 0, v) for v in vals]
            if tarifsiz:
                d.message_post(body=_(
                    "Tarifi yo'qligi uchun hisoblanmagan xodimlar (%(son)s): "
                    "%(nomlar)s",
                    son=len(tarifsiz),
                    nomlar=", ".join(tarifsiz.mapped('name'))))
        return True

    # ------------------------------------------------------------ tasdiqlash
    def _buxgalteriya_company(self):
        """Provodka yoziladigan korxona — bosh korxona.

        Ish haqi hujjati bo'lim korxonasida (Yem zavodi, Ona tovuq...)
        ochiladi, chunki xodimlar o'sha yerda. Buxgalteriya esa bitta —
        to'liq hisoblar rejasi (shu jumladan 6710) va ish haqi jurnali
        faqat bosh korxonada turadi. Shuning uchun provodka doim bosh
        korxonaga yoziladi; bo'lim provodka izohida ko'rinadi.
        """
        self.ensure_one()
        company = self.company_id
        while company.parent_id:
            company = company.parent_id
        return company

    def _hisob_raqamlari(self):
        """(xarajat hisobi, xodimga qarz hisobi, jurnal)."""
        self.ensure_one()
        bux = self._buxgalteriya_company()
        ICP = self.env['ir.config_parameter'].sudo()
        Account = self.env['account.account'].sudo()
        Journal = self.env['account.journal'].sudo()

        def olish(param, model, qidiruv):
            rid = ICP.get_param(param)
            if rid:
                rec = model.browse(int(rid))
                if rec.exists():
                    return rec
            # Odoo 19 da `account.account` ko'p korxonaga tegishli bo'lishi
            # mumkin — unda `company_ids`, jurnalda esa oddiy `company_id`.
            maydon = ('company_ids', 'in') if 'company_ids' in model._fields                 else ('company_id', '=')
            return model.search(
                qidiruv + [(maydon[0], maydon[1], bux.id)], limit=1)

        xarajat = olish('agronova_ish_haqi.account_xarajat', Account,
                        [('account_type', '=', 'expense')])
        qarz = olish('agronova_ish_haqi.account_qarz', Account,
                     [('account_type', '=', 'liability_payable')])
        jurnal = olish('agronova_ish_haqi.journal', Journal,
                       [('type', '=', 'general')])
        yoq = [nom for nom, rec in [("ish haqi xarajati hisobi", xarajat),
                                    ("xodimga qarz hisobi", qarz),
                                    ("jurnal", jurnal)] if not rec]
        if yoq:
            raise UserError(_(
                "Provodka yozish uchun sozlama yetishmayapti: %s. "
                "Sozlamalar → Ish haqi bo'limida ko'rsating.",
                ", ".join(yoq)))
        return xarajat, qarz, jurnal

    def _move_vals(self):
        """Dt ish haqi xarajati / Kt xodimga qarz.

        Avans va jarima bu yerga kirmaydi — ular pul harakati bilan
        bog'lanmagan, faqat xodim balansida turadi.
        """
        self.ensure_one()
        xarajat, qarz, jurnal = self._hisob_raqamlari()
        lines = []
        for q in self.qator_ids:
            summa = q.hisoblangan + q.bonus
            if self.currency_id.is_zero(summa):
                continue
            nom = _("Ish haqi %(davr)s: %(xodim)s",
                    davr=self.davr_boshi.strftime('%m.%Y'),
                    xodim=q.employee_id.name)
            lines.append((0, 0, {
                'name': nom, 'account_id': xarajat.id, 'debit': summa,
                'credit': 0.0}))
            lines.append((0, 0, {
                'name': nom, 'account_id': qarz.id, 'debit': 0.0,
                'credit': summa,
                'partner_id': q.employee_id.work_contact_id.id or False}))
        if not lines:
            raise UserError(_("Hisoblangan summa nol — provodka yozilmaydi."))
        return {
            'journal_id': jurnal.id,
            'date': self.davr_oxiri,
            'ref': _("Ish haqi: %(hujjat)s — %(bolim)s",
                     hujjat=self.name, bolim=self.company_id.name),
            'company_id': self._buxgalteriya_company().id,
            'line_ids': lines,
        }

    def action_tasdiqlash(self):
        for d in self:
            if d.holat != 'draft':
                raise UserError(_("«%s» allaqachon tasdiqlangan.",
                                  d.display_name))
            if not d.qator_ids:
                raise UserError(_(
                    "Qator yo'q — avval «Yig'ish» tugmasini bosing."))
            d._balans_yozish()
            # Provodka bosh korxonada yoziladi (`_buxgalteriya_company`),
            # shuning uchun yozuv ham o'sha korxona kontekstida
            # yaratiladi — aks holda jurnal "ruxsat etilgan korxonalarda
            # emas" deb rad etiladi.
            move = d.env['account.move'].sudo().with_company(
                d._buxgalteriya_company()).create(d._move_vals())
            move.action_post()
            d.write({'move_id': move.id, 'holat': 'posted'})
            d.message_post(body=_(
                "Ish haqi hisoblandi: %(son)s xodim, %(summa)s so'm.",
                son=d.xodim_soni, summa=d.jami_hisoblangan + d.jami_bonus))
        return True

    def _balans_yozish(self):
        """Xodim balansiga harakat qatorlarini yozadi."""
        self.ensure_one()
        Harakat = self.env['agronova.ish_haqi.harakat'].sudo()
        vals = []
        for q in self.qator_ids:
            for tur, summa in [('hisoblandi', q.hisoblangan),
                               ('bonus', q.bonus),
                               ('avans', q.avans),
                               ('jarima', q.jarima)]:
                if self.currency_id.is_zero(summa):
                    continue
                vals.append({
                    'employee_id': q.employee_id.id,
                    'sana': self.davr_oxiri,
                    'tur': tur,
                    'summa': summa,
                    'davr_id': self.id,
                    'izoh': self.name,
                })
        if vals:
            Harakat.with_context(agronova_ish_haqi_post=True).create(vals)

    def action_storno(self):
        for d in self:
            if d.holat != 'posted':
                raise UserError(_("Faqat tasdiqlangan hujjat storno qilinadi."))
            if d.move_id:
                teskari = d.move_id.sudo()._reverse_moves(
                    [{'date': fields.Date.context_today(d),
                      'ref': _("STORNO: %s", d.name)}], cancel=True)
                # `cancel=True` teskari provodkani o'zi o'tkazadi va
                # asl yozuvni yopadi — qayta o'tkazishga urinsak xato beradi.
                if teskari.state == 'draft':
                    teskari.action_post()
            d.harakat_ids.with_context(agronova_ish_haqi_post=True).unlink()
            d.holat = 'storno'
            d.message_post(body=_("Hujjat storno qilindi."))
        return True

    def action_qoralamaga(self):
        for d in self:
            if d.holat != 'storno':
                raise UserError(_(
                    "Qoralamaga faqat storno qilingan hujjat qaytariladi."))
            d.write({'holat': 'draft', 'move_id': False})
        return True

    def action_open_move(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.move_id.id,
            'view_mode': 'form',
        }


class AgroNovaIshHaqiDavrQator(models.Model):
    """Bitta xodimning bir oylik hisob-kitobi."""
    _name = 'agronova.ish_haqi.davr.qator'
    _description = "Ish haqi — hisoblash qatori"
    _order = 'employee_id'

    davr_id = fields.Many2one('agronova.ish_haqi.davr', string="Hujjat",
                              required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='davr_id.company_id', store=True,
                                 readonly=True)
    currency_id = fields.Many2one(related='davr_id.currency_id', readonly=True)
    employee_id = fields.Many2one('hr.employee', string="Xodim", required=True,
                                  ondelete='restrict', index=True)
    department_id = fields.Many2one(related='employee_id.department_id',
                                    string="Bo'lim", store=True, readonly=True)
    tarif_id = fields.Many2one('agronova.ish_haqi.tarif', string="Tarif",
                               required=True, ondelete='restrict')
    tur = fields.Selection(TARIF_TUR, related='tarif_id.tur', string="Tarif turi",
                           store=True, readonly=True)
    stavka = fields.Monetary(related='tarif_id.stavka', string="Stavka",
                             store=True, readonly=True)
    manba = fields.Selection(MANBA, string="Kun manbai", required=True,
                             default='qolda')
    norma_kun = fields.Float("Norma (kun)", compute='_compute_hisoblangan',
                             store=True)
    ishlagan_kun = fields.Float("Ishlagan kun")
    ishlagan_soat = fields.Float("Ishlagan soat")
    hisoblangan = fields.Monetary("Hisoblangan", compute='_compute_hisoblangan',
                                  store=True)
    avans = fields.Monetary("Avans")
    jarima = fields.Monetary("Jarima")
    bonus = fields.Monetary("Bonus")
    qolga = fields.Monetary("Qo'lga tegadi", compute='_compute_hisoblangan',
                            store=True)
    izoh = fields.Char("Izoh")

    @api.depends('tarif_id', 'ishlagan_kun', 'ishlagan_soat',
                 'avans', 'jarima', 'bonus')
    def _compute_hisoblangan(self):
        for q in self:
            tarif = q.tarif_id
            norma = tarif.norma_kun if tarif else 0.0
            q.norma_kun = norma
            if not tarif:
                q.hisoblangan = 0.0
            elif tarif.tur == 'soatlik':
                q.hisoblangan = tarif.stavka * q.ishlagan_soat
            else:
                # Oklad va kunbay bir xil formulada — farqi normada
                kunlik = tarif.stavka / norma if norma else 0.0
                q.hisoblangan = kunlik * q.ishlagan_kun
            q.qolga = q.hisoblangan + q.bonus - q.avans - q.jarima
