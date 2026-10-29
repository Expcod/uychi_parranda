# -*- coding: utf-8 -*-
"""Lot/partiya raqamlari — korxonalar orasida umumiy.

Bo'limlar orasidagi o'tkazmalar standart Sotuv/Xarid orqali ishlaydi.
Odoo'ning korxonalararo sinxronizatsiyasi jo'natish va qabul hujjatida
BITTA `stock.lot` yozuvini ishlatadi. Lot esa odatda yaratilgan
korxonaga qattiq bog'lanadi va Odoo "korxonalar aralashib ketmasin"
deb tekshiruv bilan qabulni bloklaydi.

Odoo'ning o'z yechimi — lotni korxonasiz (`company_id = False`) qilib
qo'yish: bunday lot barcha korxonalar uchun umumiy bo'ladi. Shu fayl
yangi lotlarni doim shunday yaratadi.

DIQQAT: eski lotlarda korxona bor. Ular avtomat tozalanmaydi, chunki
eski (endi ishlatilmaydigan) ichki o'tkazma hujjatlari ba'zi lotni
ikkala korxonada nusxalab yaratgan — nomi bir xil ikkita yozuv.
Korxona olib tashlansa, Odoo'ning bir xil nom taqiqi ishga tushadi.
Ularni birlashtirish alohida, qo'lda qilinadigan tozalash ishi.
"""
from odoo import api, models


class StockLot(models.Model):
    _inherit = 'stock.lot'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['company_id'] = False
        return super().create(vals_list)
