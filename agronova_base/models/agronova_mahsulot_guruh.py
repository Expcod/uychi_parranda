# -*- coding: utf-8 -*-
"""Mahsulot guruhlari — hujjatda faqat kerakli mahsulot ko'rinsin.

## Muammo

Loyihada 190 dan ortiq nomenklatura bor: yem xomashyosi, dori-darmon,
dezinfeksiya vositalari, go'sht bo'laklari, tuxum, tirik parranda. Hujjat
maydonida hammasi bir ro'yxatda chiqsa, operator inkubatsion tuxum
o'rniga «Arosat» ni tanlab yuborishi hech gap emas — tuxum qabuliga dori
tushib qoladi.

## Yechim

Har bir hujjat maydoni **guruh kodi** bilan cheklanadi. Guruh esa bir yoki
bir necha mahsulot kategoriyasini (kerak bo'lsa alohida mahsulotlarni)
qamraydi. Guruh ma'lumotnomasi bitta joyda turadi: buyurtmachi yangi
kategoriya qo'shsa, kodni o'zgartirmasdan shu yerda belgilab qo'yadi.

Guruh bo'sh bo'lsa (kategoriya ham, mahsulot ham tanlanmagan) filtr
qo'llanmaydi — hujjat ishlashdan to'xtamaydi, faqat ro'yxat torayimaydi.
Bu ataylab: sozlanmagan bazada modul baribir ishlashi kerak.
"""
from odoo import api, fields, models


class AgroNovaMahsulotGuruh(models.Model):
    _name = 'agronova.mahsulot.guruh'
    _description = "AgroNova — mahsulot guruhi"
    _order = 'name'

    name = fields.Char("Guruh", required=True, translate=False)
    kod = fields.Char(
        "Kod", required=True,
        help="Dasturda shu kod bo'yicha izlanadi — o'zgartirmang.")
    izoh = fields.Char("Qayerda ishlatiladi")
    categ_ids = fields.Many2many(
        'product.category', string="Kategoriyalar",
        help="Shu kategoriyalardagi (va ularning ichidagi) mahsulotlar "
             "hujjatda ko'rinadi.")
    product_ids = fields.Many2many(
        'product.product', string="Qo'shimcha mahsulotlar",
        help="Kategoriyaga tushmaydigan, lekin kerak bo'lgan alohida "
             "mahsulotlar.")
    product_soni = fields.Integer("Nechta mahsulot", compute='_compute_soni')
    active = fields.Boolean("Faol", default=True)

    _kod_uniq = models.Constraint('UNIQUE(kod)',
                                  "Bu kod boshqa guruhda ishlatilgan.")

    def _compute_soni(self):
        Product = self.env['product.product']
        for g in self:
            d = g._domain()
            g.product_soni = Product.search_count(d) if d else 0

    def _domain(self):
        """Guruhning o'z domeni. Bo'sh guruhda — bo'sh ro'yxat."""
        self.ensure_one()
        shart = []
        if self.categ_ids:
            shart.append(('categ_id', 'child_of', self.categ_ids.ids))
        if self.product_ids:
            shart.append(('id', 'in', self.product_ids.ids))
        if not shart:
            return []
        if len(shart) == 2:
            return ['|'] + shart
        return shart

    def action_open_products(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': 'product.product',
            'view_mode': 'list,form',
            'domain': self._domain(),
        }


class AgroNovaMahsulotFiltrMixin(models.AbstractModel):
    """Hujjat modeliga mahsulot filtrini beradi.

    Foydalanish: modelda hisoblanadigan `Binary` maydon ochiladi va
    ko'rinishda `domain="<maydon>"` deb yoziladi.

        product_domain = fields.Binary(compute='_compute_product_domain')

        @api.depends_context('company')
        def _compute_product_domain(self):
            for rec in self:
                rec.product_domain = rec._agronova_mahsulot_domain(
                    'tuxum', [('is_storable', '=', True)])
    """
    _name = 'agronova.mahsulot.filtr.mixin'
    _description = "AgroNova — mahsulot filtri"

    @api.model
    def _agronova_mahsulot_domain(self, kod, qoshimcha=None):
        """`kod` guruhiga tushadigan mahsulotlar domeni."""
        guruh = self.env['agronova.mahsulot.guruh'].sudo().search(
            [('kod', '=', kod)], limit=1)
        domain = list(qoshimcha or [])
        return domain + (guruh._domain() if guruh else [])
