# -*- coding: utf-8 -*-
"""Inkubator jihozlari kartotekasi (TZ 4-band).

Partiyada «inkubator raqami» talab qilingan. Uni oddiy matn qilib
qo'yish mumkin edi, lekin unda hisobotda «inkubatorlar kesimida
natijalar» (TZ 10-band) chiqmaydi: raqam har safar boshqacha yozilsa
guruhlab bo'lmaydi.

Shuning uchun alohida kartoteka. Qo'shimcha foydasi — sig'im nazorati:
inkubatorga sig'imidan ko'p tuxum qo'yib bo'lmaydi.
"""
from odoo import _, api, fields, models


class AgroNovaInkInkubator(models.Model):
    _name = 'agronova.ink.inkubator'
    _description = "Inkubator"
    _order = 'kod, name'

    name = fields.Char("Nomi", required=True)
    kod = fields.Char("Raqami", required=True,
                      help="Masalan: INK-01. Hisobotlarda shu bo'yicha "
                           "guruhlanadi.")
    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True,
        default=lambda self: self.env.company)
    sigim = fields.Integer("Sig'imi (dona tuxum)", required=True,
                           help="Bir martada qancha tuxum sig'adi.")
    turi = fields.Selection([
        ('inkubatsiya', "Inkubatsiya (asosiy)"),
        ('vivarium', "Chiqarish (vivarium)"),
        ('universal', "Universal"),
    ], string="Turi", default='inkubatsiya', required=True)
    active = fields.Boolean("Faol", default=True)
    izoh = fields.Text("Izoh")

    partiya_ids = fields.One2many('agronova.ink.partiya', 'inkubator_id',
                                  string="Partiyalar")
    holat = fields.Selection([
        ('bosh', "Bo'sh"),
        ('band', "Band"),
        ('tamir', "Ta'mirda"),
    ], string="Holati", default='bosh', required=True, compute='_compute_holat',
        store=True, readonly=False,
        help="Ta'mir holati qo'lda qo'yiladi — unda partiya qo'yib "
             "bo'lmaydi.")
    joriy_partiya_id = fields.Many2one(
        'agronova.ink.partiya', string="Joriy partiya", compute='_compute_holat',
        store=True)
    band_dona = fields.Integer("Bandligi (dona)", compute='_compute_holat',
                               store=True)

    _kod_uniq = models.Constraint(
        'UNIQUE(kod, company_id)',
        "Bu inkubator raqami shu korxonada allaqachon bor.",
    )
    _sigim_musbat = models.Constraint(
        'CHECK (sigim > 0)', "Sig'im noldan katta bo'lishi kerak.")

    @api.depends('partiya_ids.holat', 'partiya_ids.tuxum_dona')
    def _compute_holat(self):
        for ink in self:
            band = ink.partiya_ids.filtered(
                lambda p: p.holat == 'inkubatsiyada')
            ink.joriy_partiya_id = band[:1]
            ink.band_dona = sum(band.mapped('tuxum_dona'))
            # Ta'mir qo'lda qo'yiladi va avtomat o'zgarmaydi.
            if ink.holat != 'tamir':
                ink.holat = 'band' if band else 'bosh'

    @api.depends('kod', 'name')
    def _compute_display_name(self):
        for ink in self:
            ink.display_name = " · ".join(
                x for x in (ink.kod, ink.name) if x)

    def action_tamirga(self):
        self.write({'holat': 'tamir'})
        return True

    def action_tamirdan(self):
        for ink in self:
            ink.holat = 'band' if ink.joriy_partiya_id else 'bosh'
        return True

    def bosh_joy(self):
        """Nechta tuxum sig'adi — sig'im minus hozir bandligi."""
        self.ensure_one()
        return max(self.sigim - self.band_dona, 0)
