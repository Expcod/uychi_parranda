# -*- coding: utf-8 -*-
"""Yo'qotishlar reyestri (TZ 5.2, 5.3).

Ikki ko'rsatkich doim alohida: **me'yoriy** (texnolog tasdiqlagan) va
**haqiqiy** (o'lchov va inventarizatsiyadan). Yozuv yashirilmaydi — rad
etilgani ham reyestrda qoladi, faqat hisobotga kirmaydi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

TURLAR = [
    ('texnologik', "Texnologik yo'qotish"),
    ('tokilish', "To'kilish"),
    ('namlik', "Namlik o'zgarishi"),
    ('qadoqlash', "Qadoqlashdagi tafovut"),
    ('tortish', "Tortish tafovuti"),
    ('brak', "Brak"),
    ('inventarizatsiya', "Inventarizatsiya farqi"),
    ('boshqa', "Boshqa sabab"),
]


class AgroNovaYemYoqotish(models.Model):
    _name = 'agronova.yem.yoqotish'
    _description = "Yem zavodi — yo'qotish"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'agronova.yem.smena.qulf.mixin']
    _order = 'sana desc, id desc'

    name = fields.Char("Raqam", required=True, copy=False, readonly=True, default=lambda s: _("Yangi"))
    company_id = fields.Many2one('res.company', "Korxona", required=True, default=lambda s: s.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    sana = fields.Datetime("Sana va vaqt", required=True, default=fields.Datetime.now, tracking=True)
    production_id = fields.Many2one('mrp.production', "Ishlab chiqarish buyurtmasi", index='btree_not_null')
    product_id = fields.Many2one('product.product', "Mahsulot / xomashyo", required=True, tracking=True)
    smena_id = fields.Many2one('agronova.yem.smena', "Smena", index='btree_not_null')
    liniya_id = fields.Many2one('agronova.yem.liniya', "Liniya")
    turi = fields.Selection(TURLAR, "Sabab turi", required=True, default='texnologik', tracking=True)
    miqdor_kg = fields.Float("Yo'qotish (kg)", required=True, digits=(16, 2), tracking=True)
    meyoriy_kg = fields.Float("Me'yor (kg)", digits=(16, 2),
                              help="Shu hajm uchun ruxsat etilgan yo'qotish. Texnologik yo'qotishda "
                                   "retseptura me'yoridan olinadi.")
    tafovut_kg = fields.Float("Me'yordan farq (kg)", compute='_compute_tafovut', store=True, digits=(16, 2))
    meyorda_kg = fields.Float("Me'yor doirasida (kg)", compute='_compute_tafovut', store=True, digits=(16, 2))
    ortiqcha_kg = fields.Float("Me'yordan ortiq (kg)", compute='_compute_tafovut', store=True, digits=(16, 2))
    meyordan_ortiq = fields.Boolean("Me'yordan ortiq", compute='_compute_tafovut', store=True)
    sabab = fields.Text("Sabab va izoh")
    masul_id = fields.Many2one('hr.employee', "Mas'ul shaxs", tracking=True)
    dalolatnoma = fields.Char("Dalolatnoma №")
    dalolatnoma_fayl = fields.Binary("Dalolatnoma fayli", attachment=True)
    dalolatnoma_nomi = fields.Char()
    state = fields.Selection([
        ('draft', "Loyiha"), ('tekshiruvda', "Tekshiruvda"), ('tasdiqlangan', "Tasdiqlangan"),
        ('rad', "Rad etilgan"),
    ], "Holat", default='draft', required=True, tracking=True)
    tasdiqlagan_id = fields.Many2one('res.users', "Tasdiqlagan", readonly=True)
    birlik_narx = fields.Float("1 kg qiymati", compute='_compute_qiymat', store=True, digits='Product Price')
    qiymat = fields.Monetary("Moliyaviy ta'siri", compute='_compute_qiymat', store=True)
    avtomatik = fields.Boolean("Avtomatik", readonly=True,
                               help="Buyurtma yopilganda tizim yozgan texnologik yo'qotish.")

    @api.model_create_multi
    def create(self, vals_list):
        for v in vals_list:
            if v.get('name', _("Yangi")) == _("Yangi"):
                v['name'] = self.env['ir.sequence'].next_by_code('agronova.yem.yoqotish') or _("Yangi")
        recs = super().create(vals_list)
        recs._smena_qulf_tekshir()
        return recs

    @api.onchange('production_id')
    def _onchange_production(self):
        mo = self.production_id
        if mo:
            self.product_id = mo.product_id
            self.liniya_id = mo.agronova_liniya_id
            self.smena_id = mo.agronova_smena_id

    @api.depends('miqdor_kg', 'meyoriy_kg')
    def _compute_tafovut(self):
        for y in self:
            y.tafovut_kg = y.miqdor_kg - y.meyoriy_kg
            y.meyorda_kg = min(y.miqdor_kg, y.meyoriy_kg)
            y.ortiqcha_kg = max(y.miqdor_kg - y.meyoriy_kg, 0.0)
            y.meyordan_ortiq = y.ortiqcha_kg > 0.05

    @api.depends('miqdor_kg', 'product_id', 'production_id.agronova_xomashyo_qiymat',
                 'production_id.agronova_kirim_kg')
    def _compute_qiymat(self):
        P = self.env['product.product']
        for y in self:
            mo = y.production_id
            if mo and mo.agronova_kirim_kg:
                narx = mo.agronova_xomashyo_qiymat / mo.agronova_kirim_kg
            else:
                kg1 = P._agronova_kg(1.0, y.product_id.uom_id) or 1.0
                narx = (y.product_id.standard_price or 0.0) / kg1
            y.birlik_narx = narx
            y.qiymat = narx * y.miqdor_kg

    # ----------------------------------------------------------------- amallar
    def _boshliqqa_vazifa(self):
        guruh = self.env.ref('agronova_yem_zavodi.group_yem_boshliq', raise_if_not_found=False)
        for y in self:
            for u in (guruh.user_ids[:3] if guruh else []):
                y.activity_schedule(
                    'mail.mail_activity_data_todo', user_id=u.id,
                    summary=_("Me'yordan ortiq yo'qotish: %s kg", round(y.ortiqcha_kg, 1)),
                    note=_("%(n)s — %(p)s. Sababini aniqlab, tasdiqlang yoki rad eting.",
                           n=y.name, p=y.product_id.display_name))

    def action_tekshiruvga(self):
        for y in self.filtered(lambda r: r.state == 'draft'):
            if not y.masul_id and not y.avtomatik:
                raise UserError(_("Mas'ul shaxsni ko'rsating."))
            y.state = 'tekshiruvda'
            if y.meyordan_ortiq:
                y._boshliqqa_vazifa()
        return True

    def _tekshiruvchi(self):
        if not self.env.user.has_group('agronova_yem_zavodi.group_yem_boshliq'):
            raise UserError(_("Yo'qotishni faqat ishlab chiqarish boshlig'i tasdiqlaydi yoki rad etadi."))

    def action_tasdiqlash(self):
        self._tekshiruvchi()
        for y in self:
            if y.meyordan_ortiq and not (y.sabab or '').strip():
                raise UserError(_("Me'yordan ortiq yo'qotish sababsiz tasdiqlanmaydi."))
            y.write({'state': 'tasdiqlangan', 'tasdiqlagan_id': self.env.user.id})
            y.activity_ids.action_done()
        return True

    def action_rad(self):
        self._tekshiruvchi()
        for y in self:
            y.write({'state': 'rad', 'tasdiqlagan_id': self.env.user.id})
            y.activity_ids.action_done()
        return True

    def action_loyiha(self):
        self._tekshiruvchi()
        self.write({'state': 'draft'})
        return True
