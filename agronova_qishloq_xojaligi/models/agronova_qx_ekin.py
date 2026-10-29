# -*- coding: utf-8 -*-
"""Ekin turi ma'lumotnomasi — bug'doy, makkajo'xori va boshqalar."""
from odoo import fields, models


class AgroNovaQxEkin(models.Model):
    _name = 'agronova.qx.ekin'
    _description = "Qishloq xo'jaligi — ekin turi"
    _order = 'name'

    name = fields.Char("Ekin nomi", required=True)
    code = fields.Char("Kod")
    product_id = fields.Many2one(
        'product.product', string="Hosil mahsuloti",
        domain="[('is_storable', '=', True)]",
        help="Hosil omborga shu mahsulot sifatida kirim qilinadi. "
             "Ko'rsatilmasa hosil hujjatida qo'lda tanlanadi.")
    urug_product_id = fields.Many2one(
        'product.product', string="Urug' mahsuloti",
        domain="[('is_storable', '=', True)]",
        help="Ekish ishida standart holda taklif qilinadi.")
    yetishtirish_kun = fields.Integer(
        "Yetishtirish muddati (kun)",
        help="Ekishdan o'rimgacha o'rtacha necha kun. Rejalashtirishda "
             "ishlatiladi.")
    norma_hosildorlik = fields.Float(
        "Normativ hosildorlik (kg/ga)",
        help="Reja-fakt taqqoslash uchun. Fakt shundan past bo'lsa "
             "hisobotda ko'rinadi.")
    active = fields.Boolean("Faol", default=True)
    note = fields.Text("Izoh")
