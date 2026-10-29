# -*- coding: utf-8 -*-
"""Analitik qatorga bitta belgi qo'shiladi — tannarx bazasiga kiradimi.

Nima uchun kerak. Partiyaning birlik tannarxi shunday hisoblanadi:

    1 birlik tannarxi = partiyaning jami xarajati / ishlab chiqarilgan miqdor

Mahsulot ichki bo'limga berilganda (tuxum → Inkubatsiya, don → Yem zavodi)
boshqaruv hisobida ikki yozuv kerak: **daromad** va sotilgan mahsulotning
**tannarx chiqimi**. Ammo tannarx chiqimi xuddi shu analitik hisobga
tushganda, u birlik tannarxini oshirib yuboradi — keyingi sotuvda tannarx
yana oshadi, ya'ni o'z-o'zini ovqatlantiradigan halqa paydo bo'ladi.

Sinovda aniq ko'rindi: 1 kg tannarxi 370 so'm edi, ichki berishdan keyin
601,25 so'mga chiqib ketdi — hech qanday yangi xarajat qilinmagan holda.

Shu sababli tannarx chiqimi qatorlari `agronova_tannarx_bazasi = False` bilan
yoziladi va birlik tannarxi hisobiga kirmaydi. Foyda-zarar hisobida esa
ular to'liq qatnashadi — u yerda ular o'rinli.
"""
from odoo import fields, models


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    # Xarajat tarkibini kategoriya kesimida ko'rsatish uchun. Qator nomida
    # kategoriya matn sifatida bor, lekin hisobotda guruhlash uchun bog'lanish
    # kerak — matn bo'yicha guruhlash nomi o'zgarsa buziladi.
    agronova_kategoriya_id = fields.Many2one(
        'agronova.xarajat.kategoriya', string="Xarajat kategoriyasi", index=True,
        ondelete='set null',
        help="Xarajat hujjatidan ko'chadi. Foyda-zarar hisobotida xarajat "
             "tarkibi shu kesimda ko'rsatiladi.")

    agronova_tannarx_bazasi = fields.Boolean(
        "Tannarx bazasiga kiradi", default=True, index=True,
        help="Belgilanmagan qatorlar birlik tannarxini hisoblashda "
             "e'tiborga olinmaydi (masalan sotilgan mahsulotning tannarx "
             "chiqimi). Foyda-zarar hisobida esa qatnashadi.")

    # Analitik reja ustunlari dinamik yaratiladi (`x_plan9_id` — «Yer
    # maydoni», `x_plan13_id` — «Inkubatsiya partiyasi» va h.k.). Standart
    # ro'yxatda ularning HAMMASI ustun bo'lib chiqadi va bo'sh joy egallab
    # turadi: bitta qator faqat bitta rejaga tegishli bo'ladi. Shu maydon
    # qaysi rejaga tushganini bitta ustunda ko'rsatadi.
    agronova_obyekt = fields.Char(
        "Obyekt", compute='_compute_agronova_obyekt',
        help="Qator qaysi analitik obyektga (partiya, yer, sex, bino) "
             "tushgani.")

    def _agronova_reja_ustunlari(self):
        """Analitik reja ustunlari (`account_id`, `x_plan9_id`, ...).

        Odoo ning `_get_all_plans()` iga tayanilmaydi: u
        `analytic.project_plan` sozlamasi qo'yilmagan bazada xato beradi
        (sinov bazalarida shunday). Ustunlarni turi bo'yicha topamiz —
        bu har qanday bazada ishlaydi.
        """
        # Faqat saqlanadigan ustunlar: `auto_account_id` — hisoblanadigan
        # oyna maydoni, u `account_id` ni takrorlab «Obyekt · Obyekt»
        # qilib qo'yardi.
        return sorted(
            nom for nom, f in self._fields.items()
            if f.type == 'many2one'
            and f.comodel_name == 'account.analytic.account'
            and f.store)

    def _compute_agronova_obyekt(self):
        ustunlar = self._agronova_reja_ustunlari()
        for qator in self:
            nomlar = []
            for u in ustunlar:
                hisob = qator[u]
                if hisob:
                    nomlar.append(hisob.display_name)
            qator.agronova_obyekt = " · ".join(nomlar)
