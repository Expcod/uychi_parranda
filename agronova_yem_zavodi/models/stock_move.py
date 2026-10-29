# -*- coding: utf-8 -*-
"""Komponent bo'yicha reja va haqiqiy sarf (TZ 3.3).

**Reja** retsepturadan olinadi: qator miqdori × (buyurtma hajmi /
retseptura partiyasi). `product_uom_qty` ga tayanib bo'lmaydi — buyurtma
yopilganda Odoo kam sarflangan harakatni bo'lib yuboradi va talabni
haqiqiy miqdorga tenglashtiradi, shunda farq doim nol chiqardi.

Bitta retseptura qatoriga bir necha harakat to'g'ri kelishi mumkin
(bo'linish, qo'shimcha berish). Reja va farq **birinchi** harakatda
turadi, haqiqiy miqdor esa guruh bo'yicha yig'iladi — yig'indilar doim
to'g'ri chiqadi.
"""
from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = 'stock.move'

    agronova_reja_kg = fields.Float("Reja (kg)", compute='_compute_agronova_sarf', store=True,
                                    digits=(16, 2))
    agronova_fakt_kg = fields.Float("Haqiqiy (kg)", compute='_compute_agronova_sarf', store=True,
                                    digits=(16, 2))
    agronova_farq_kg = fields.Float("Farq (kg)", compute='_compute_agronova_sarf', store=True,
                                    digits=(16, 2))
    agronova_farq_pct = fields.Float("Farq (%)", compute='_compute_agronova_sarf', store=True,
                                     digits=(16, 2))
    agronova_ogish_limit = fields.Float("Ruxsat (%)", compute='_compute_agronova_sarf', store=True,
                                        digits=(16, 2))
    agronova_limitdan_oshdi = fields.Boolean("Me'yordan tashqari", compute='_compute_agronova_sarf',
                                             store=True)

    @api.model
    def _agronova_reja_kg(self, production, bom_line):
        """Retseptura qatori bo'yicha shu buyurtmaga reja (kg)."""
        P = self.env['product.product']
        bom = bom_line.bom_id
        if not bom or not bom.product_qty:
            return 0.0
        mo_qty = production.product_uom_id._compute_quantity(
            production.product_qty, bom.product_uom_id, round=False)
        return P._agronova_kg(bom_line.product_qty, bom_line.product_uom_id) * mo_qty / bom.product_qty

    @api.depends('quantity', 'product_uom', 'state', 'bom_line_id.agronova_ogish_foiz',
                 'raw_material_production_id.product_qty',
                 'raw_material_production_id.move_raw_ids.quantity',
                 'raw_material_production_id.move_raw_ids.state')
    def _compute_agronova_sarf(self):
        P = self.env['product.product']
        guruh_kesh = {}
        for m in self:
            m.agronova_reja_kg = m.agronova_farq_kg = 0.0
            m.agronova_farq_pct = m.agronova_ogish_limit = 0.0
            m.agronova_limitdan_oshdi = False
            m.agronova_fakt_kg = P._agronova_kg(m.quantity, m.product_uom)
            mo = m.raw_material_production_id
            if not mo or m.state == 'cancel':
                continue
            kalit = (mo.id, m.bom_line_id.id or ('p', m.product_id.id))
            if kalit not in guruh_kesh:
                # Qardosh harakatlar faqat o'qiladi — qiymat faqat `m` ga yoziladi.
                qardosh = mo.move_raw_ids.filtered(
                    lambda x: (x.bom_line_id.id or ('p', x.product_id.id)) == kalit[1]
                    and x.state != 'cancel')
                guruh_kesh[kalit] = (
                    min(qardosh.ids) if qardosh.ids else m.id,
                    sum(P._agronova_kg(x.quantity, x.product_uom) for x in qardosh),
                )
            birinchi_id, fakt = guruh_kesh[kalit]
            if m.id != birinchi_id and isinstance(m.id, int):
                continue
            bom_line = m.bom_line_id
            reja = self._agronova_reja_kg(mo, bom_line) if bom_line else 0.0
            limit = bom_line.agronova_ogish_foiz if bom_line else 0.0
            m.agronova_reja_kg = reja
            m.agronova_ogish_limit = limit
            m.agronova_farq_kg = fakt - reja
            m.agronova_farq_pct = ((fakt - reja) / reja * 100.0) if reja else 0.0
            m.agronova_limitdan_oshdi = bool(
                (reja and fakt and abs(m.agronova_farq_pct) > limit)
                # Retsepturada yo'q komponent berilgan bo'lsa ham — og'ish.
                or (not bom_line and fakt))
