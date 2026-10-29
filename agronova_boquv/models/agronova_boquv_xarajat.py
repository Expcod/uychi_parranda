# -*- coding: utf-8 -*-
"""Boquv xarajat hujjati — `agronova.xarajat.mixin` merosi.

Umumiy mexanizm (naqd/qarz, foto majburiy, tahrirlash muddati 12/24/36
soat, storno) `agronova_base` da yozilgan. Bu yerda faqat **taqsimlash
maqsadi** aniqlanadi.

Yakuniy TZ dagi taqsimlash matritsasi ikki o'lchovli — nafaqat *baza*,
balki *qaysi binolarga* ham muhim:

| Xarajat                  | Baza          | Qaysi binolarga        |
|--------------------------|---------------|------------------------|
| Ijara, elektr, isitish   | m²            | aktiv + dizinfeksiya   |
| Oshpaz, oziq-ovqat       | m²            | aktiv + dizinfeksiya   |
| Filial xodimlari ish haqi| m²            | aktiv + dizinfeksiya   |
| **Veterinar ish haqi**   | teng          | **faqat aktiv**        |
| Atrof dorisi             | teng          | aktiv + dizinfeksiya   |
| Bino operatori ish haqi  | to'g'ridan    | biriktirilgan bino     |
| Maqsadli dori            | to'g'ridan    | aniq bino              |

Sabab: dizinfeksiyadagi binoda jo'ja yo'q, shuning uchun veterinar mehnati
u yerga tushmasligi kerak. «No aktiv» binoga esa hech qanday xarajat
kelmaydi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Xarajat qamrovi — qaysi holatdagi binolar ishtirok etadi.
QAMROV = [
    ('aktiv_dizinfeksiya', "Aktiv va dizinfeksiyadagi binolar"),
    ('faqat_aktiv', "Faqat aktiv binolar"),
    ('tanlangan', "Faqat tanlangan binolar"),
]


class AgroNovaBoquvXarajat(models.Model):
    _name = 'agronova.boquv.xarajat'
    _description = "Boquv — xarajat hujjati"
    _inherit = ['agronova.xarajat.mixin']

    filial_id = fields.Many2one(
        'agronova.boquv.filial', string="Filial", tracking=True,
        ondelete='restrict', index=True,
        help="Bo'sh qoldirilsa xarajat barcha filiallarga taqsimlanadi.")
    qamrov = fields.Selection(
        QAMROV, string="Qamrov", default='aktiv_dizinfeksiya', required=True,
        tracking=True,
        help="Xarajat qaysi holatdagi binolarga tushadi. Veterinar mehnati "
             "kabi xarajatlar faqat aktiv binoga tushadi — dizinfeksiyadagi "
             "binoda jo'ja yo'q. «No aktiv» binoga hech narsa tushmaydi.")
    bino_ids = fields.Many2many(
        'agronova.boquv.bino', string="Binolar",
        help="«Faqat tanlangan binolar» qamrovida to'ldiriladi.")
    partiya_id = fields.Many2one(
        'agronova.boquv.partiya', string="Partiya", tracking=True,
        ondelete='restrict', index=True,
        domain="[('holat', '=', 'active')]",
        help="To'g'ridan-to'g'ri bitta partiyaga yoziladigan xarajat "
             "(maqsadli dori, operator ish haqi).")

    # ---------------------------------------------------------- taqsimlash
    def _boquv_binolar(self):
        """Xarajat tushadigan binolar ro'yxati."""
        self.ensure_one()
        Bino = self.env['agronova.boquv.bino']
        if self.qamrov == 'tanlangan':
            binolar = self.bino_ids
        else:
            domain = []
            if self.filial_id:
                domain.append(('filial_id', '=', self.filial_id.id))
            if self.qamrov == 'faqat_aktiv':
                domain.append(('holat', '=', 'aktiv'))
            else:
                domain.append(('holat', 'in', ('aktiv', 'dizinfeksiya')))
            binolar = Bino.search(domain)
        # «No aktiv» binoga hech qanday xarajat kelmaydi (yakuniy TZ).
        return binolar.filtered(lambda b: b.holat != 'no_aktiv')

    def _agronova_taqsimot_targets(self):
        """Xarajat taqsimlanadigan obyektlar.

        Partiya ko'rsatilgan bo'lsa — to'g'ridan-to'g'ri unga. Aks holda
        binolar bo'yicha: har binoning faol partiyalariga tushadi, faol
        partiya bo'lmasa (dizinfeksiya davri) binoning o'ziga.
        """
        self.ensure_one()
        if self.partiya_id:
            p = self.partiya_id
            return [{
                'record': p,
                'maydoni': p.bino_id.maydoni,
                'bosh_soni': p.joriy_son,
            }]

        targets = []
        for bino in self._boquv_binolar():
            aktiv = bino.aktiv_partiya_ids
            if aktiv:
                # Bino maydoni faol partiyalar orasida bosh soniga qarab
                # bo'linadi — bir binoda bir necha partiya bo'lishi mumkin.
                jami_bosh = sum(aktiv.mapped('joriy_son')) or len(aktiv)
                for p in aktiv:
                    ulush = ((p.joriy_son / jami_bosh) if jami_bosh
                             else 1.0 / len(aktiv))
                    targets.append({
                        'record': p,
                        'maydoni': bino.maydoni * ulush,
                        'bosh_soni': p.joriy_son,
                    })
            else:
                # Dizinfeksiya davri — xarajat binoning o'ziga yig'iladi va
                # keyingi partiya ochilganda unga o'tkaziladi.
                targets.append({
                    'record': bino,
                    'maydoni': bino.maydoni,
                    'bosh_soni': 0,
                })
        return targets

    @api.onchange('qamrov')
    def _onchange_qamrov(self):
        if self.qamrov != 'tanlangan':
            self.bino_ids = [(5, 0, 0)]

    def action_tasdiqlash(self):
        for rec in self:
            if not rec._boquv_binolar() and not rec.partiya_id:
                raise UserError(_(
                    "«%s» xarajati uchun bino topilmadi. Filial, qamrov yoki "
                    "partiyani tekshiring — «No aktiv» binolarga xarajat "
                    "tushmaydi.", rec.display_name))
        return super().action_tasdiqlash()
