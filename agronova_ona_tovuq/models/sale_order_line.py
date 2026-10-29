# -*- coding: utf-8 -*-
"""Tashqi sotuv — B11.

Umumiy TZ M08 talabi: **tannarxdan past sotuv taqiqlanadi**. Sotuv
qatorida tannarx va marja ko'rinib turadi — sotuvchi qaror qabul qilishdan
oldin ko'radi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # Tannarx korxonaga bog'liq (har bo'limda o'z FIFO qiymati), shuning
    # uchun saqlanmaydi: saqlansa qaysi korxonada hisoblangani tasodifiy
    # bo'lib qoladi va boshqa bo'limda noto'g'ri (ko'pincha nol) turadi.
    agronova_tannarx = fields.Monetary(
        "Tannarx", compute='_compute_agronova_marja', readonly=True,
        help="Mahsulotning shu korxonadagi joriy tannarxi. Qo'lda kiritilmaydi.")
    agronova_marja = fields.Monetary(
        "Marja", compute='_compute_agronova_marja', readonly=True)
    agronova_marja_foiz = fields.Float(
        "Marja (%)", compute='_compute_agronova_marja', readonly=True)

    @api.depends('product_id', 'product_uom_qty', 'price_subtotal', 'company_id')
    def _compute_agronova_marja(self):
        for line in self:
            tannarx = line.product_id.with_company(
                line.company_id or self.env.company).standard_price or 0.0
            line.agronova_tannarx = tannarx
            jami_tannarx = tannarx * line.product_uom_qty
            line.agronova_marja = line.price_subtotal - jami_tannarx
            line.agronova_marja_foiz = (
                line.agronova_marja / line.price_subtotal * 100.0
                if line.price_subtotal else 0.0)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        """Tannarxdan past sotuvni bloklaydi."""
        ICP = self.env['ir.config_parameter'].sudo()
        if ICP.get_param('agronova_ona_tovuq.tannarxdan_past_taqiq', 'True') == 'True':
            for order in self:
                past = order.order_line.filtered(
                    lambda l: l.agronova_tannarx and l.product_uom_qty
                    and l.price_unit < l.agronova_tannarx)
                if past:
                    raise UserError(_(
                        "Tannarxdan past narxda sotib bo'lmaydi:\n%s",
                        "\n".join(
                            "· %s — narx %s, tannarx %s" % (
                                l.product_id.display_name, l.price_unit,
                                l.agronova_tannarx)
                            for l in past)))
        return super().action_confirm()
