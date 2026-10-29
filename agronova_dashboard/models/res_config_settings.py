# -*- coding: utf-8 -*-
"""Brend (oq yorliq) va normativlar — har bir mijoz korxona o'zinikini beradi.

Qiymatlar `ir.config_parameter` da saqlanadi (`agronova.*`), dashboard ularni
`agronova.executive.dashboard._norm()` va `get_dashboard_meta()` orqali o'qiydi.
"""
from odoo import fields, models

from .agronova_executive_dashboard import BRAND_DEFAULT, NORM_DEFAULTS, TAGLINE_DEFAULT


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    agronova_brand_name = fields.Char(
        "Panel nomi (brend)", config_parameter='agronova.brand_name', default=BRAND_DEFAULT,
        help="Rahbar paneli sarlavhasida chiqadigan nom. Har bir mijoz uchun o'zgartiriladi.")
    agronova_brand_tagline = fields.Char(
        "Shior", config_parameter='agronova.brand_tagline', default=TAGLINE_DEFAULT)

    agronova_norm_fcr = fields.Float(
        "FCR normativi", config_parameter='agronova.norm_fcr', default=NORM_DEFAULTS["fcr"],
        digits=(6, 3), help="1 kg tirik vaznga sarflanadigan yem, kg.")
    agronova_norm_nobud = fields.Float(
        "Boquv nobudgarchiligi, %", config_parameter='agronova.norm_nobud',
        default=NORM_DEFAULTS["nobud"])
    agronova_norm_vazn = fields.Float(
        "O'rtacha tirik vazn, kg", config_parameter='agronova.norm_vazn',
        default=NORM_DEFAULTS["vazn"], digits=(6, 3))
    agronova_norm_soyish_chiqim = fields.Float(
        "So'yishdagi chiqim, %", config_parameter='agronova.norm_soyish_chiqim',
        default=NORM_DEFAULTS["soyish_chiqim"])
    agronova_norm_ochilish = fields.Float(
        "Inkubatsiyada ochilish, %", config_parameter='agronova.norm_ochilish',
        default=NORM_DEFAULTS["ochilish"])
    agronova_norm_tuxum_berish = fields.Float(
        "Tuxum berish, %", config_parameter='agronova.norm_tuxum_berish',
        default=NORM_DEFAULTS["tuxum_berish"])
