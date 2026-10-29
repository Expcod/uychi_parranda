# -*- coding: utf-8 -*-
"""Zayavka — omborchidan kelgan xarid buyurtmasi (TZ 4.1, 14-bo'lim).

Zanjirning birinchi halqasi:

    Omborchi zayavka berdi
       -> Zakupchik qabul qildi (1-tasdiq, javob tezligi KPI ga tushadi)
       -> yoki rad etdi (sabab bilan, omborchiga qaytadi)

Javob muddati **muhimlik darajasidan** kelib chiqadi va markazlashgan ish
vaqti kalendari bo'yicha hisoblanadi — tunda va dam olishda muddat
o'smaydi (TZ 13.5, 21.7).

Nega OCA `purchase_request` emas: bu o'rnatmaning addons_path ida u modul
yo'q va 19.0 uchun port ham chiqmagan. Shuning uchun so'rov qobig'i shu
yerda, lekin u tovar ham, pul ham qimirlatmaydi — faqat ruxsat hujjatiga
ulanish nuqtasi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

MUHIMLIK = [
    ('1_juda_muhim', "1 — juda muhim"),
    ('2_orta', "2 — o'rta muhim"),
    ('3_zaxira', "3 — zaxira uchun"),
]
MUHIMLIK_PARAM = {
    '1_juda_muhim': ('agronova_zakupka.muddat_juda_muhim', 1.0),
    '2_orta': ('agronova_zakupka.muddat_orta', 1.5),
    '3_zaxira': ('agronova_zakupka.muddat_zaxira', 3.0),
}
RAD_SABABI = [
    ('bozorda_yoq', "Bozorda yo'q"),
    ('narx_baland', "Narx juda baland"),
    ('muddat_real_emas', "Muddat real emas"),
    ('boshqa', "Boshqa sabab"),
]


class AgroNovaZayavka(models.Model):
    _name = 'agronova.zayavka'
    _description = "Xarid zayavkasi"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'agronova.muddat.mixin']
    _order = 'muhimlik_darajasi, maksimal_muddat, id desc'

    name = fields.Char(
        "Zayavka raqami", default=lambda self: _("Yangi"),
        copy=False, readonly=True, index=True)
    warehouse_id = fields.Many2one(
        'stock.warehouse', string="Ombor", required=True, tracking=True,
        help="Tovar qaysi omborga kerak.")
    omborchi_id = fields.Many2one(
        'res.users', string="Omborchi", required=True, tracking=True,
        default=lambda self: self.env.user)
    zakupchik_id = fields.Many2one(
        'res.users', string="Zakupchik", tracking=True, copy=False,
        domain="[('share', '=', False)]",
        help="Zayavkani qabul qilgan xodim.")
    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True,
        default=lambda self: self.env.company)

    qator_ids = fields.One2many(
        'agronova.zayavka.qatori', 'zayavka_id', string="Qatorlar", copy=True)

    # --- sanalar. TZ 21.4: operatsiya sanasi va kiritilgan sana alohida.
    sana = fields.Date(
        "Zayavka sanasi", required=True, tracking=True,
        default=fields.Date.context_today)
    kiritilgan_sana = fields.Datetime(
        "Kiritilgan payt", related='create_date', store=True, readonly=True,
        help="Hech qachon o'zgarmaydi — nazorat izi.")
    maksimal_muddat = fields.Datetime(
        "Tovar kerak bo'lgan muddat", required=True, tracking=True,
        help="Tovar shu paytgacha omborda bo'lishi kerak.")
    muhimlik_darajasi = fields.Selection(
        MUHIMLIK, string="Muhimlik", default='2_orta', required=True,
        tracking=True)

    yuborilgan_vaqti = fields.Datetime(
        "Yuborilgan payt", readonly=True, copy=False, tracking=True)
    javob_muddati = fields.Datetime(
        "Javob muddati", readonly=True, copy=False,
        help="Muhimlik darajasidan kelib chiqib, ish vaqti kalendari "
             "bo'yicha hisoblanadi.")
    javob_vaqti = fields.Datetime(
        "Javob berilgan payt", readonly=True, copy=False, tracking=True)

    holat = fields.Selection(
        [('draft', "Qoralama"),
         ('zakupchikka_yuborildi', "Zakupchikka yuborildi"),
         ('qabul_qilindi', "Qabul qilindi"),
         ('rad_etildi', "Rad etildi"),
         ('qisman_bajarildi', "Qisman bajarildi"),
         ('yopildi', "Yopildi")],
        string="Holati", default='draft', required=True, tracking=True, copy=False)
    rad_sababi = fields.Selection(RAD_SABABI, string="Rad sababi", tracking=True)
    rad_izohi = fields.Text("Rad izohi", tracking=True)
    izoh = fields.Text("Izoh")

    ruxsat_ids = fields.One2many(
        'agronova.ruxsat', 'zayavka_id', string="Ruxsat so'rovlari")
    ruxsat_soni = fields.Integer("Ruxsatlar", compute='_compute_ruxsat_soni')
    bajarilish_foizi = fields.Float(
        "Bajarilish (%)", compute='_compute_bajarilish', store=True)

    # ------------------------------------------------------------- compute
    def _compute_ruxsat_soni(self):
        for rec in self:
            rec.ruxsat_soni = len(rec.ruxsat_ids)

    @api.depends('qator_ids.miqdor', 'qator_ids.bajarilgan_miqdor')
    def _compute_bajarilish(self):
        for rec in self:
            soralgan = sum(rec.qator_ids.mapped('miqdor'))
            bajarilgan = sum(rec.qator_ids.mapped('bajarilgan_miqdor'))
            rec.bajarilish_foizi = (
                100.0 * min(bajarilgan, soralgan) / soralgan) if soralgan else 0.0

    def _agronova_muddat_maydoni(self):
        return 'javob_muddati', 'javob_vaqti'

    # ---------------------------------------------------------- validatsiya
    @api.constrains('maksimal_muddat', 'sana')
    def _check_muddat(self):
        for rec in self:
            if rec.maksimal_muddat and rec.maksimal_muddat < rec.create_date:
                raise ValidationError(_(
                    "«%s» zayavkasining kerak bo'lish muddati o'tib ketgan "
                    "paytga qo'yilgan.", rec.display_name))

    @api.constrains('qator_ids')
    def _check_qatorlar(self):
        for rec in self:
            if rec.holat != 'draft' and not rec.qator_ids:
                raise ValidationError(_(
                    "«%s» zayavkasida bironta ham qator yo'q.", rec.display_name))

    # -------------------------------------------------------------- create
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _("Yangi")) == _("Yangi"):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'agronova.zayavka') or _("Yangi")
        return super().create(vals_list)

    # ------------------------------------------------------------ workflow
    def _agronova_javob_soati(self):
        self.ensure_one()
        kalit, standart = MUHIMLIK_PARAM[self.muhimlik_darajasi]
        return float(self.env['ir.config_parameter'].sudo().get_param(
            kalit, standart) or standart)

    def action_yuborish(self):
        for rec in self:
            if rec.holat != 'draft':
                raise UserError(_("Faqat qoralama zayavka yuboriladi."))
            if not rec.qator_ids:
                raise UserError(_(
                    "Bo'sh zayavka yuborilmaydi — tovar qatorlarini kiriting."))
            hozir = fields.Datetime.now()
            rec.write({
                'holat': 'zakupchikka_yuborildi',
                'yuborilgan_vaqti': hozir,
                'javob_muddati': rec._agronova_muddat_qoshish(
                    hozir, rec._agronova_javob_soati()),
                'eskalatsiya_darajasi': 0,
            })
            rec._agronova_zakupchiklarga_xabar()
        return True

    def _agronova_zakupchiklarga_xabar(self):
        """Barcha zakupchiklarga faoliyat (activity) ochadi."""
        self.ensure_one()
        guruh = self.env.ref('agronova_zakupka.group_zakupka_zakupchik',
                             raise_if_not_found=False)
        if not guruh:
            return
        for user in guruh.sudo().all_user_ids:
            self.activity_schedule(
                'mail.mail_activity_data_todo', user_id=user.id,
                summary=_("Yangi zayavka: %s", self.name),
                note=_("«%(ombor)s» ombori %(muhimlik)s zayavka yubordi. "
                       "Javob muddati: %(muddat)s.",
                       ombor=self.warehouse_id.display_name,
                       muhimlik=dict(MUHIMLIK)[self.muhimlik_darajasi],
                       muddat=self.javob_muddati))

    def action_qabul_qilish(self):
        for rec in self:
            if rec.holat != 'zakupchikka_yuborildi':
                raise UserError(_(
                    "Faqat yuborilgan zayavka qabul qilinadi."))
            rec.write({
                'holat': 'qabul_qilindi',
                'zakupchik_id': self.env.user.id,
                'javob_vaqti': fields.Datetime.now(),
            })
            rec._agronova_kechikish_yangilash()
            rec.activity_unlink(['mail.mail_activity_data_todo'])
            rec._agronova_javob_kpi()
            rec.message_post(body=_("Zayavka qabul qilindi."))
        return True

    def action_rad_etish(self):
        for rec in self:
            if rec.holat != 'zakupchikka_yuborildi':
                raise UserError(_("Faqat yuborilgan zayavka rad etiladi."))
            if not rec.rad_sababi:
                raise UserError(_(
                    "Rad etish sababi majburiy — omborchi nima uchun "
                    "rad etilganini bilishi kerak (TZ 4.1)."))
            rec.write({
                'holat': 'rad_etildi',
                'zakupchik_id': self.env.user.id,
                'javob_vaqti': fields.Datetime.now(),
            })
            rec._agronova_kechikish_yangilash()
            rec.activity_unlink(['mail.mail_activity_data_todo'])
            rec._agronova_javob_kpi()
            rec.message_post(body=_(
                "Rad etildi: %(sabab)s. %(izoh)s",
                sabab=dict(RAD_SABABI)[rec.rad_sababi], izoh=rec.rad_izohi or ''))
        return True

    def action_yopish(self):
        for rec in self:
            if rec.holat not in ('qabul_qilindi', 'qisman_bajarildi'):
                raise UserError(_(
                    "Faqat qabul qilingan yoki qisman bajarilgan zayavka "
                    "yopiladi."))
            rec.holat = 'yopildi'
        return True

    def action_qoralamaga(self):
        for rec in self:
            if rec.holat not in ('rad_etildi',):
                raise UserError(_(
                    "Faqat rad etilgan zayavka qoralamaga qaytariladi."))
            rec.write({'holat': 'draft', 'javob_vaqti': False,
                       'javob_muddati': False, 'yuborilgan_vaqti': False,
                       'eskalatsiya_darajasi': 0})
        return True

    def action_ruxsat_yaratish(self):
        """Qabul qilingan zayavkadan ruxsat so'rovi ochadi."""
        self.ensure_one()
        if self.holat != 'qabul_qilindi':
            raise UserError(_(
                "Ruxsat so'rovi faqat qabul qilingan zayavkadan ochiladi."))
        return {
            'type': 'ir.actions.act_window',
            'name': _("Sotib olishga ruxsat"),
            'res_model': 'agronova.ruxsat',
            'view_mode': 'form',
            'context': {
                'default_zayavka_id': self.id,
                'default_muhimlik_darajasi': self.muhimlik_darajasi,
                'default_zakupchik_id': self.env.user.id,
            },
        }

    def action_ruxsatlarni_korish(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Ruxsat so'rovlari"),
            'res_model': 'agronova.ruxsat',
            'view_mode': 'list,form',
            'domain': [('zayavka_id', '=', self.id)],
            'context': {'default_zayavka_id': self.id},
        }

    # ----------------------------------------------------------------- KPI
    def _agronova_javob_kpi(self):
        """Javob tezligini KPI ga yozadi."""
        self.ensure_one()
        if not self.zakupchik_id or not self.yuborilgan_vaqti:
            return
        soat = self._agronova_ish_soatlari(self.yuborilgan_vaqti, self.javob_vaqti)
        norma = self._agronova_javob_soati()
        self.env['agronova.kpi']._agronova_ball_yozish(
            user=self.zakupchik_id,
            mezon='javob_tezligi',
            manba=self,
            qiymat=soat,
            norma=norma,
        )

    # ---------------------------------------------------------------- cron
    @api.model
    def _cron_muddat_nazorati(self):
        """Javobsiz zayavkalarni eskalatsiya qiladi (TZ 6, 13.5)."""
        kutayotgan = self.sudo().search([
            ('holat', '=', 'zakupchikka_yuborildi'),
            ('javob_muddati', '!=', False),
            ('javob_muddati', '<', fields.Datetime.now()),
        ])
        kutayotgan._agronova_kechikish_yangilash()
        oraliq = int(self.env['ir.config_parameter'].sudo().get_param(
            'agronova_zakupka.eskalatsiya_oraliq', 30) or 30) / 60.0
        for rec in kutayotgan:
            kerakli = 1
            if rec.kechikish_soati >= oraliq:
                kerakli = 2
            if kerakli <= rec.eskalatsiya_darajasi:
                continue
            rec.eskalatsiya_darajasi = kerakli
            rec._agronova_eskalatsiya(kerakli)
        return True

    def _agronova_eskalatsiya(self, daraja):
        """1 — bo'lim boshlig'iga, 2 — yuqori rahbarga."""
        self.ensure_one()
        if daraja == 1:
            guruh = self.env.ref('agronova_zakupka.group_zakupka_bolim_boshligi',
                                 raise_if_not_found=False)
            userlar = guruh.sudo().all_user_ids if guruh else self.env['res.users']
            matn = _("Zayavkaga javob muddati o'tdi — zakupchiklar javob "
                     "bermadi.")
        else:
            userlar = self.omborchi_id.zakupka_rahbar_id or self.env.ref(
                'base.user_admin', raise_if_not_found=False) or self.env['res.users']
            matn = _("Zayavka ikkinchi muddat ham o'tdi — yuqori rahbarga "
                     "ko'tarildi.")
            # Javobsiz qolgan so'rov tasdiqlovchilar KPI siga tushadi.
            guruh = self.env.ref('agronova_zakupka.group_zakupka_zakupchik',
                                 raise_if_not_found=False)
            for user in (guruh.sudo().all_user_ids if guruh else []):
                self.env['agronova.kpi']._agronova_ball_yozish(
                    user=user, mezon='javobsiz_sorovlar', manba=self,
                    qiymat=1.0, norma=0.0)
        for user in userlar:
            self.activity_schedule(
                'mail.mail_activity_data_todo', user_id=user.id,
                summary=_("Kechikkan zayavka: %s", self.name), note=matn)
        self.message_post(body=matn)


