# -*- coding: utf-8 -*-
"""Ona tovuq -> boshqa bo'lim o'tkazmasi — standart Sotuv orqali.

Ilgari (B10) bu maxsus `agronova.ona_tovuq.ichki_sotuv` hujjati orqali
ishlagan. Endi oddiy `sale.order` ishlatiladi: mijoz — qabul qiluvchi
bo'limning kontragenti (`res.company.partner_id`). Odoo o'zi avtomat
`purchase.order` va qabul hujjatini ochadi (korxona sozlamalaridagi
"Intercompany" bo'limi).

Standart oqim buxgalteriya provodkasini biladi, lekin bizning
boshqaruv hisobimizni (partiyaning o'z analitik hisobi) bilmaydi.
Shu fayl o'sha bo'shliqni yopadi:

    sale.order.line -> qaysi partiyadan chiqayotgani (`agronova_ot_partiya_id`)
    stock.move done  -> partiyaning analitik hisobiga daromad/tannarx qatori

Tannarx `sale_order_line.py`dagi `agronova_tannarx` (=
`product.with_company(company).standard_price`) dan olinadi — xuddi
tashqi sotuvdagi marja hisobida ishlatilgani kabi.

DIQQAT — `stock.move.value` (Odoo'ning o'z FIFO baholashi) ATAYIN
ISHLATILMAYDI. Sinovda aniqlandi: bu tizimda tuxumning kirim
harakatlarida ham `value=0` chiqadi (FIFO qatlami umuman
yaratilmagan) — `standard_price` esa boshqa yo'l bilan (partiya
tannarxidan qo'lda) to'g'irlanadi. Bu — Odoo'ning o'z baholash
zanjiridagi eski, alohida muammo, shu ko'prikning vazifasi emas.
"""
from odoo import _, fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    agronova_ot_partiya_id = fields.Many2one(
        'agronova.ona_tovuq.partiya.tuxum', string="Ona tovuq partiyasi",
        help="Ichki sotuvda (boshqa bo'limimizga) tuxum qaysi partiyadan "
             "chiqayotgani. Tashqi mijozga sotuvda bo'sh qoldiriladi.")


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _action_done(self, cancel_backorder=False):
        moves = super()._action_done(cancel_backorder=cancel_backorder)
        moves._agronova_ot_ichki_otkazma_yozish()
        return moves

    def _agronova_ot_ichki_otkazma_yozish(self):
        """Partiyaga bog'langan sotuv qatorining harakati tugasa yozadi."""
        ichki_kompaniyalar = self.env['res.company'].sudo().search(
            []).mapped('partner_id')
        for move in self:
            line = move.sale_line_id
            partiya = line.agronova_ot_partiya_id if line else False
            if (not partiya or move.state != 'done'
                    or move.raw_material_production_id
                    or line.order_id.partner_id not in ichki_kompaniyalar):
                continue
            # Bitta sotuv qatori bir necha `stock.move`ga bo'linishi
            # mumkin (qisman yetkazish) — har move o'zining ulushini
            # yozadi, shuning uchun ikki marta yozilmasligi uchun
            # move id belgisi bilan tekshiramiz.
            if partiya.analytic_account_id.line_ids.filtered(
                    lambda al, m=move: al.ref == 'stock.move,%s' % m.id):
                continue
            miqdor = move.quantity
            if not miqdor:
                continue
            ulush = miqdor / line.product_uom_qty if line.product_uom_qty else 0.0
            tushum = line.price_subtotal * ulush
            tannarx = line.agronova_tannarx * miqdor

            partiya._agronova_post_analytic(
                name=_("Ichki sotuv: %s", line.order_id.name),
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
