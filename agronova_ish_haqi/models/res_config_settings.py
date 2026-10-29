# -*- coding: utf-8 -*-
"""Ish haqi provodkasi uchun hisob raqamlari.

Bosh buxgalter tasdiqlashi kerak: O'zbekiston hisoblar rejasida ishlab
chiqarish ish haqi uchun alohida hisob bo'lishi mumkin, bazadagi standart
reja esa faqat umumiy xarajat hisoblarini beradi.
"""
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    agronova_ish_haqi_account_xarajat = fields.Many2one(
        'account.account', string="Ish haqi xarajati hisobi",
        config_parameter='agronova_ish_haqi.account_xarajat',
        domain="[('account_type', '=', 'expense')]",
        help="Provodkaning debet tomoni.")
    agronova_ish_haqi_account_qarz = fields.Many2one(
        'account.account', string="Xodimga qarz hisobi",
        config_parameter='agronova_ish_haqi.account_qarz',
        domain="[('account_type', '=', 'liability_payable')]",
        help="Provodkaning kredit tomoni. Odatda 6710.")
    agronova_ish_haqi_journal = fields.Many2one(
        'account.journal', string="Ish haqi jurnali",
        config_parameter='agronova_ish_haqi.journal',
        domain="[('type', '=', 'general')]")
