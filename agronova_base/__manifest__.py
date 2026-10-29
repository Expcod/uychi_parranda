# -*- coding: utf-8 -*-
{
    'name': "AgroNova — umumiy asos (base)",
    'summary': "Bo'limlar uchun umumiy mixin'lar: xarajat hujjati, taqsimlash bazasi, analitik yordamchilar",
    'description': """
AgroNova ERP ning umumiy qatlami.

Boquv, Ona Tovuq, So'yish, Inkubatoriya kabi bo'lim modullarida bir xil
takrorlanadigan mexanizmlar shu yerda bir marta yozilgan:

* `agronova.xarajat.mixin` — xarajat hujjatining umumiy skeleti: naqd/qarz
  to'lov turi, naqdda foto majburiyati, tahrirlash muddati pog'onasi
  (12/24/36 soat), maqsad turi va taqsimlash bazasi (bosh soni / m² / teng).
* `agronova.xarajat.kategoriya` — xarajat kategoriyalari, har biriga standart
  taqsimlash bazasi bog'lanadi (faqat administrator yaratadi).
* `agronova.analitik.mixin` — obyektga (bino, partiya) avtomat analitik hisob
  ochish va unga xarajat/daromad qatorlarini yozish yordamchilari.
* Bo'limlararo umumiy rollar: bosh buxgalter, direktor.

**Muhim:** bu modul hech qanday bo'limga tegishli biznes mantiq saqlamaydi —
faqat qayta ishlatiladigan pattern. Yangi bo'lim moduli yozilganda xarajat
hujjati qaytadan yozilmaydi, shu mixin'dan meros olinadi.
""",
    'author': "NOVA CODE",
    'website': "https://novaodoo.uz",
    'category': 'AgroNova/Base',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'account',
        'analytic',
        'hr',
    ],
    'assets': {
        'web.assets_backend': [
            'agronova_base/static/src/css/agronova_list.css',
        ],
    },
    'data': [
        'security/agronova_base_groups.xml',
        'security/agronova_stock_lot_rules.xml',
        'security/ir.model.access.csv',
        'data/agronova_xarajat_kategoriya_data.xml',
        'data/agronova_mahsulot_guruh_data.xml',
        'views/account_analytic_line_views.xml',
        'views/agronova_xarajat_kategoriya_views.xml',
        'views/agronova_mahsulot_guruh_views.xml',
        'views/agronova_base_menus.xml',
    ],
    'installable': True,
    'application': False,
    'post_init_hook': 'post_init_hook',
}
