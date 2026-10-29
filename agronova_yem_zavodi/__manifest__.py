# -*- coding: utf-8 -*-
{
    'name': "AgroNova — Yem zavodi",
    'summary': "Yem tannarxi: 1 kg va 1 tonna, reja-fakt, tannarx tahlili",
    'description': """
AgroNova ERP — Yem zavodi moduli.

Yem zavodi TZ sining asosiy qismi standart Odoo MRP bilan qoplanadi
(retsept, ishlab chiqarish, ombor, sotuv). Bu modul faqat standartda
yo'q narsalarni qo'shadi:

* **1 kg va 1 tonna tannarxi** — Odoo 19 da `mrp.production` da tannarx
  yig'indisi maydonlari yo'q, qiymat `stock.move.value` da yashiringan;
* **xomashyo ulushi** — tannarxning necha foizi xomashyoga to'g'ri keladi;
* **ishlab chiqarish xarajati** — ish markazi orqali kirgan qism
  (elektr, gaz, ish haqi, amortizatsiya) alohida ko'rinadi;
* **reja-fakt taqqoslash** — retsept bo'yicha nazariy tannarx va haqiqiy
  tannarx, chetlanish foizi bilan;
* **tannarx tahlili** — pivot va grafik ko'rinishlar (mahsulot, oy, hafta
  kesimida).

Tonnaga o'girish o'lchov birligi orqali bajariladi, shuning uchun mahsulot
kilogrammda ham, tonnada ham yuritilishi mumkin.
""",
    'author': "NOVA CODE",
    'website': "https://novaodoo.uz",
    'category': 'AgroNova/Manufacturing',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['mrp', 'mrp_account', 'stock_account'],
    'data': [
        'views/mrp_production_views.xml',
        'views/agronova_yem_menus.xml',
    ],
    'installable': True,
    'application': False,
}
