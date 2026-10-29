# -*- coding: utf-8 -*-
{
    'name': "AgroNova — Barcode, QR, printer va skaner",
    'summary': "Lot/seriya uchun QR va chiziqli barcode stikerlari, stiker printerlari "
               "(TSPL/ZPL), chop etish navbati va agenti, qutilash, transferda "
               "majburiy skanerlash.",
    'description': """
AgroNova — Barcode / QR integratsiyasi
===================================
Ombor TZ (8-band: «Barcode va QR Code») va So'yish TZ (8.2: qadoqlash etiketkasi)
talablarini bajaradi.

Nima qiladi
-----------
* **QR kod** — har bir lot/seriya nomini kodlaydi, Odoo Barcode ilovasi va oddiy
  skaner uni o'qiy oladi.
* **Chiziqli barcode** — Code128 yoki EAN-13. Mahsulotning `barcode` maydonidan
  yoki lot nomidan olinadi. Stikerda QR bilan birga ham chiqishi mumkin.
* **Etiketka mazmuni** — mahsulot nomi, QR/barcode, partiya raqami, og'irligi (kg),
  ishlab chiqarilgan sana va yaroqlilik muddati. Har bir element printer
  sozlamasida alohida yoqiladi/o'chiriladi.
* **Stiker printerlari** — har printer uchun alohida yozuv: o'lchami, tili
  (TSPL/ZPL), harflar to'plami (kirill), qoraligi va tezligi. Formada jonli
  ko'rinish (preview) — chop etishdan oldin sig'ishi ko'rinadi.
* **Chop etish navbati + agent** — server uzoqda (VPS) bo'lsa ham sexdagi agent
  dasturi navbatni olib printerga yuboradi.
* **Qutilash** — bir nechta seriyani bitta quti kodiga birlashtirish, quti QR ini
  bir marta skanerlab hammasini o'tkazish.
* **Transferda majburiy skanerlash** — qabul/jo'natishda seriyalar skanerlanmasa
  transfer tasdiqlanmaydi (operatsiya turi bo'yicha istisno berish mumkin).
    """,
    'author': "NOVA CODE",
    'website': "https://novaodoo.uz",
    'category': 'AgroNova/Ombor',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'depends': [
        'stock',
        'product_expiry',
        'agronova_base',
    ],
    'external_dependencies': {'python': ['qrcode', 'Pillow']},
    'data': [
        'security/ir.model.access.csv',
        'data/config_parameter.xml',
        'data/product_barcode_action.xml',
        'report/lot_qr_label_report.xml',
        'report/lot_qr_label_template.xml',
        'views/label_printer_views.xml',
        'views/agronova_lot_box_views.xml',
        'views/stock_picking_type_views.xml',
        'views/stock_picking_views.xml',
        'views/stock_lot_views.xml',
        'views/stock_quant_views.xml',
        'views/res_config_settings_views.xml',
        'views/agronova_barcode_menus.xml',
    ],
    'installable': True,
    'application': True,
    'sequence': 26,
}
