# -*- coding: utf-8 -*-
"""KPI va ball tizimi (TZ 13-bo'lim).

Bu — noldan yoziladigan beshta joydan biri (TZ 15-bo'lim).

Beshta majburiy talab kodda shunday qoplangan:

1. **Nizo mexanizmi** — `agronova.kpi.etiroz`: xodim ballga sabab yozib
   e'tiroz bildiradi, rahbar ko'rib chiqadi, qondirsa ball qayta yoziladi.
2. **Jonli ko'rinish** — ball hodisa sodir bo'lgan zahoti yoziladi, xodim
   uni «Mening KPI'im» menyusida har kuni ko'rib turadi.
3. **Oy yopilgach qulf** — `agronova.kpi.davr` yopilgach ballar `qulflangan`
   bo'ladi va o'zgartirilmaydi.
4. **Ochiq formula** — har bir mezonning ball formulasi shu faylda
   yozilgan va hujjatning `formula_izohi` maydonida xodimga ko'rinadi.
5. **Ish vaqti chegarasi** — tezlik mezonlari `agronova.muddat.mixin` orqali
   faqat ish soatlarini sanaydi.

KPI **faqat bonusga** ta'sir qiladi, belgilangan ish haqiga tegmaydi —
shuning uchun bu modelning `hr.payslip` bilan hech qanday bog'lanishi yo'q
va ataylab qo'shilmaydi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

MEZON = [
    # zakupchik mezonlari
    ('javob_tezligi', "Javob tezligi"),
    ('muddat', "Muddat (vaqtida keldimi)"),
    ('toliqlik', "To'liqlik (miqdor)"),
    ('sifat', "Sifat"),
    ('narx_tejami', "Narx tejami"),
    # tasdiqlovchi mezonlari
    ('tasdiqlash_tezligi', "Tasdiqlash tezligi"),
    ('javobsiz_sorovlar', "Javobsiz qolgan so'rovlar"),
]

# Ochiq formula (TZ 13.4). Har mezon 0..10 ball beradi.
FORMULA_IZOHI = {
    'javob_tezligi':
        "Muddat ichida javob berilsa 10 ball. Har kechikkan ish soati "
        "uchun 2 ball ayiriladi, 0 dan pastga tushmaydi.",
    'tasdiqlash_tezligi':
        "Muddat ichida tasdiqlansa 10 ball. Har kechikkan ish soati uchun "
        "2 ball ayiriladi.",
    'muddat': "Omborchi qo'ygan muddat bahosi (0..10) to'g'ridan-to'g'ri ball.",
    'toliqlik': "Omborchi qo'ygan to'liqlik bahosi (0..10) ball bo'ladi. "
                "Masalan 10 ta so'ralib 9 tasi kelsa — 9 ball.",
    'sifat': "Omborchi qo'ygan sifat bahosi (0..10) ball bo'ladi.",
    'narx_tejami':
        "Norma narxdan har 1% tejam +1 ball, har 1% ortiqcha to'lov "
        "-1 ball. Boshlang'ich 5 ball, oralig'i 0..10.",
    'javobsiz_sorovlar':
        "So'rov javobsiz qolib eskalatsiya qilinsa 0 ball yoziladi.",
}
KECHIKISH_JARIMASI = 2.0   # 1 ish soati kechikish uchun necha ball


class AgroNovaKpiDavr(models.Model):
    _name = 'agronova.kpi.davr'
    _description = "KPI davri"
    _inherit = ['mail.thread']
    _order = 'boshlanish desc'

    name = fields.Char("Davr", required=True, tracking=True)
    boshlanish = fields.Date("Boshlanish", required=True)
    tugash = fields.Date("Tugash", required=True)
    holat = fields.Selection(
        [('ochiq', "Ochiq"), ('yopilgan', "Yopilgan")],
        string="Holati", default='ochiq', required=True, tracking=True)
    ball_narxi = fields.Monetary(
        "1 ball bahosi (so'm)", currency_field='currency_id',
        help="Bonus = (o'rtacha ball) x (1 ball bahosi). "
             "TODO: buyurtmachi tasdiqlashi kerak (TZ 20.7).")
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id)
    kpi_ids = fields.One2many('agronova.kpi', 'davr_id', string="Ballar")

    _davr_uniq = models.Constraint(
        'UNIQUE(name)', "Bunday nomli KPI davri allaqachon bor.")

    @api.constrains('boshlanish', 'tugash')
    def _check_oraliq(self):
        for rec in self:
            if rec.tugash < rec.boshlanish:
                raise ValidationError(_("Davr tugashi boshlanishidan oldin."))

    def action_yopish(self):
        """Bonus hisoblangach ball o'zgartirish taqiqlanadi (TZ 13.3)."""
        for rec in self:
            ochiq_etiroz = rec.kpi_ids.mapped('etiroz_ids').filtered(
                lambda e: e.holat in ('draft', 'korib_chiqilmoqda'))
            if ochiq_etiroz:
                raise UserError(_(
                    "«%(davr)s» yopilmaydi: %(soni)s ta e'tiroz hali ko'rib "
                    "chiqilmagan. Nizolar hal bo'lgach yoping.",
                    davr=rec.name, soni=len(ochiq_etiroz)))
            rec.kpi_ids.write({'holat': 'qulflangan'})
            rec.holat = 'yopilgan'
            rec.message_post(body=_("Davr yopildi, ballar qulflandi."))
        return True

    def action_ochish(self):
        """Faqat administrator — xato yopilgan davrni qaytarish uchun."""
        if not self.env.user.has_group('base.group_system'):
            raise UserError(_("Yopilgan davrni faqat administrator ochadi."))
        for rec in self:
            rec.kpi_ids.write({'holat': 'hisoblandi'})
            rec.holat = 'ochiq'
        return True

    @api.model
    def _agronova_joriy_davr(self, sana=None):
        """Sanaga mos davr; bo'lmasa oylik davr ochadi."""
        sana = sana or fields.Date.context_today(self)
        davr = self.sudo().search([
            ('boshlanish', '<=', sana), ('tugash', '>=', sana)], limit=1)
        if davr:
            return davr
        boshlanish = sana.replace(day=1)
        from dateutil.relativedelta import relativedelta
        tugash = boshlanish + relativedelta(months=1, days=-1)
        return self.sudo().create({
            'name': boshlanish.strftime('%Y-%m'),
            'boshlanish': boshlanish,
            'tugash': tugash,
        })


