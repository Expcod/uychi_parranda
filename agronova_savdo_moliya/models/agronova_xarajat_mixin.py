# -*- coding: utf-8 -*-
"""Xarajat mixin'ini depozit bilan kengaytirish.

`agronova_base` depozit modelini bilmaydi (u shu modulda), shuning uchun
naqd to'lov manbasi shu yerda qo'shiladi. Mixin kengaytirilgani uchun
undan meros olgan barcha bo'lim modullari (Ona Tovuq, keyin Boquv,
So'yish) `depozit_id` ni avtomat oladi — har birida qaytadan yozilmaydi.
"""
from odoo import _, fields, models
from odoo.exceptions import ValidationError


class AgroNovaXarajatMixin(models.AbstractModel):
    _inherit = 'agronova.xarajat.mixin'

    depozit_id = fields.Many2one(
        'agronova.depozit', string="Depozit",
        tracking=True, ondelete='restrict',
        help="Naqd to'lovda pul shu depozitdan chiqadi. Naqdda majburiy.")
    depozit_harakat_id = fields.Many2one(
        'agronova.depozit.harakat', string="Depozit chiqimi",
        readonly=True, copy=False)

    def _check_naqd_manba(self):
        for rec in self:
            if rec.tolov_turi == 'naqd' and not rec.depozit_id:
                raise ValidationError(_(
                    "«%s» naqd xarajatida depozit tanlanishi shart — pul "
                    "qaysi mas'ul xodimning qo'lidan chiqqani ko'rinishi kerak.",
                    rec.nom or ''))
        return True

    def _agronova_qulfsiz_maydonlar(self):
        # Depozit chiqimi tasdiqlashdan KEYIN yoziladi, ya'ni hujjat
        # allaqachon «tasdiqlangan». Shu maydon qulfdan ozod bo'lmasa
        # tasdiqlash o'z-o'zini bloklaydi.
        return super()._agronova_qulfsiz_maydonlar() | {'depozit_harakat_id'}

    def _agronova_tolov_amalga_oshirish(self):
        """Tasdiqlanganda depozitdan chiqim yozadi."""
        for rec in self:
            if rec.tolov_turi != 'naqd' or not rec.depozit_id:
                continue
            rec.depozit_harakat_id = rec.depozit_id._chiqim_yozish(
                summa=rec.summa,
                izoh=_("%(kat)s: %(nom)s", kat=rec.kategoriya_id.name, nom=rec.nom),
                manba=rec,
                sana=rec.sana,
            )
        return True

    def _agronova_tolov_storno(self):
        for rec in self:
            if rec.depozit_harakat_id.holat == 'tasdiqlangan':
                rec.depozit_harakat_id.action_storno()
        return True
