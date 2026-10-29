# -*- coding: utf-8 -*-
"""Normativ ko'rsatkichlar bazasi (B01).

Reja-fakt taqqoslash va normadan chetlanish ogohlantirishi shu jadvaldan
oziqlanadi. Normativ zot va yosh (hafta) oralig'i kesimida saqlanadi —
tuxum berish % podaning yoshiga qarab keskin o'zgaradi, shuning uchun
bitta global raqam yetarli emas.

Aniq qiymatlar buyurtmachidan hali olinmagan (9-bo'lim, 1–2-band), shuning
uchun `data/agronova_ona_tovuq_normativ_data.xml` dagi qatorlar **taxminiy** —
sanoat o'rtachasi. Buyurtmachi tasdiqlagach shu jadval to'g'rilanadi,
kodga tegilmaydi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Normativ topilmasa ishlatiladigan global standart qiymatlar.
# TODO: buyurtmachi tasdiqlashi kerak (9-bo'lim 1, 2, 3-band).
DEFAULT_NORMA = {
    'tuxum_berish_foiz': 85.0,
    'uruglanish_foiz': 92.0,
    'nobud_foiz_haftalik': 0.35,
    'brak_foiz_haftalik': 0.20,
    'xoroz_tovuq_nisbati': 0.10,      # 1 : 10
    'eskirish_chegara_foiz': 65.0,
    'yem_bosh_kunlik_gr': 115.0,
}


class AgroNovaOnaTovuqNormativ(models.Model):
    _name = 'agronova.ona_tovuq.normativ'
    _description = "Ona tovuq normativi"
    _order = 'zot_id, hafta_dan'

    name = fields.Char("Nomi", compute='_compute_name', store=True)
    zot_id = fields.Many2one(
        'agronova.ona_tovuq.zot', string="Zot", ondelete='cascade', index=True,
        help="Bo'sh qoldirilsa — barcha zotlar uchun umumiy normativ.")
    davr = fields.Selection(
        [('ostirish', "O'stirish davri"), ('tuxum', "Tuxum berish davri")],
        string="Davr", required=True, default='tuxum')
    hafta_dan = fields.Integer("Haftadan", default=0)
    hafta_gacha = fields.Integer("Haftagacha", default=999)

    tuxum_berish_foiz = fields.Float(
        "Tuxum berish normasi (%)", default=DEFAULT_NORMA['tuxum_berish_foiz'])
    uruglanish_foiz = fields.Float(
        "Urug'lanish normasi (%)", default=DEFAULT_NORMA['uruglanish_foiz'])
    nobud_foiz_haftalik = fields.Float(
        "Haftalik nobudgarchilik normasi (%)",
        default=DEFAULT_NORMA['nobud_foiz_haftalik'])
    brak_foiz_haftalik = fields.Float(
        "Haftalik brak normasi (%)", default=DEFAULT_NORMA['brak_foiz_haftalik'])
    xoroz_tovuq_nisbati = fields.Float(
        "Xo'roz/tovuq normasi", default=DEFAULT_NORMA['xoroz_tovuq_nisbati'],
        digits=(12, 4),
        help="Masalan 0,10 — bu 1 xo'roz : 10 tovuq.")
    yem_bosh_kunlik_gr = fields.Float(
        "Kunlik yem normasi (gr/bosh)",
        default=DEFAULT_NORMA['yem_bosh_kunlik_gr'])
    active = fields.Boolean("Faol", default=True)

    @api.depends('zot_id', 'davr', 'hafta_dan', 'hafta_gacha')
    def _compute_name(self):
        for rec in self:
            zot = rec.zot_id.name or _("Umumiy")
            rec.name = _("%(zot)s · %(dan)s–%(gacha)s hafta",
                         zot=zot, dan=rec.hafta_dan, gacha=rec.hafta_gacha)

    @api.constrains('hafta_dan', 'hafta_gacha')
    def _check_hafta(self):
        for rec in self:
            if rec.hafta_dan > rec.hafta_gacha:
                raise ValidationError(_(
                    "Normativda «haftadan» qiymati «haftagacha» dan katta bo'lmasin."))

    @api.model
    def _topish(self, zot=None, hafta=0, davr='tuxum'):
        """Zot va yosh bo'yicha eng mos normativni qaytaradi.

        Avval zotga xos normativ qidiriladi, topilmasa umumiy (zotsiz)
        normativ. U ham bo'lmasa — bo'sh recordset (chaqiruvchi
        DEFAULT_NORMA ga tushadi).
        """
        base = [('davr', '=', davr),
                ('hafta_dan', '<=', hafta),
                ('hafta_gacha', '>=', hafta)]
        if zot:
            norma = self.search([('zot_id', '=', zot.id)] + base, limit=1)
            if norma:
                return norma
        return self.search([('zot_id', '=', False)] + base, limit=1)

    @api.model
    def qiymat(self, field, zot=None, hafta=0, davr='tuxum'):
        """Bitta normativ ko'rsatkichni qaytaradi, topilmasa standart qiymat."""
        norma = self._topish(zot=zot, hafta=hafta, davr=davr)
        if norma and norma[field]:
            return norma[field]
        return DEFAULT_NORMA.get(field, 0.0)
