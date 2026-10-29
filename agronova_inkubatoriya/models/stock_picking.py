# -*- coding: utf-8 -*-
"""Tuxum omborga kirsa — «Tuxum qabuli» qoralamasi o'zi ochiladi.

Standart Xarid va qabul hujjati tuxumni Inkubatoriya omboriga kiritadi,
lekin «bu tuxum qaysi inkubatsiya partiyasiga ketadi» degan savolga
javob bermaydi — bu boshqaruv qarori, uni avtomatlashtirib bo'lmaydi
(bitta partiyaga bir necha kun kelgan tuxum qo'shilishi mumkin).

Shuning uchun bu yerda faqat qo'l mehnati olib tashlanadi: qabul
tasdiqlanishi bilan «Tuxum qabuli» hujjati **qoralama** holatida,
miqdori, qiymati, sanasi va jo'natuvchisi to'ldirilgan holda ochiladi.
Operatorga bitta ish qoladi — partiyani tanlab tasdiqlash.

Qiymat manbai: xarid qatoridagi narx (`purchase.order.line.price_unit`).
Odoo'ning o'z ombor baholashi (`stock.move.value`) bu tizimda ishonchli
emas — buni Ona tovuq ko'prigida ham aniqlagan edik.
"""
from odoo import _, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _agronova_ink_tuxum_qabuli(self):
        """Qabul qilingan tuxum uchun qoralama hujjat ochadi."""
        Qabul = self.env['agronova.ink.qabul'].sudo()
        for picking in self:
            if (picking.picking_type_id.code != 'incoming'
                    or picking.state != 'done'):
                continue
            # Bir hujjat ikki marta ochilmasin.
            if Qabul.search_count([('picking_id', '=', picking.id)]):
                continue
            domain = Qabul.with_company(
                picking.company_id)._agronova_mahsulot_domain('tuxum', [])
            tuxumlar = self.env['product.product'].sudo().search(domain)
            kompaniyalar = self.env['res.company'].sudo().search([])
            ichki = {c.partner_id.id: c for c in kompaniyalar if c.partner_id}
            for move in picking.move_ids:
                if move.product_id not in tuxumlar or not move.quantity:
                    continue
                po_line = move.purchase_line_id
                narx = po_line.price_unit if po_line else 0.0
                jonatuvchi = picking.partner_id
                jonatuvchi_company = ichki.get(jonatuvchi.id)
                ichkimi = bool(jonatuvchi_company)
                Qabul.with_company(picking.company_id).create({
                    'date': picking.date_done and picking.date_done.date()
                            or picking.scheduled_date.date(),
                    'manba': 'ichki' if ichkimi else 'tashqi',
                    'company_id': picking.company_id.id,
                    'picking_id': picking.id,
                    'partner_id': False if ichkimi else jonatuvchi.id,
                    'ot_company_id': (jonatuvchi_company.id if ichkimi
                                      else False),
                    'product_id': move.product_id.id,
                    'dona': int(move.quantity),
                    'qiymat': narx * move.quantity,
                    'izoh': _("Avtomat: %s", picking.name),
                })
        return True

    def button_validate(self):
        res = super().button_validate()
        # `button_validate` ba'zan sozlash oynasini qaytaradi — hujjat
        # haqiqatan tugagandagina yozamiz.
        self.filtered(lambda p: p.state == 'done')._agronova_ink_tuxum_qabuli()
        return res
