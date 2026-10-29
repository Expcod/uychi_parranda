# -*- coding: utf-8 -*-
"""To'lovlarni kassa kitobiga ko'chirish.

Naqd jurnal orqali qilingan HAR QANDAY to'lov — hisob-fakturadan, xarid
buyurtmasidan yoki buxgalteriyadan — kassaning kunlik kitobiga tushishi
kerak. Aks holda kassir kechqurun pulni sanaganda hisob chiqmaydi.

Provodka bu yerda YOZILMAYDI: to'lovning o'z provodkasi bor, shuning
uchun ko'chirilgan yozuv `manba != 'qol'` bilan, ya'ni avtomatik sifatida
yoziladi.
"""
import logging

from odoo import _, api, fields, models

from .utils import uz_datetime

_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    agronova_harakat_id = fields.Many2one(
        'agronova.kassa.harakat', string="Kassa yozuvi", readonly=True,
        copy=False, index=True,
    )

    # ------------------------------------------------------------------
    # Holat o'zgarishlari
    # ------------------------------------------------------------------

    def action_post(self):
        res = super().action_post()
        if not self.env.context.get('agronova_kassa_skip_mirror'):
            self._agronova_kassa_yozish()
        return res

    def action_cancel(self):
        res = super().action_cancel()
        self._agronova_kassa_storno(_("To'lov bekor qilindi"))
        return res

    def action_draft(self):
        res = super().action_draft()
        self._agronova_kassa_storno(_("To'lov qoralamaga qaytarildi"))
        return res

    def unlink(self):
        harakatlar = self.mapped('agronova_harakat_id')
        res = super().unlink()
        harakatlar._avto_storno(_("To'lov o'chirildi"))
        return res

    # ------------------------------------------------------------------
    # Ko'chirish
    # ------------------------------------------------------------------

    def _agronova_kassa_yozish(self):
        Kassa = self.env['agronova.kassa']
        Harakat = self.env['agronova.kassa.harakat']
        for pay in self:
            if pay.agronova_harakat_id:
                continue
            kassa = Kassa._for_journal(pay.journal_id)
            if not kassa:
                continue
            direction = 'in' if pay.payment_type == 'inbound' else 'out'
            manba = pay._agronova_manba(direction)
            summa = pay._agronova_summa(kassa)
            if not summa:
                continue
            try:
                harakat = Harakat._avto_yozuv(kassa, {
                    'date': uz_datetime(pay.date),
                    'direction': direction,
                    'amount': summa,
                    'modda_id': pay._agronova_modda(direction, manba).id or False,
                    'partner_id': pay.partner_id.id or False,
                    'izoh': pay._agronova_izoh(),
                    'manba': manba,
                    'payment_id': pay.id,
                    'origin': pay.display_name,
                    'user_id': self.env.user.id,
                })
            except Exception as e:  # noqa: BLE001 — to'lov kassa xatosidan yiqilmasin
                _logger.exception(
                    "To'lovni kassa kitobiga yozib bo'lmadi (%s): %s", pay.id, e)
                continue
            pay.sudo().agronova_harakat_id = harakat.id

    def _agronova_kassa_storno(self, sabab):
        self.mapped('agronova_harakat_id')._avto_storno(sabab)

    # ------------------------------------------------------------------
    # Yordamchi
    # ------------------------------------------------------------------

    def _agronova_summa(self, kassa):
        """To'lov summasi kassa valyutasida."""
        self.ensure_one()
        if not self.currency_id or self.currency_id == kassa.currency_id:
            return self.amount
        return self.currency_id._convert(
            self.amount, kassa.currency_id, self.company_id, self.date)

    def _agronova_manba(self, direction):
        self.ensure_one()
        if direction == 'in' and self.partner_type == 'customer':
            return 'sotuv'
        if direction == 'out' and self.partner_type == 'supplier':
            return 'xarid'
        return 'boshqa'

    @api.model
    def _agronova_modda_ref(self, xmlid):
        return (self.env.ref('agronova_kassa.%s' % xmlid, raise_if_not_found=False)
                or self.env['agronova.kassa.modda'])

    def _agronova_modda(self, direction, manba):
        self.ensure_one()
        if manba == 'sotuv':
            return self._agronova_modda_ref('modda_sotuv')
        if manba == 'xarid':
            return self._agronova_modda_ref('modda_yetkazuvchi')
        return self._agronova_modda_ref(
            'modda_boshqa_kirim' if direction == 'in' else 'modda_boshqa_chiqim')

    def _agronova_izoh(self):
        """Kassa kitobida ko'rinadigan izoh."""
        self.ensure_one()
        qismlar = []
        if self.partner_id:
            qismlar.append(self.partner_id.display_name)
        hujjatlar = self.reconciled_invoice_ids | self.reconciled_bill_ids
        if hujjatlar:
            qismlar.append(', '.join(hujjatlar.mapped('name')[:3]))
        if self.memo and not any(self.memo in q for q in qismlar):
            qismlar.append(self.memo)
        return ' — '.join([q for q in qismlar if q]) or (self.display_name or '')
