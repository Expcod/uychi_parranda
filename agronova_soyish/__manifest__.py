# -*- coding: utf-8 -*-
{
    'name': "AgroNova — So'yish",
    'summary': "Qabul va tortish, so'yish, chiqim foizi, tashqi mijoz xizmati",
    'description': """
AgroNova ERP — So'yish bo'limi moduli.

So'yish TZ sining katta qismi standart Odoo bilan qoplanadi: sortirovka va
kesish MRP yon mahsulotlari orqali, tayyor mahsulot ombori va yaroqlilik
muddati `product_expiry` bilan, sotuv `sale_stock` bilan, kuzatuv esa
lot/seriya orqali. Bu modul faqat standartda yo'q narsalarni qo'shadi:

* **Qabul va tortish** — brutto, tara, netto va 1 dona o'rtacha vazni.
  Tovuq donada sanaladi, kilogrammda tortiladi;
* **Chiqim foizi** — tirik vazndan necha foiz tayyor mahsulot chiqdi.
  Odooda bunday ko'rsatkich yo'q;
* **Ikki manba** — ichki boquv va tashqi mijoz. Tashqi mijozning tovug'i
  ham, mahsuloti ham uning mulki: bizga faqat xizmat haqi tegadi
  (so'yilgan dona × narx), ombor harakati yaratilmaydi;
* **Sortirovka tannarxi** — chiqqan mahsulotlar orasida tannarx vazn
  yoki qiymat ulushi bo'yicha bo'linadi;
* **Xarajat taqsimoti** — bosh soni yoki tirik vazn bo'yicha.

Vaqtinchalik saqlash (mijoz mulki omborda turishi) uchun Odooning
konsignatsiya mexanizmi ishlatiladi — custom ombor mantiqi yozilmagan.
""",
    'author': "NOVA CODE",
    'website': "https://novaodoo.uz",
    'category': 'AgroNova/Manufacturing',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'depends': [
        'base', 'mail', 'stock', 'stock_account', 'account', 'analytic',
        'hr', 'sale_management', 'agronova_base', 'agronova_savdo_moliya',
    ],
    'data': [
        'security/agronova_soyish_groups.xml',
        'security/ir.model.access.csv',
        'data/agronova_soyish_data.xml',
        'views/agronova_soyish_views.xml',
        'views/agronova_soyish_hujjat_views.xml',
        'views/agronova_soyish_pl_views.xml',
        'views/agronova_soyish_hisobot_views.xml',
        'views/agronova_soyish_menus.xml',
    ],
    'installable': True,
    'application': True,
}
