# -*- coding: utf-8 -*-
from odoo import _, models
from odoo.exceptions import UserError

# Har qanday hujjatda o'zgarishi mumkin bo'lgan texnik maydonlar.
TEXNIK = {'message_main_attachment_id', 'activity_ids', 'message_follower_ids'}


class AgroNovaYemSmenaQulfMixin(models.AbstractModel):
    """Tasdiqlangan smenaga yangi hujjat qo'shilmaydi va mavjudining
    miqdorlari o'zgarmaydi.

    Smena hisobotidagi raqamlar shu hujjatlardan yig'iladi — ular o'zgarsa
    tasdiqlangan hisobot ham jimgina o'zgarib qolardi (TZ 3.5). Lekin ish
    jarayoni davom etadi: smena yopilgandan keyin ham boshliq yo'qotishni
    tasdiqlaydi yoki rad etadi. Shuning uchun har model `_smena_qulf_erkin`
    da raqamga ta'sir qilmaydigan maydonlarni (holat, tasdiqlagan, sabab)
    sanab beradi.
    """
    _name = 'agronova.yem.smena.qulf.mixin'
    _description = "Smena qulfi"
    _smena_qulf_erkin = set()

    def _smena_qulf_tekshir(self, vals=None):
        if self.env.context.get('agronova_smena_ruxsat') or self.env.su:
            return
        if vals is not None and set(vals) <= (self._smena_qulf_erkin | TEXNIK):
            return
        for r in self:
            smena = r['smena_id'] if 'smena_id' in r._fields else False
            if smena and smena.state == 'tasdiqlangan':
                raise UserError(_(
                    "«%s» smena hisoboti tasdiqlangan — unga bog'liq hujjatni qo'shib yoki "
                    "o'zgartirib bo'lmaydi.", smena.name))

    def write(self, vals):
        self._smena_qulf_tekshir(vals)
        res = super().write(vals)
        if 'smena_id' in vals:
            self._smena_qulf_tekshir(vals)
        return res

    def unlink(self):
        self._smena_qulf_tekshir()
        return super().unlink()
