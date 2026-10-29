# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    agronova_yem_qop_usul = fields.Selection(
        [('standart', "Standart (qoplar soni × bitta qop)"), ('haqiqiy', "Bo'sh qoplar tortiladi")],
        "Qop og'irligi usuli", default='standart', config_parameter='agronova_yem.qop_usul')
    agronova_yem_toldirish_tolerans = fields.Float(
        "To'ldirish chegarasi (%)", default=0.5, config_parameter='agronova_yem.toldirish_tolerans_pct',
        help="Qadoqdagi sof yem nominaldan shu foizgacha farq qilsa — me'yorda.")
    agronova_yem_tortish_majburiy = fields.Boolean(
        "Jo'natmada tortish majburiy", default=True, config_parameter='agronova_yem.tortish_majburiy')
    agronova_yem_elektr_narx = fields.Float("1 kVt·soat narxi", config_parameter='agronova_yem.elektr_narx')
    agronova_yem_gaz_narx = fields.Float("1 m³ gaz narxi", config_parameter='agronova_yem.gaz_narx')
    agronova_yem_kwh_norma = fields.Float("Elektr me'yori (kVt·soat / t)", default=35.0,
                                          config_parameter='agronova_yem.kwh_norma_t')
    agronova_yem_qadoq_location_id = fields.Many2one(
        'stock.location', "Qadoq materiallari ombori", domain=[('usage', '=', 'internal')],
        config_parameter='agronova_yem.qadoq_location_id')
    agronova_yem_ona_tovuq_location_id = fields.Many2one(
        'stock.location', "Ona tovuq xo'jaligi ombori", domain=[('usage', '=', 'internal')],
        config_parameter='agronova_yem.ona_tovuq_location_id')
    agronova_yem_boquv_location_id = fields.Many2one(
        'stock.location', "Boquv bo'limi ombori", domain=[('usage', '=', 'internal')],
        config_parameter='agronova_yem.boquv_location_id')
    agronova_yem_ichki_location_id = fields.Many2one(
        'stock.location', "Boshqa ichki xo'jalik ombori", domain=[('usage', '=', 'internal')],
        config_parameter='agronova_yem.ichki_location_id')
