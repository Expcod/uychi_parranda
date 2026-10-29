# -*- coding: utf-8 -*-
"""Normativ ko'rsatkichlar — reja-fakt taqqoslash bazasi.

Umumiy TZ M05 №13: «Normativ qiymatlar bazasi va reja-fakt taqqoslash
(normativ FCR, normativ nobudgarchilik)», №14: «Og'ish bo'lganda
ogohlantirish».

Normativ **yosh (kun) oralig'i** kesimida saqlanadi — broyler boqishda
yem sarfi va o'sish sur'ati yoshga qarab keskin o'zgaradi, shuning uchun
bitta global raqam yetarli emas.

**Diqqat:** aniq qiymatlar buyurtmachidan hali olinmagan. Umumiy TZ §10
«Buyurtmachi zimmasidagi majburiyatlar» 4-band: «Normativ ko'rsatkichlarni
berish: FCR normasi, nobudgarchilik normasi, chiqim foizi — 3-bosqich».

Shuning uchun `data/agronova_boquv_normativ_data.xml` **bo'sh** qoldirilgan va
`DEFAULT_NORMA` ham bo'sh. Normativ topilmasa reja-fakt taqqoslash
o'tkazilmaydi, ogohlantirish chiqmaydi — noto'g'ri raqamga tayanib signal
berishdan ko'ra jim turgani yaxshi. Buyurtmachi qiymatlarni bergach shu
jadval to'ldiriladi, **kodga tegilmaydi**.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Buyurtmachi tasdiqlagach to'ldiriladi (umumiy TZ §10, 4-band).
# Bo'sh bo'lgani uchun `qiymat()` 0.0 qaytaradi va chaqiruvchi kod
# reja-fakt taqqoslashni o'tkazib yuboradi.
DEFAULT_NORMA = {}


class AgroNovaBoquvNormativ(models.Model):
    _name = 'agronova.boquv.normativ'
    _description = "Boquv normativi"
    _order = 'yosh_kun_dan, id'

    name = fields.Char("Nomi", compute='_compute_name', store=True)
    yosh_kun_dan = fields.Integer("Yoshdan (kun)", default=0)
    yosh_kun_gacha = fields.Integer("Yoshgacha (kun)", default=999)

    # --- asosiy ko'rsatkichlar (TZ M05 №12, №13)
    fcr_norma = fields.Float(
        "FCR normasi", digits=(12, 3),
        help="1 kg tirik vazn olish uchun sarflanishi kerak bo'lgan yem (kg). "
             "Namunaviy hisobda 1,60.")
    nobud_foiz_norma = fields.Float(
        "Nobudgarchilik normasi (%)", digits=(12, 2),
        help="Partiya davri uchun jami nobudgarchilik normasi. "
             "Namunaviy hisobda 3,5%.")
    ortacha_vazn_norma = fields.Float(
        "O'rtacha vazn normasi (kg)", digits='Product Unit',
        help="Shu yoshda kutilayotgan o'rtacha bir bosh vazni.")
    kunlik_osish_norma = fields.Float(
        "Kunlik o'sish normasi (gr)", digits=(12, 2),
        help="Bir boshning bir kunlik o'rtacha vazn qo'shishi.")
    yem_bosh_kunlik_gr = fields.Float(
        "Kunlik yem normasi (gr/bosh)", digits=(12, 2),
        help="Norma rasxod — mijoz alohida so'ragan (1C da yo'q edi).")
    harorat_min = fields.Float(
        "Harorat — pastki me'yor (°C)", digits=(12, 1),
        help="Obxodda kiritilgan harorat shu chegaradan past bo'lsa "
             "ogohlantirish chiqadi (TZ 11-band).")
    harorat_max = fields.Float(
        "Harorat — yuqori me'yor (°C)", digits=(12, 1))

    active = fields.Boolean("Faol", default=True)
    izoh = fields.Text("Izoh")

    _yosh_oraliq = models.Constraint(
        'CHECK (yosh_kun_dan <= yosh_kun_gacha)',
        "Normativda «yoshdan» qiymati «yoshgacha» dan katta bo'lmasin.")

    @api.depends('yosh_kun_dan', 'yosh_kun_gacha')
    def _compute_name(self):
        for rec in self:
            rec.name = _("%(dan)s–%(gacha)s kun",
                         dan=rec.yosh_kun_dan, gacha=rec.yosh_kun_gacha)

    @api.constrains('yosh_kun_dan', 'yosh_kun_gacha')
    def _check_oraliq(self):
        """Yosh oraliqlari kesishmasin — aks holda qaysi norma amal qilishi
        noaniq bo'lib qoladi."""
        for rec in self:
            kesishgan = self.search([
                ('id', '!=', rec.id),
                ('yosh_kun_dan', '<=', rec.yosh_kun_gacha),
                ('yosh_kun_gacha', '>=', rec.yosh_kun_dan),
            ], limit=1)
            if kesishgan:
                raise ValidationError(_(
                    "«%(yangi)s» normativi «%(band)s» bilan kesishadi. "
                    "Yosh oraliqlari bir-birining ustiga tushmasligi kerak.",
                    yangi=rec.name, band=kesishgan.name))

    # ------------------------------------------------------------- qidiruv
    @api.model
    def _topish(self, yosh_kun=0):
        """Yoshga mos normativni qaytaradi, topilmasa bo'sh recordset."""
        return self.search([
            ('yosh_kun_dan', '<=', yosh_kun),
            ('yosh_kun_gacha', '>=', yosh_kun),
        ], limit=1)

    @api.model
    def qiymat(self, field, yosh_kun=0):
        """Bitta normativ ko'rsatkichni qaytaradi.

        Normativ kiritilmagan bo'lsa **0.0** qaytadi — chaqiruvchi kod
        shuni tekshirib, reja-fakt taqqoslashni o'tkazib yuboradi.
        """
        norma = self._topish(yosh_kun=yosh_kun)
        if norma and norma[field]:
            return norma[field]
        return DEFAULT_NORMA.get(field, 0.0)

    # -------------------------------------------------- qayta hisoblash
    def _qayta_hisoblash(self):
        """Faol partiyalarning reja-fakt maydonlarini yangilaydi.

        `agronova.boquv.partiya.ogish_bormi` saqlanadigan compute maydon, lekin
        uning bog'liqlik ro'yxatida shu model yo'q — Odoo boshqa modeldagi
        o'zgarishni avtomat kuzata olmaydi. Shuning uchun normativ
        yaratilganda/o'zgarganda partiyalarni o'zimiz qayta hisoblatamiz.
        """
        partiyalar = self.env['agronova.boquv.partiya'].search([
            ('holat', '=', 'active'),
        ])
        if partiyalar:
            partiyalar._compute_norma()
        return True

    @api.model_create_multi
    def create(self, vals_list):
        normativlar = super().create(vals_list)
        normativlar._qayta_hisoblash()
        return normativlar

    def write(self, vals):
        res = super().write(vals)
        self._qayta_hisoblash()
        return res

    def unlink(self):
        res = super().unlink()
        self.env['agronova.boquv.normativ']._qayta_hisoblash()
        return res
