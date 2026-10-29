# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    agronova_tarozi_normal_kg = fields.Float(
        "Me'yorda: kg gacha", default=40.0,
        config_parameter='agronova_tarozi.normal_kg')
    agronova_tarozi_normal_pct = fields.Float(
        "yoki % gacha", default=0.2,
        config_parameter='agronova_tarozi.normal_pct')
    agronova_tarozi_ogohlantirish_kg = fields.Float(
        "Ogohlantirish: kg gacha", default=100.0,
        config_parameter='agronova_tarozi.ogohlantirish_kg')
    agronova_tarozi_ogohlantirish_pct = fields.Float(
        "yoki % gacha", default=0.5,
        config_parameter='agronova_tarozi.ogohlantirish_pct')
    agronova_tarozi_tasdiq_kg = fields.Float(
        "Tasdiq kerak: kg gacha", default=300.0,
        config_parameter='agronova_tarozi.tasdiq_kg')
    agronova_tarozi_tasdiq_pct = fields.Float(
        "yoki % gacha", default=1.0,
        config_parameter='agronova_tarozi.tasdiq_pct')
