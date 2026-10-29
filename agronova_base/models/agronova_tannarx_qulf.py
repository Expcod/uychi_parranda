# -*- coding: utf-8 -*-
"""Tannarx maydonini qulflash — B12 ning ikkinchi yarmi.

TZ talabi qat'iy: **tannarx maydoni barcha rollar uchun readonly — hech kim
qo'lda kiritmaydi**. Faqat `readonly=True` yozish yetarli emas: u bor-yo'g'i
ekranda maydonni o'chiradi. XML-RPC, ma'lumot importi yoki dasturchi
konsolidan yozib yuborsa bo'ladi — ya'ni tannarxni «to'g'rilab qo'yish»
yo'li ochiq qoladi. Loyihada esa butun ishonch shu raqamga tayanadi.

Shu mixin maydonni **ma'lumotlar bazasi darajasida** himoya qiladi: qiymatni
faqat kontekstda `agronova_tannarx_yozish=True` bo'lganda yozib bo'ladi, uni esa
tannarxni hisoblaydigan kodning o'zi qo'yadi.

Ishlatilishi::

    class Partiya(models.Model):
        _inherit = ['agronova.tannarx.qulf.mixin']
        _agronova_tannarx_fields = ('tannarx_1_bosh',)

Va tannarxni hisoblagan joyda::

    p._tannarx_yozish().tannarx_1_bosh = xarajat / p.joriy_son
"""
from odoo import _, api, models
from odoo.exceptions import UserError

TANNARX_KONTEKST = 'agronova_tannarx_yozish'


class AgroNovaTannarxQulfMixin(models.AbstractModel):
    _name = 'agronova.tannarx.qulf.mixin'
    _description = "AgroNova — tannarx maydonini qulflash"

    # Meros oluvchi model to'ldiradi
    _agronova_tannarx_fields = ()

    def _tannarx_yozish(self):
        """Tannarx maydonini yozishga ruxsat berilgan nusxa."""
        return self.with_context(**{TANNARX_KONTEKST: True})

    def _agronova_tekshir_tannarx(self, vals):
        if self.env.context.get(TANNARX_KONTEKST):
            return
        qulf = set(self._agronova_tannarx_fields) & set(vals)
        if not qulf:
            return
        nomlar = ", ".join(
            "«%s»" % self._fields[f].get_description(self.env)['string']
            for f in sorted(qulf))
        raise UserError(_(
            "%(maydon)s — tannarx maydoni, qo'lda kiritilmaydi. U xarajat "
            "va miqdor yozuvlaridan avtomat hisoblanadi. Tannarx noto'g'ri "
            "chiqayotgan bo'lsa, sababi xarajat hujjatlarida — o'shalarni "
            "to'g'rilang.", maydon=nomlar))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._agronova_tekshir_tannarx(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._agronova_tekshir_tannarx(vals)
        return super().write(vals)
