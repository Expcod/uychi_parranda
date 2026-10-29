# -*- coding: utf-8 -*-
{
    'name': "AgroNova — Qishloq xo'jaligi",
    'summary': "Yer maydonlari, ekin partiyalari, hosil tannarxi va sotuvi",
    'description': """
AgroNova ERP — Qishloq xo'jaligi bo'limi moduli.

Zanjir: **yer → ekin → partiya → xarajat → hosil → tannarx → sotuv → foyda**.

* **Yer maydoni** — doimiy obyekt, gektari, o'z analitik hisobi va ombor
  lokatsiyasi bilan. Ustida partiyalar ketma-ket almashadi, tarixi saqlanadi.
* **Ekin partiyasi** — bitta yetishtirish sikli. Urug', o'g'it, yoqilg'i,
  ish haqi va boshqa xarajatlar shunga yig'iladi.
* **Dalada bajarilgan ish** — ekish, o'g'itlash, sug'orish, dorilash, o'rim.
  Tasdiqlanganda resurs ombordan hisobdan chiqadi, FIFO qiymati partiya
  tannarxiga tushadi. Kunlik jurnal yo'q — ekinda har kun yozadigan narsa
  bo'lmaydi.
* **Hosil kirimi** — omborga lot bilan kiradi, qiymati partiya tannarxidan.
* **Tannarx** = partiyaning jami xarajati / olingan hosil (kg). Qo'lda
  kiritilmaydi.
* **Xarajat taqsimoti** — sug'orish, elektr, texnika **gektar bo'yicha**
  yerlar orasida bo'linadi.
* **Ichki berish** (Yem zavodiga) — QQS fakturasi yo'q, lekin partiyaga
  daromad va tannarx chiqimi yoziladi, shunda rentabellik to'g'ri chiqadi.

Xarajat hujjati va analitik hisob mexanizmi `agronova_base` dan meros olinadi —
Ona Tovuq bilan bir xil uslub.
""",
    'author': "NOVA CODE",
    'website': "https://novaodoo.uz",
    'category': 'AgroNova/Agriculture',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'stock',
        'stock_account',
        'account',
        'analytic',
        'hr',
        'sale_management',
        'agronova_base', 'agronova_savdo_moliya',
    ],
    'data': [
        'security/agronova_qx_groups.xml',
        'security/ir.model.access.csv',
        'data/agronova_qx_data.xml',
        'views/agronova_qx_views.xml',
        'views/agronova_qx_hujjat_views.xml',
        'views/agronova_qx_pl_views.xml',
        'views/agronova_qx_hisobot_views.xml',
        'views/sale_order_views.xml',
        'views/agronova_qx_menus.xml',
    ],
    'installable': True,
    'application': True,
}
