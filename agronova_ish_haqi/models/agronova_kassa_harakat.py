# -*- coding: utf-8 -*-
"""Kassadan oylik berilishi — xodim balansiga avtomat tushadi.

Muammo: kassada «Ish haqi / avans» moddasi bilan pul berilsa,
buxgalteriya provodkasi to'g'ri yozilardi (Dt 6710 / Kt kassa), lekin
xodimning ish haqi balansi o'zgarmasdi — kassir alohida, qo'lda
«Berildi» harakatini kiritishi kerak edi. Ikki joyga yozish esa albatta
bir kun unutiladi va balans yolg'on ko'rsata boshlaydi.

Endi bitta yozuv yetarli: kassada order tasdiqlansa, xodimning ish haqi
balansidan ham avtomat chiqadi; storno qilinsa — qaytadi.

Moddaning o'zi «oylik moddasi»mi degan savolga javob sozlamadagi
«Xodimga qarz hisobi» (odatda 6710) bilan beriladi — modda o'sha
hisobga yozadigan bo'lsa, demak bu ish haqi to'lovi. Shunday qilib
yangi modda qo'shilsa ham kod o'zgartirilmaydi.
"""
from odoo import _, fields, models


class AgroNovaKassaHarakat(models.Model):
    _inherit = 'agronova.kassa.harakat'

    agronova_ish_haqi_harakat_id = fields.Many2one(
        'agronova.ish_haqi.harakat', string="Ish haqi harakati", readonly=True,
        copy=False, ondelete='set null',
        help="Kassadan oylik berilganda avtomat yaratilgan balans yozuvi.")

    def _agronova_ish_haqi_tolovimi(self):
        """Shu order xodimga oylik/avans berishmi?"""
        self.ensure_one()
        if self.direction != 'out' or not self.employee_id:
            return False
        hisob = self.modda_id.account_id
        if not hisob:
            return False
        rid = self.env['ir.config_parameter'].sudo().get_param(
            'agronova_ish_haqi.account_qarz')
        if rid:
            return hisob.id == int(rid)
        # Sozlama hali qo'yilmagan bo'lsa — hisob kodiga qarab.
        return (hisob.code or '').startswith('6710')

    def _tasdiqlash(self):
        res = super()._tasdiqlash()
        if self._agronova_ish_haqi_tolovimi() and not self.agronova_ish_haqi_harakat_id:
            harakat = self.env['agronova.ish_haqi.harakat'].sudo().create({
                'employee_id': self.employee_id.id,
                'sana': self.date_day,
                'tur': 'berildi',
                'summa': abs(self.amount),
                'izoh': _("Kassadan: %s", self.name or ''),
                'kassa_harakat_id': self.id,
            })
            self.sudo().agronova_ish_haqi_harakat_id = harakat.id
        return res

    def _provodka_storno(self):
        res = super()._provodka_storno()
        # Storno — pul qaytdi, demak balansdan chiqarilgan summa ham
        # qaytariladi. Harakat o'chiriladi, chunki u shu orderning
        # aksi bo'lib, o'zi mustaqil ma'noga ega emas.
        if self.agronova_ish_haqi_harakat_id:
            self.agronova_ish_haqi_harakat_id.sudo().unlink()
        return res