class AgroNovaKpi(models.Model):
    _name = 'agronova.kpi'
    _description = "KPI ball yozuvi"
    _inherit = ['mail.thread']
    _order = 'sana desc, id desc'

    name = fields.Char("Nomi", compute='_compute_name', store=True)
    xodim_id = fields.Many2one(
        'res.users', string="Xodim", required=True, index=True, tracking=True)
    davr_id = fields.Many2one(
        'agronova.kpi.davr', string="Davr", required=True, index=True,
        ondelete='restrict')
    sana = fields.Date(
        "Sana", required=True, default=fields.Date.context_today, index=True)
    mezon_turi = fields.Selection(
        MEZON, string="Mezon", required=True, index=True)
    qiymat = fields.Float(
        "O'lchangan qiymat",
        help="Mezonga qarab: ish soati, foiz yoki 0..10 baho.")
    norma = fields.Float("Norma", help="Qiymat solishtirilgan chegara.")
    ball = fields.Float("Ball (0..10)", required=True, tracking=True)
    formula_izohi = fields.Char(
        "Formula", compute='_compute_formula_izohi',
        help="Ball qanday hisoblangani — xodimga ochiq (TZ 13.4).")
    nizoli = fields.Boolean(
        "Nizoli belgilangan",
        help="Omborchi «nizoli» sababini tanlagan — rahbar hal qiladi.")
    manba_model = fields.Char("Manba modeli", readonly=True)
    manba_id = fields.Integer("Manba yozuvi", readonly=True)
    manba_nomi = fields.Char(
        "Manba hujjat", compute='_compute_manba_nomi')
    holat = fields.Selection(
        [('hisoblandi', "Hisoblandi"),
         ('etiroz', "E'tiroz bildirilgan"),
         ('qayta_yozildi', "E'tiroz bo'yicha qayta yozildi"),
         ('qulflangan', "Qulflangan")],
        string="Holati", default='hisoblandi', required=True, tracking=True)
    etiroz_ids = fields.One2many(
        'agronova.kpi.etiroz', 'kpi_id', string="E'tirozlar")
    izoh = fields.Char("Izoh")

    @api.depends('xodim_id', 'mezon_turi', 'sana')
    def _compute_name(self):
        mezonlar = dict(MEZON)
        for rec in self:
            rec.name = "%s — %s (%s)" % (
                rec.xodim_id.name or '', mezonlar.get(rec.mezon_turi, ''),
                rec.sana or '')

    def _compute_formula_izohi(self):
        for rec in self:
            rec.formula_izohi = FORMULA_IZOHI.get(rec.mezon_turi, '')

    def _compute_manba_nomi(self):
        for rec in self:
            nomi = False
            if rec.manba_model and rec.manba_id:
                yozuv = self.env[rec.manba_model].browse(rec.manba_id).exists()
                nomi = yozuv.display_name if yozuv else False
            rec.manba_nomi = nomi

    # ------------------------------------------------------------- formula
    @api.model
    def _agronova_ball_hisoblash(self, mezon, qiymat, norma):
        """Ochiq formula — TZ 13.4. Natija har doim 0..10 oralig'ida."""
        if mezon in ('javob_tezligi', 'tasdiqlash_tezligi'):
            kechikish = max(qiymat - norma, 0.0)
            ball = 10.0 - kechikish * KECHIKISH_JARIMASI
        elif mezon in ('toliqlik', 'muddat', 'sifat'):
            ball = qiymat
        elif mezon == 'narx_tejami':
            ball = 5.0 + qiymat
        elif mezon == 'javobsiz_sorovlar':
            ball = 0.0
        else:
            ball = 0.0
        return min(max(ball, 0.0), 10.0)

    @api.model
    def _agronova_ball_yozish(self, user, mezon, manba, qiymat=0.0, norma=0.0,
                           nizoli=False, sana=None):
        """Hodisa sodir bo'lgan zahoti ball yozadi (jonli ko'rinish, TZ 13.2)."""
        if not user:
            return self.browse()
        sana = sana or fields.Date.context_today(self)
        davr = self.env['agronova.kpi.davr']._agronova_joriy_davr(sana)
        if davr.holat == 'yopilgan':
            # Yopilgan davrga orqaga ball yozilmaydi (TZ 13.3) — yozuv
            # keyingi ochiq davrga tushadi, izohi bilan.
            davr = self.env['agronova.kpi.davr']._agronova_joriy_davr(
                fields.Date.context_today(self))
        return self.sudo().create({
            'xodim_id': user.id,
            'davr_id': davr.id,
            'sana': sana,
            'mezon_turi': mezon,
            'qiymat': qiymat,
            'norma': norma,
            'ball': self._agronova_ball_hisoblash(mezon, qiymat, norma),
            'nizoli': nizoli,
            'manba_model': manba._name if manba else False,
            'manba_id': manba.id if manba else False,
        })

    def write(self, vals):
        if set(vals) - {'holat', 'etiroz_ids', 'message_ids',
                        'message_follower_ids'}:
            for rec in self:
                if rec.holat == 'qulflangan':
                    raise UserError(_(
                        "«%s» qulflangan davrga tegishli — ball "
                        "o'zgartirilmaydi (TZ 13.3).", rec.display_name))
        return super().write(vals)

    def unlink(self):
        if any(rec.holat == 'qulflangan' for rec in self):
            raise UserError(_("Qulflangan ball o'chirilmaydi."))
        return super().unlink()

    def action_etiroz(self):
        """Xodim ballga e'tiroz bildiradi (TZ 13.1)."""
        self.ensure_one()
        if self.holat == 'qulflangan':
            raise UserError(_(
                "Davr yopilgan — e'tiroz muddati o'tdi."))
        return {
            'type': 'ir.actions.act_window',
            'name': _("Ballga e'tiroz"),
            'res_model': 'agronova.kpi.etiroz',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_kpi_id': self.id},
        }


