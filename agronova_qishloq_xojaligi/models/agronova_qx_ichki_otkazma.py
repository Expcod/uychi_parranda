# -*- coding: utf-8 -*-
"""Qishloq xo'jaligi -> Yem zavodi o'tkazmasi — standart Sotuv orqali.

Ilgari bu maxsus `agronova.qx.ichki_berish` hujjati orqali ishlagan: u
faqat pul tomonini (partiyaga daromad + tannarx chiqimi) yozardi,
donning fizik harakati esa butunlay alohida ombor o'tkazmasi bilan
rasmiylashtirilardi — ikkovi bir-biriga bog'lanmagan edi.

Endi oddiy `sale.order` ishlatiladi: mijoz — Yem zavodi korxonasining
kontragenti. Odoo o'zi avtomat `purchase.order` va qabul hujjatini
Yem zavodi tomonida ochadi, ya'ni tovar va pul bitta zanjirda yuradi.

Shu fayl standart oqim bilmaydigan yagona narsani — bizning boshqaruv
hisobimizni (ekin partiyasining analitik hisobi) — yopadi:

    sale.order.line -> qaysi ekin partiyasidan (`agronova_qx_partiya_id`)
    stock.move done  -> partiyaga daromad/tannarx qatori

Tannarx manbasi — partiyaning o'z `tannarx_1_kg` maydoni (jami xarajat
/ olingan hosil), xuddi eski `action_otkazish()` da bo'lgani kabi.
Ona tovuqdagi ko'prikdan farqi shu: u yerda tannarx mahsulotning
`standard_price`idan olinadi, bu yerda esa partiyaning o'zi tannarx
manbai — chunki bir ekin partiyasining tannarxi boshqasinikidan
keskin farq qilishi mumkin.
"""
from odoo import _, fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    agronova_qx_partiya_id = fields.Many2one(
        'agronova.qx.partiya', string="Ekin partiyasi",
        help="Ichki berishda (Yem zavodiga) hosil qaysi ekin "
             "partiyasidan chiqayotgani. Tashqi sotuvda bo'sh qoladi.")


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _action_done(self, cancel_backorder=False):
        moves = super()._action_done(cancel_backorder=cancel_backorder)
        moves._agronova_qx_ichki_otkazma_yozish()
        return moves

    def _agronova_qx_ichki_otkazma_yozish(self):
        """Ekin partiyasiga bog'langan sotuv harakati tugasa yozadi."""
        ichki_kompaniyalar = self.env['res.company'].sudo().search(
            []).mapped('partner_id')
        for move in self:
            line = move.sale_line_id
            partiya = line.agronova_qx_partiya_id if line else False
            if (not partiya or move.state != 'done'
                    or move.raw_material_production_id
                    or line.order_id.partner_id not in ichki_kompaniyalar):
                continue
            # Bitta sotuv qatori bir necha harakatga bo'linishi mumkin
            # (qisman yetkazish) — har biri o'z ulushini yozadi, ikki
            # marta yozilmasligi uchun move belgisi bilan tekshiramiz.
            if partiya.analytic_account_id.line_ids.filtered(
                    lambda al, m=move: al.ref == 'stock.move,%s' % m.id):
                continue
            miqdor = move.quantity
            if not miqdor:
                continue
            ulush = miqdor / line.product_uom_qty if line.product_uom_qty else 0.0
            tushum = line.price_subtotal * ulush
            tannarx = partiya.tannarx_1_kg * miqdor

            partiya._agronova_post_analytic(
                name=_("Ichki berish: %s", line.order_id.name),
                amount=tushum, date=fields.Date.context_today(self),
                unit_amount=miqdor, product=move.product_id,
                extra={'ref': 'stock.move,%s' % move.id})
            if tannarx:
                partiya._agronova_post_analytic(
                    name=_("Ichki berish tannarxi: %s", line.order_id.name),
                    amount=-tannarx, date=fields.Date.context_today(self),
                    unit_amount=miqdor, product=move.product_id,
                    tannarxga=False,
                    extra={'ref': 'stock.move,%s' % move.id})
