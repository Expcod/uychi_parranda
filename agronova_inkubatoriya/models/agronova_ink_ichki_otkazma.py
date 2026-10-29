# -*- coding: utf-8 -*-
"""Inkubatoriya -> Boquv o'tkazmasi — standart Sotuv orqali.

Ilgari bu maxsus `agronova.ink.ichki_sotuv` hujjati orqali ishlagan. Endi
oddiy `sale.order`: mijoz — Boquv korxonasining kontragenti. Odoo o'zi
avtomat `purchase.order` va qabul hujjatini Boquv tomonida ochadi.

TZ ning talabi o'zgarmaydi: bu oddiy ko'chirish emas, ichki oldi-sotdi —
inkubatsiya bosqichining natijasi alohida ko'rinishi kerak. Shu fayl
o'sha boshqaruv hisobini yozadi:

    sale.order.line -> qaysi inkubatsiya partiyasidan (`agronova_ink_partiya_id`)
    stock.move done  -> partiyaga daromad/tannarx qatori

Tannarx manbai — partiyaning o'z `tannarx_1_joja` maydoni (partiya
yakunlanganda qotadi), xuddi eski `_analitik_yozish()` dagi kabi.
Tannarx qatori `tannarxga=False` bilan yoziladi: berilgan jo'janing
tannarxi qolganlarining birlik tannarxini oshirmasligi kerak.
"""
from odoo import _, fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    agronova_ink_partiya_id = fields.Many2one(
        'agronova.ink.partiya', string="Inkubatsiya partiyasi",
        help="Ichki berishda (Boquvga) jo'ja qaysi partiyadan "
             "chiqayotgani. Tashqi sotuvda bo'sh qoladi.")


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _action_done(self, cancel_backorder=False):
        moves = super()._action_done(cancel_backorder=cancel_backorder)
        moves._agronova_ink_ichki_otkazma_yozish()
        return moves

    def _agronova_ink_ichki_otkazma_yozish(self):
        """Inkubatsiya partiyasiga bog'langan sotuv harakati tugasa yozadi."""
        ichki_kompaniyalar = self.env['res.company'].sudo().search(
            []).mapped('partner_id')
        for move in self:
            line = move.sale_line_id
            partiya = line.agronova_ink_partiya_id if line else False
            if (not partiya or move.state != 'done'
                    or move.raw_material_production_id
                    or line.order_id.partner_id not in ichki_kompaniyalar):
                continue
            # Qisman yetkazishda bir qator bir necha harakatga bo'linadi —
            # har biri o'z ulushini yozadi, takror yozilmasligi uchun
            # harakat belgisi bilan tekshiramiz.
            if partiya.analytic_account_id.line_ids.filtered(
                    lambda al, m=move: al.ref == 'stock.move,%s' % m.id):
                continue
            miqdor = move.quantity
            if not miqdor:
                continue
            ulush = miqdor / line.product_uom_qty if line.product_uom_qty else 0.0
            tushum = line.price_subtotal * ulush
            tannarx = partiya.tannarx_1_joja * miqdor

            partiya._agronova_post_analytic(
                name=_("Ichki sotuv: jo'ja (%s)", line.order_id.name),
                amount=tushum, date=fields.Date.context_today(self),
                unit_amount=miqdor, product=move.product_id,
                extra={'ref': 'stock.move,%s' % move.id})
            if tannarx:
                partiya._agronova_post_analytic(
                    name=_("Ichki sotuv tannarxi: %s", line.order_id.name),
                    amount=-tannarx, date=fields.Date.context_today(self),
                    unit_amount=miqdor, product=move.product_id,
                    tannarxga=False,
                    extra={'ref': 'stock.move,%s' % move.id})
