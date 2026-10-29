# -*- coding: utf-8 -*-
"""Savdo nuqtasi sozlamalari.

Har bir do'kon o'z kassasiga (`agronova.kassa`) bog'lanadi — smena
yopilganda naqd tushum o'sha kassaning kitobiga tushadi. Qolgan uchta
bayroq TZ M08 dagi qoidalarni yoqib-o'chiradi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PosConfig(models.Model):
    _inherit = 'pos.config'

    agronova_kassa_id = fields.Many2one(
        'agronova.kassa', string="Kassa kitobi",
        help="Smena yopilganda naqd tushum shu kassaga kirim bo'lib "
             "yoziladi. Bo'sh qoldirilsa POS naqdi kassa kitobiga "
             "tushmaydi va kassir kechqurun pulni sanaganda hisob "
             "chiqmaydi.",
    )
    agronova_fefo = fields.Boolean(
        string="Lotni FEFO bo'yicha avtomat tanlash", default=True,
        help="Go'sht lot va yaroqlilik muddati bilan yuritiladi, lekin "
             "kassir har tarozi urishida lot terib o'tira olmaydi. "
             "Yoqilganda tizim sotuvdan keyin muddati eng oldin "
             "tugaydigan partiyani o'zi biriktiradi (TZ M01 FEFO, "
             "M06 lot+muddat).",
    )
    agronova_tannarx_nazorati = fields.Boolean(
        string="Tannarxdan past sotuvni taqiqlash", default=True,
        help="TZ M08 talabi. Tannarxi kiritilmagan (0) mahsulot "
             "tekshirilmaydi — aks holda butun savdo to'xtab qolardi.",
    )
    agronova_kredit_nazorati = fields.Boolean(
        string="Kredit limitini tekshirish", default=True,
        help="«Keyin to'lash» usulida mijozning jami qarzi kartochkasidagi "
             "kredit limitidan oshsa sotuv bloklanadi (TZ M08).",
    )

    @api.constrains('agronova_kassa_id', 'company_id')
    def _check_agronova_kassa(self):
        for config in self:
            kassa = config.agronova_kassa_id
            if not kassa:
                continue
            ruxsat = config.company_id.parent_ids or config.company_id
            if kassa.company_id not in ruxsat:
                raise ValidationError(_(
                    "«%(kassa)s» kassasi «%(kk)s» korxonasiga tegishli, "
                    "«%(pos)s» savdo nuqtasi esa «%(pk)s» da.",
                    kassa=kassa.name, kk=kassa.company_id.name,
                    pos=config.name, pk=config.company_id.name))

    def _agronova_naqd_usullari(self):
        """Shu POS ning naqd to'lov usullari."""
        self.ensure_one()
        return self.payment_method_ids.filtered(
            lambda m: m.journal_id and m.journal_id.type == 'cash')
