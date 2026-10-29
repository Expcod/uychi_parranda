# -*- coding: utf-8 -*-
"""Smena yopilganda naqd tushumni kassa kitobiga o'tkazish.

TZ M04 kassa kitobini rasmiy kunlik hujjat deb belgilaydi va kun yopish
majburiyatini kiritadi. Agar POS naqdi o'sha kitobga tushmasa, korxonada
ikkita parallel naqd hisobi paydo bo'ladi: Odoo POS smenasi va
`agronova.kassa`. Kassir kechqurun pulni sanaganda ikkalasi ham to'g'ri
ko'rinadi-yu, jami chiqmaydi.

Shuning uchun smena yopilganda **bitta** yig'ma yozuv yoziladi — har
chek uchun emas. Kassa kitobi rasmiy hujjat: unda kun davomidagi 300 ta
chek emas, «POS smenasi №… tushumi» qatori turishi kerak, tafsilot esa
smenaning o'zida qoladi.

Provodka bu yerda YOZILMAYDI: smena yopilganda Odoo o'zining
`account.move` ini yaratadi. Yozuv `manba='pos'` bilan, ya'ni avtomatik
sifatida qo'yiladi — `agronova.kassa.harakat` bunday yozuvlarga provodka
yozmaydi.
"""
import logging

from odoo import _, models

_logger = logging.getLogger(__name__)


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _validate_session(self, balancing_account=False, amount_to_balance=0,
                          bank_payment_method_diffs=None):
        res = super()._validate_session(
            balancing_account=balancing_account,
            amount_to_balance=amount_to_balance,
            bank_payment_method_diffs=bank_payment_method_diffs)
        for session in self:
            try:
                session._agronova_kassaga_yozish()
            except Exception as e:  # noqa: BLE001 — smena yopilishi to'xtamasin
                # Smena allaqachon yopildi va provodkasi yozildi; kassa
                # kitobidagi xato uni orqaga qaytarmasligi kerak, lekin
                # jimgina yo'qolmasligi ham kerak.
                _logger.exception(
                    "POS smenasini kassa kitobiga yozib bo'lmadi (%s): %s",
                    session.name, e)
                session.message_post(body=_(
                    "⚠ Smena naqdi kassa kitobiga yozilmadi: %s\n"
                    "Kassa menejeri qo'lda kiritishi kerak.", e))
        return res

    def _agronova_kassa(self):
        """Smena bog'langan kassa (sozlanmagan bo'lsa — bo'sh recordset)."""
        self.ensure_one()
        return self.config_id.agronova_kassa_id

    def _agronova_naqd_summa(self):
        """Smenada mijozlardan naqd olingan summa.

        DIQQAT — bu yerda `statement_line_ids` yig'indisi ISHLATILMAYDI.
        Smena yopilganda Odoo o'sha ro'yxatga «sanoq farqi» satrini ham
        qo'shadi: kassir 1 000 000 sotib, yashikda 990 000 sanasa,
        −10 000 lik farq satri paydo bo'ladi va yig'indi kamayib ketadi.
        Kassa kitobiga esa **sotuvdan tushgan** pul yozilishi kerak —
        kamomad kitobning o'z mexanizmi bilan, kun yopilganda sanoq va
        farq orqali ko'rsatiladi (TZ M04). Aks holda kamomad ikki marta
        hisobga olinardi: bir marta POS farqida, bir marta kassa
        farqida.

        Kassadan qilingan kirim/chiqim (inkassatsiya, xarajat) POS
        oynasidan emas, kassa modulining o'z hujjatlaridan kiritiladi —
        u yerda modda, provodka va tasdiqlash zanjiri bor.
        """
        self.ensure_one()
        naqd = self.sudo().order_ids.payment_ids.filtered(
            lambda p: p.payment_method_id.is_cash_count)
        return sum(naqd.mapped('amount'))

    def _agronova_kassaga_yozish(self):
        """Smena naqdini kassa kitobiga bitta yig'ma yozuv qilib qo'yadi."""
        self.ensure_one()
        kassa = self._agronova_kassa()
        if not kassa:
            return False
        Harakat = self.env['agronova.kassa.harakat']
        mavjud = Harakat.sudo().search([
            ('pos_session_id', '=', self.id),
            ('state', '=', 'posted'),
        ], limit=1)
        if mavjud:
            return mavjud

        summa = self._agronova_naqd_summa()
        if kassa.currency_id.is_zero(summa):
            return False
        kirimmi = summa > 0
        modda = self.env.ref(
            'agronova_pos.modda_pos_tushum' if kirimmi
            else 'agronova_pos.modda_pos_chiqim', raise_if_not_found=False)
        return Harakat._avto_yozuv(kassa, {
            'date': self.stop_at or self.start_at,
            'direction': 'in' if kirimmi else 'out',
            'amount': abs(summa),
            'modda_id': modda.id if modda else False,
            'manba': 'pos',
            'pos_session_id': self.id,
            'origin': self.name,
            'izoh': _(
                "POS smenasi «%(smena)s» — %(nuqta)s. Cheklar: %(soni)s.",
                smena=self.name, nuqta=self.config_id.name,
                soni=len(self.order_ids)),
        })
