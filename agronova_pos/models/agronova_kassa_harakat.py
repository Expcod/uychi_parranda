# -*- coding: utf-8 -*-
"""Kassa harakatiga POS manbasini qo'shish.

`agronova_kassa` moduli POS haqida bilmaydi (u undan oldin yozilgan va
POS'siz ham ishlaydi), shuning uchun manba ro'yxati shu yerdan
kengaytiriladi.

Yozuv **avtomatik** deb belgilanadi: smena yopilganda Odoo o'zining
provodkasini yozgan bo'ladi, kassa harakati esa faqat kitobdagi qatorni
beradi. Avtomatik yozuvni kassir qo'lda tahrirlay ham, storno qila ham
olmaydi — buning uchun smenani ochish kerak.
"""
from odoo import api, fields, models


class AgroNovaKassaHarakat(models.Model):
    _inherit = 'agronova.kassa.harakat'

    manba = fields.Selection(
        selection_add=[('pos', "POS smenasi")],
        ondelete={'pos': 'set default'},
    )
    pos_session_id = fields.Many2one(
        'pos.session', string="POS smenasi", readonly=True, copy=False,
        ondelete='set null', index=True,
        help="Qaysi smenaning naqd tushumi shu yozuvni yaratgan.",
    )

    # Kassir panelidagi belgi. `agronova_kassa` dagi lug'at oddiy sinf
    # atributi bo'lgani uchun uni to'liq qayta yozamiz — POS qatori
    # boshqalaridan ajralib tursin.
    MANBA_BELGI = {
        'qol': '', 'sotuv': '🧾', 'xarid': '📦', 'oylik': '👷',
        'otkazma': '⇄', 'inkassatsiya': '🏦', 'boshqa': '💳',
        'pos': '🛒',
    }

    @api.depends('manba')
    def _compute_auto(self):
        """POS yozuvi ham avtomatik — provodkasi smenada yozilgan."""
        super()._compute_auto()
        for rec in self:
            if rec.manba == 'pos':
                rec.auto = True

    def _panel_kim(self):
        """Kassir panelida «Kim» ustuni: savdo nuqtasining nomi."""
        self.ensure_one()
        kim = super()._panel_kim()
        if not kim and self.pos_session_id:
            kim = self.pos_session_id.config_id.name
        return kim

    def action_open_source(self):
        """Manba hujjat — smenaning o'zi."""
        self.ensure_one()
        if self.pos_session_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'pos.session',
                'res_id': self.pos_session_id.id,
                'views': [(False, 'form')],
            }
        return super().action_open_source()
