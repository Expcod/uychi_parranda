# -*- coding: utf-8 -*-
"""Tashqi mijoz xizmati va mahsulotni qaytarish (TZ 5, 6-band).

Tashqi mijoz tovuqni so'yish uchun olib keladi. Tovuq ham, undan chiqqan
mahsulot ham **mijozning mulki** — biz faqat xizmat ko'rsatamiz:

    Xizmat summasi = so'yilgan tovuq soni × 1 dona narxi

Mahsulot mijozga qaytariladi. Agar darhol olib ketmasa, korxonaning
**vaqtinchalik saqlash omborida** turadi va o'sha yerda ham mijozning
mulki sifatida yuritiladi (TZ 6-band).

Odooda buning uchun tayyor mexanizm bor — konsignatsiya: `stock.quant`
dagi **egasi** (`owner_id`) maydoni. «Manage Different Stock Owners»
guruhi yoqilsa, bir omborda bir necha egaga tegishli mahsulot alohida
hisobda turadi. Shuning uchun bu qismga custom ombor mantiqi yozilmagan.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AgroNovaSoyishXizmat(models.Model):
    _name = 'agronova.soyish.xizmat'
    _description = "So'yish — tashqi mijoz xizmati"
    _inherit = ['mail.thread']
    _order = 'sana desc, id desc'

    name = fields.Char(
        "Hujjat", default=lambda self: _("Yangi"), copy=False, readonly=True,
        index=True)
    sana = fields.Date(
        "Sana", required=True, default=fields.Date.context_today, tracking=True)
    partiya_id = fields.Many2one(
        'agronova.soyish.partiya', string="Partiya", required=True,
        ondelete='restrict', index=True,
        domain="[('manba', '=', 'tashqi')]")
    partner_id = fields.Many2one(
        related='partiya_id.partner_id', string="Mijoz", store=True,
        readonly=True)
    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True, readonly=True,
        store=True, precompute=True, compute='_compute_company_id')
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)

    # --- partiyadan (ma'lumot uchun)
    kelgan_son = fields.Integer(
        related='partiya_id.tirik_son', string="Kelgan tovuq (dona)",
        readonly=True)
    kelgan_vazn = fields.Float(
        related='partiya_id.tirik_vazn_kg', string="Kelgan netto vazn (kg)",
        readonly=True)
    soyilgan_son = fields.Integer(
        related='partiya_id.soyilgan_son', string="So'yilgan (dona)",
        readonly=True)
    tayyor_kg = fields.Float(
        related='partiya_id.tushka_vazn_kg', string="Tayyor mahsulot (kg)",
        readonly=True)

    # --- xizmat
    dona_narx = fields.Monetary(
        "1 dona so'yish narxi", required=True, tracking=True)
    xizmat_summa = fields.Monetary(
        "Jami xizmat summasi", compute='_compute_summa', store=True)

    # --- qaytarish
    qaytarilgan_kg = fields.Float(
        "Mijozga qaytarilgan (kg)", digits='Product Unit', tracking=True)
    omborda_kg = fields.Float(
        "Vaqtincha omborda qolgan (kg)", compute='_compute_summa', store=True,
        digits='Product Unit',
        help="Tayyor mahsulot minus qaytarilgani. Bu miqdor mijozning "
             "mulki sifatida omborda turadi.")

    holat = fields.Selection(
        [('draft', "Qoralama"), ('done', "Rasmiylashtirilgan")],
        string="Holati", default='draft', required=True, tracking=True,
        copy=False)
    izoh = fields.Text("Izoh")

    # ------------------------------------------------------------- compute
    @api.depends('partiya_id')
    def _compute_company_id(self):
        for r in self:
            r.company_id = r.partiya_id.company_id or self.env.company

    @api.depends('soyilgan_son', 'dona_narx', 'tayyor_kg', 'qaytarilgan_kg')
    def _compute_summa(self):
        for r in self:
            r.xizmat_summa = r.soyilgan_son * r.dona_narx
            r.omborda_kg = max(r.tayyor_kg - r.qaytarilgan_kg, 0.0)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _("Yangi"):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'agronova.soyish.xizmat') or _("Yangi")
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('agronova_soyish_post'):
            for r in self:
                if r.holat == 'done' and set(vals) - {
                        'izoh', 'qaytarilgan_kg', 'message_ids',
                        'message_follower_ids'}:
                    raise UserError(_(
                        "«%s» rasmiylashtirilgan — tahrirlanmaydi. "
                        "Faqat qaytarilgan miqdorni yangilash mumkin.",
                        r.name))
        return super().write(vals)

    # ------------------------------------------------------------ amallar
    def action_rasmiylashtirish(self):
        """Xizmat haqini partiya daromadiga yozadi."""
        for r in self:
            if r.holat == 'done':
                continue
            if not r.soyilgan_son:
                raise UserError(_(
                    "«%s» partiyasida hali so'yish qayd etilmagan.",
                    r.partiya_id.name))
            if not r.dona_narx:
                raise UserError(_("1 dona so'yish narxi ko'rsatilmagan."))
            r.partiya_id.xizmat_narx = r.dona_narx
            r.partiya_id._agronova_post_analytic(
                name=_("So'yish xizmati: %(son)s dona × %(narx).0f",
                       son=r.soyilgan_son, narx=r.dona_narx),
                amount=r.xizmat_summa,          # daromad — musbat
                date=r.sana,
                unit_amount=r.soyilgan_son,
                extra={'company_id': r.company_id.id,
                       'partner_id': r.partner_id.id or False},
            )
            r.with_context(agronova_soyish_post=True).holat = 'done'
            r.message_post(body=_(
                "Xizmat rasmiylashtirildi: %(son)s dona × %(narx).0f = "
                "%(jami).0f so'm",
                son=r.soyilgan_son, narx=r.dona_narx, jami=r.xizmat_summa))
        return True
