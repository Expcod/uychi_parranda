# -*- coding: utf-8 -*-
from odoo import fields, models

TAQSIMLASH_BAZASI = [
    ('bosh_soni', "Bosh soni bo'yicha"),
    ('m2', "Maydon (m²) bo'yicha"),
    ('teng', "Teng bo'lib"),
    ('togridan', "To'g'ridan-to'g'ri (bitta obyektga)"),
]


class AgroNovaXarajatKategoriya(models.Model):
    """Xarajat kategoriyasi.

    TZ bo'yicha kategoriyani faqat administrator yaratadi (xarajat nomini
    esa oddiy foydalanuvchi kiritishi mumkin). Har kategoriyaga standart
    taqsimlash bazasi bog'lanadi — hujjatda uni o'zgartirsa bo'ladi.
    """
    _name = 'agronova.xarajat.kategoriya'
    _description = "Xarajat kategoriyasi"
    _order = 'sequence, name'

    name = fields.Char("Kategoriya", required=True, translate=False)
    code = fields.Char("Kod")
    sequence = fields.Integer("Tartib", default=10)
    taqsimlash_bazasi = fields.Selection(
        TAQSIMLASH_BAZASI, string="Standart taqsimlash bazasi",
        default='m2', required=True,
        help="Shu kategoriyadagi xarajat standart holda qaysi baza bo'yicha "
             "obyektlarga taqsimlanadi. Hujjatda o'zgartirilishi mumkin.")
    account_id = fields.Many2one(
        'account.account', string="Xarajat hisobi",
        help="Moliyaviy hisobga o'tkazishda ishlatiladigan hisob raqami.")
    is_ish_haqi = fields.Boolean(
        "Ish haqi kategoriyasi",
        help="Belgilansa, bu kategoriya xodim biriktirilgan obyektga "
             "to'g'ridan-to'g'ri, biriktirilmagan xodimda esa m² bo'yicha "
             "taqsimlanadi.")
    active = fields.Boolean("Faol", default=True)
    company_id = fields.Many2one(
        'res.company', string="Korxona", default=lambda self: self.env.company)
    note = fields.Text("Izoh")

    _name_uniq = models.Constraint(
        'UNIQUE(name, company_id)',
        "Bu nomdagi xarajat kategoriyasi allaqachon mavjud.",
    )
