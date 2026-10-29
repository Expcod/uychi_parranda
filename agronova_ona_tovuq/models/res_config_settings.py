# -*- coding: utf-8 -*-
"""Ona tovuq sozlamalari — normativ chegaralar va mahsulot bog'lanishi."""
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    agronova_ot_eskirish_chegara = fields.Float(
        "Eskirish chegarasi (%)",
        config_parameter='agronova_ona_tovuq.eskirish_chegara',
        help="So'nggi 7 kunlik o'rtacha tuxum berish shu foizdan past bo'lsa, "
             "poda «eskirgan» deb belgilanadi.")
    agronova_ot_tannarxdan_past_taqiq = fields.Boolean(
        "Tannarxdan past sotuvni taqiqlash",
        config_parameter='agronova_ona_tovuq.tannarxdan_past_taqiq', default=True)
    agronova_ot_product_inkubatsion = fields.Many2one(
        'product.product', string="Inkubatsion tuxum mahsuloti",
        config_parameter='agronova_ona_tovuq.product_inkubatsion')
    agronova_ot_product_tovar = fields.Many2one(
        'product.product', string="Tovar tuxum mahsuloti",
        config_parameter='agronova_ona_tovuq.product_tovar')
    agronova_ot_product_brak = fields.Many2one(
        'product.product', string="Brak tuxum mahsuloti",
        config_parameter='agronova_ona_tovuq.product_brak')
    agronova_ot_product_poda = fields.Many2one(
        'product.product', string="Eskirgan poda (tirik tovuq) mahsuloti",
        config_parameter='agronova_ona_tovuq.product_poda',
        help="Poda so'yishga o'tkazilganda shu mahsulot So'yish omboriga "
             "kirim qilinadi.")
    agronova_ot_company_inkubatsiya = fields.Many2one(
        'res.company', string="Inkubatsiya bo'limi",
        config_parameter='agronova_ona_tovuq.company_inkubatsiya',
        help="Tuxum ichki sotuvida mahsulot shu korxona omboriga tushadi.")
    agronova_ot_company_soyish = fields.Many2one(
        'res.company', string="So'yish bo'limi",
        config_parameter='agronova_ona_tovuq.company_soyish',
        help="Eskirgan poda shu korxona omboriga tushadi va u yerda qabul "
             "hujjati ochiladi.")