class AgroNovaZayavkaQatori(models.Model):
    _name = 'agronova.zayavka.qatori'
    _description = "Zayavka qatori"
    _order = 'zayavka_id, id'

    zayavka_id = fields.Many2one(
        'agronova.zayavka', string="Zayavka", required=True,
        ondelete='cascade', index=True)
    product_id = fields.Many2one(
        'product.product', string="Tovar", required=True,
        domain="[('purchase_ok', '=', True)]")
    miqdor = fields.Float("So'ralgan miqdor", required=True, default=1.0)
    olchov_birligi_id = fields.Many2one(
        'uom.uom', string="O'lchov birligi",
        compute='_compute_olchov_birligi_id', store=True, readonly=False)
    bajarilgan_miqdor = fields.Float(
        "Bajarilgan miqdor", compute='_compute_bajarilgan', store=True,
        help="Kirim hujjatlarida shu qatorga yozilgan miqdor — qisman "
             "yetkazishni kuzatish uchun.")
    qoldiq_miqdor = fields.Float(
        "Qolgan miqdor", compute='_compute_bajarilgan', store=True)
    izoh = fields.Char("Izoh")
    kirim_qatori_ids = fields.One2many(
        'agronova.kirim.qatori', 'zayavka_qatori_id', string="Kirim qatorlari")

    @api.depends('product_id')
    def _compute_olchov_birligi_id(self):
        for qator in self:
            qator.olchov_birligi_id = qator.product_id.uom_id

    @api.depends('miqdor', 'kirim_qatori_ids.qabul_miqdor',
                 'kirim_qatori_ids.kirim_id.holat')
    def _compute_bajarilgan(self):
        for qator in self:
            bajarilgan = sum(
                q.qabul_miqdor for q in qator.kirim_qatori_ids
                if q.kirim_id.holat in ('tasdiqlangan', 'qabul_qilindi'))
            qator.bajarilgan_miqdor = bajarilgan
            qator.qoldiq_miqdor = max(qator.miqdor - bajarilgan, 0.0)

    @api.constrains('miqdor')
    def _check_miqdor(self):
        for qator in self:
            if qator.miqdor <= 0:
                raise ValidationError(_(
                    "«%s» qatorida miqdor noldan katta bo'lishi kerak.",
                    qator.product_id.display_name))
