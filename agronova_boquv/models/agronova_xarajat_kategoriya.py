# -*- coding: utf-8 -*-
"""Xarajat kategoriyasiga hisobot guruhini qo'shish.

Umumiy TZ, A ilova («Boquv partiyasi tannarxi hisobi») xarajatlarni
oltita satrda ko'rsatadi:

    1. Yem
    2. Jo'ja (boshlang'ich mol)
    3. Kommunal xarajatlar (gaz, elektr, suv)
    4. Ish haqi
    5. Veterinariya va dori-darmon
    6. Amortizatsiya va boshqa xarajatlar

Bazadagi kategoriyalar esa mayda-chuyda (12 ta): «Yo'lkira», «Skotch»,
«Laboratoriya xizmati»… Ularni hisobotda birma-bir ko'rsatish rahbariyatga
foyda bermaydi — shuning uchun har kategoriyaga **hisobot guruhi**
biriktiriladi va A ilova shu guruhlar bo'yicha yig'iladi.

Guruh ko'rsatilmagan kategoriya «Boshqa» ga tushadi — hisobot hech qachon
xarajatni yo'qotmaydi.
"""
from odoo import fields, models

# A ilovadagi satrlar tartibi. Kalit — texnik nom, qiymat — ko'rinadigan
# nom va tartib raqami.
HISOBOT_GURUHI = [
    ('yem', "Yem"),
    ('joja', "Jo'ja (boshlang'ich mol)"),
    ('veterinariya', "Veterinariya va dori-darmon"),
    ('dezinfeksiya', "Dezinfeksiya"),
    ('ish_haqi', "Ish haqi"),
    ('kommunal', "Kommunal (gaz, elektr, suv)"),
    ('soyish', "So'yish xizmati"),
    ('ijara', "Ijara"),
    ('amortizatsiya', "Amortizatsiya"),
    ('boshqa', "Boshqa xarajatlar"),
]


class AgroNovaXarajatKategoriya(models.Model):
    _inherit = 'agronova.xarajat.kategoriya'

    boquv_hisobot_guruhi = fields.Selection(
        HISOBOT_GURUHI, string="Boquv hisobot guruhi",
        help="Partiya tannarxi hisobotida (A ilova) shu kategoriya qaysi "
             "satrga yig'iladi. Ko'rsatilmasa «Boshqa xarajatlar» ga tushadi.")