class AgroNovaKpiEtiroz(models.Model):
    _name = 'agronova.kpi.etiroz'
    _description = "KPI balliga e'tiroz"
    # activity.mixin — e'tiroz kelganda rahbarga faoliyat ochiladi.
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    kpi_id = fields.Many2one(
        'agronova.kpi', string="Ball yozuvi", required=True,
        ondelete='cascade', index=True)
    xodim_id = fields.Many2one(
        'res.users', related='kpi_id.xodim_id', store=True, readonly=True,
        string="Xodim")
    eski_ball = fields.Float(
        "E'tiroz paytidagi ball", readonly=True, copy=False)
    yangi_ball = fields.Float(
        "Taklif qilinayotgan ball",
        help="E'tiroz qondirilsa ball shu qiymatga qayta yoziladi.")
    sabab = fields.Text("Sabab", required=True)
    korib_chiquvchi_id = fields.Many2one(
        'res.users', string="Ko'rib chiquvchi", readonly=True, copy=False)
    qaror_izohi = fields.Text("Qaror izohi")
    holat = fields.Selection(
        [('draft', "Yuborilmagan"),
         ('korib_chiqilmoqda', "Ko'rib chiqilmoqda"),
         ('qondirildi', "Qondirildi"),
         ('rad_etildi', "Rad etildi")],
        string="Holati", default='draft', required=True, tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'eski_ball' not in vals and vals.get('kpi_id'):
                vals['eski_ball'] = self.env['agronova.kpi'].browse(
                    vals['kpi_id']).ball
        etirozlar = super().create(vals_list)
        etirozlar.action_yuborish()
        return etirozlar

    def action_yuborish(self):
        for rec in self:
            if rec.holat != 'draft':
                continue
            rec.holat = 'korib_chiqilmoqda'
            rec.kpi_id.sudo().holat = 'etiroz'
            guruh = self.env.ref('agronova_zakupka.group_zakupka_bolim_boshligi',
                                 raise_if_not_found=False)
            for user in (guruh.sudo().all_user_ids if guruh else []):
                rec.activity_schedule(
                    'mail.mail_activity_data_todo', user_id=user.id,
                    summary=_("KPI e'tirozi: %s", rec.xodim_id.name),
                    note=rec.sabab)
        return True

    def action_qondirish(self):
        for rec in self:
            if rec.holat != 'korib_chiqilmoqda':
                raise UserError(_("Faqat ko'rib chiqilayotgan e'tiroz hal qilinadi."))
            rec.kpi_id.sudo().write({
                'ball': rec.yangi_ball,
                'holat': 'qayta_yozildi',
                'izoh': _("E'tiroz qondirildi: %s", rec.qaror_izohi or rec.sabab),
            })
            rec.write({'holat': 'qondirildi',
                       'korib_chiquvchi_id': self.env.user.id})
            rec.activity_unlink(['mail.mail_activity_data_todo'])
        return True

    def action_rad_etish(self):
        for rec in self:
            if rec.holat != 'korib_chiqilmoqda':
                raise UserError(_("Faqat ko'rib chiqilayotgan e'tiroz hal qilinadi."))
            if not rec.qaror_izohi:
                raise UserError(_("Rad etish sababini yozing."))
            rec.kpi_id.sudo().holat = 'hisoblandi'
            rec.write({'holat': 'rad_etildi',
                       'korib_chiquvchi_id': self.env.user.id})
            rec.activity_unlink(['mail.mail_activity_data_todo'])
        return True
