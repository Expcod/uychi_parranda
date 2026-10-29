# -*- coding: utf-8 -*-
"""Ichki kirimlarda qiymat yo'qolib qolmasin.

Odoo 19 da ombor baholashi qayta yozilgan: harakatning qiymati endi
`price_unit` maydonidan OLINMAYDI. Odoo qiymatni shu tartibda qidiradi
(`stock_account/models/stock_move.py: _get_value_data`):

    qo'lda kiritilgan qiymat -> hisob-faktura -> sotuv/xarid qatori
    -> mahsulotning standart tannarxi

Bizning ichki hujjatlarimiz (tuxum kirimi, jo'ja ochilishi, hosil
kirimi, so'yish chiqimi va h.k.) esa mahsulotni **partiya tannarxida**
omborga kiritadi — hisob-faktura ham, xarid qatori ham yo'q. Ular
`price_unit` ni to'ldirardi va Odoo 18 da bu ishlardi; 19 da esa
e'tiborsiz qoldirilib, harakat qiymati **nol** bo'lib qolgan edi.
Natijada omborda tuxum bor, qiymati yo'q — FIFO zanjiri ham
shakllanmagan.

Odoo 19 ning o'zi shu holat uchun `value_manual` maydonini beradi
("Useful for testing and custom valuation"). Shu yerda o'sha ko'prik
quriladi: harakat tugagach, agar qiymat topilmagan bo'lsa-yu
`price_unit` ko'rsatilgan bo'lsa — qiymat qo'lda yoziladi.

Standart xarid/sotuv harakatlariga tegmaydi: ularda qiymat allaqachon
hisob-fakturadan yoki xarid qatoridan kelib chiqadi, ya'ni nolga teng
emas va bu shart ishlamaydi.
"""
from odoo import models


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _action_done(self, cancel_backorder=False):
        moves = super()._action_done(cancel_backorder=cancel_backorder)
        moves._agronova_qiymatni_tiklash()
        return moves

    def _agronova_qiymatni_tiklash(self):
        for move in self:
            if move.state != 'done' or not move.is_valued:
                continue
            if not move.price_unit or move.company_currency_id.compare_amounts(
                    move.value, 0.0) != 0:
                continue
            miqdor = move._get_valued_qty()
            if not miqdor:
                continue
            move.value_manual = move.price_unit * miqdor
