# -*- coding: utf-8 -*-
{
    'name': "AgroNova — Tarozi",
    'summary': "Avtomobil va qadoq tarozilari: ikki marta tortish, brutto/tara/netto, tafovut nazorati",
    'description': """
AgroNova ERP — Tarozi integratsiyasi.

* **Tarozi qurilmalari** — avtomobil, platforma va qadoq tarozilari.
  Qurilma (yoki undagi agent) ko'rsatkichni HTTP orqali yuboradi
  (`/agronova/tarozi/vazn`), Odoo oxirgi barqaror vaznni saqlaydi.
* **Tortish varaqasi** — ikki marta tortish tamoyili: birinchi va ikkinchi
  tortish bitta operatsiyada, `Netto = Brutto − Tara`.
* **Qo'lda o'zgartirish cheklangan** — tarozidan olingan vaznni faqat
  «tuzatish» huquqi bor xodim o'zgartira oladi, eski va yangi qiymat
  chatterga yoziladi.
* **Tafovut nazorati** — hujjatdagi netto bilan haqiqiy netto farqi kg va
  % da; to'rt daraja: me'yorda, ogohlantirish, tasdiq kerak, kritik.
  Kritik tafovutda varaqa mas'ul tasdig'isiz yakunlanmaydi. Farq avtomatik
  yo'qotish deb yozilmaydi — avval sabab va tasdiq.
* **Ombor hujjati bilan bog'lanish** — kirim yoki chiqim hujjatidan tortish
  ochiladi, yakunlanganda hujjat miqdori haqiqiy nettoga moslanadi.
""",
    'author': "NOVA CODE",
    'website': "https://novaodoo.uz",
    'category': 'AgroNova/Inventory',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['mail', 'stock', 'purchase_stock', 'sale_stock', 'agronova_base'],
    'data': [
        'security/agronova_tarozi_groups.xml',
        'security/ir.model.access.csv',
        'data/agronova_tarozi_data.xml',
        'views/agronova_tarozi_views.xml',
        'views/agronova_tarozi_tortish_views.xml',
        'views/stock_picking_views.xml',
        'views/res_config_settings_views.xml',
        'views/agronova_tarozi_menus.xml',
    ],
    'installable': True,
    'application': False,
}
