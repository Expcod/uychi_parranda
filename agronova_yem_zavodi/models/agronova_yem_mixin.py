# -*- coding: utf-8 -*-
from odoo import _, models
from odoo.exceptions import UserError


class AgroNovaYemSmenaQulfMixin(models.AbstractModel):
    """Tasdiqlangan smenaga yangi hujjat qo'shilmaydi va mavjudi o'zgarmaydi.

    Smena hisobotidagi raqamlar shu hujjatlardan yig'iladi — ular
    o'zgarsa tasdiqlangan hisobot ham jimgina o'zgarib qolardi (TZ 3.5).
    """
    _name = 'agronova.yem.smena.qulf.mixin'
    _description = "Smena qulfi"

    def _smena_qulf_tekshir(self):
        if self.env.context.get('agronova_smena_ruxsat') or self.env.su:
            return
        for r in self:
            smena = r['smena_id'] if 'smena_id' in r._fields else False
            if smena and smena.state == 'tasdiqlangan':
                raise UserError(_(
                    "«%s» smena hisoboti tasdiqlangan — unga bog'liq hujjatni qo'shib yoki "
                    "o'zgartirib bo'lmaydi.", smena.name))

    def write(self, vals):
        self._smena_qulf_tekshir()
        res = super().write(vals)
        if 'smena_id' in vals:
            self._smena_qulf_tekshir()
        return res

    def unlink(self):
        self._smena_qulf_tekshir()
        return super().unlink()
