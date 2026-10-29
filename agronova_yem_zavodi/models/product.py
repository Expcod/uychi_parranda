# -*- coding: utf-8 -*-
from odoo import api, fields, models

YEM_TURI = [
    ('yem', "Tayyor yem"),
    ('xomashyo', "Xomashyo"),
    ('premiks', "Premiks / qo'shimcha"),
    ('qadoq', "Qadoqlash materiali"),
    ('ehtiyot', "Ehtiyot qism"),
]


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    agronova_yem_turi = fields.Selection(YEM_TURI, "Yem zavodi turi", index=True,
                                         help="Yem zavodi hisobotlari va ro'yxatlari shu bo'yicha ajratiladi.")
    agronova_qop_sigim_kg = fields.Float(
        "Qopdagi yem (kg)", digits=(16, 2),
        help="Bir qopdagi nominal yem og'irligi (masalan 40 yoki 50 kg).")
    agronova_qop_product_id = fields.Many2one(
        'product.product', "Qop (qadoq)", domain="[('agronova_yem_turi', '=', 'qadoq')]",
        help="Shu yem qadoqlanadigan qop. Qadoqlashda qop sarfi shu mahsulotdan chiqadi.")
    agronova_qop_vazn_kg = fields.Float(
        "Bo'sh qop vazni (kg)", digits=(16, 3),
        help="Qadoqlash materiali uchun: bitta bo'sh qopning tasdiqlangan og'irligi.")


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.model
    def _agronova_kg(self, qty, uom):
        """Miqdorni kilogrammga o'giradi; og'irlik birligi bo'lmasa 0."""
        kg = self.env.ref('uom.product_uom_kgm', raise_if_not_found=False)
        if not kg or not uom or not qty:
            return 0.0
        if uom == kg:
            return qty
        if not uom._has_common_reference(kg):
            return 0.0
        return uom._compute_quantity(qty, kg, round=False)

    @api.model
    def _agronova_kg_dan(self, kg_qty, uom):
        """Kilogrammdan mahsulot birligiga."""
        kg = self.env.ref('uom.product_uom_kgm')
        if not uom or uom == kg:
            return kg_qty
        return kg._compute_quantity(kg_qty, uom, round=False)
