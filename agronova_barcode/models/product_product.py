"""Serialli mahsulotning qoldiq ro'yxatini yig'ilgan holda ochish.

Serialli mahsulotda har bir dona alohida quant — 122 dona tovar 122 ta qator
degani. Omborchi uchun bu o'qib bo'lmaydigan ro'yxat: qancha borligini sanash
uchun pastgacha aylantirish kerak.

Yechim: lokatsiya bo'yicha guruhlab ochish. Guruh sarlavhasida jami son turadi
("4-SEH/Tayyor (122)"), ochilsa ichidagi seriyalar ko'rinadi. Bu Odoo'ning
standart guruhlash mexanizmi — hech narsa buzilmaydi, faqat boshlang'ich
ko'rinish qulayroq bo'ladi.
"""
from odoo import models


class ProductProduct(models.Model):
    _inherit = "product.product"

    def action_open_quants(self):
        action = super().action_open_quants()
        # Faqat serialli mahsulotda — lot bilan kuzatiladigan mahsulotda bitta
        # lotda ko'p dona bo'ladi, ro'yxat allaqachon qisqa.
        if all(product.tracking == "serial" for product in self) and self:
            context = dict(action.get("context") or {})
            context["search_default_locationgroup"] = 1
            action["context"] = context
        return action
