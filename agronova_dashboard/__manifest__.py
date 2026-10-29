# -*- coding: utf-8 -*-
{
    'name': "AgroNova — Rahbar paneli va analitika",
    'summary': "Agro-sanoat holdingi uchun yagona rahbar paneli: KPI, drill-down tafsilotlar, "
               "3D biznes xaritasi, filiallar va ishlab chiqarish analitikasi",
    'description': """
AgroNova — parrandachilik / agro-sanoat korxonalari uchun rahbar paneli
=======================================================================

Bitta oynada butun korxona: moliya, kassa, qarzdorlik, ombor, xarid, do'kon (POS),
yem zavodi, ona tovuq, inkubatoriya, boquv, so'yish, qishloq xo'jaligi, transport,
ish haqi va davomat.

* **Moslashuvchan tarkib** — faqat o'rnatilgan modullar bo'limlari ko'rinadi:
  bitta panel kichik fermaga ham, to'liq zanjirli holdingga ham mos keladi.
* **Drill-down** — har bir kartochka, reyting qatori, grafik ustuni va 3D bino
  bosilganda tafsilot oynasi ochiladi: ko'rsatkichlar, grafik, yozuvlar jadvali,
  ichma-ich o'tish (filial → partiya → kunlik jurnal) va Odoo hujjatining o'zi.
* **3D biznes xaritasi** — mahsulot oqimi (yem → tuxum → jo'ja → boquv → go'sht →
  do'kon → pul) uch o'lchamli sahnada; fermalar, dalalar va omborlar 3D ko'rinishi.
  Bino balandligi — hajm, rangi — normativ holati.
* **Avtomatik xulosalar** — normadan og'ish, muddati o'tgan qarz, kechikkan
  zayavka kabi muammolar panel tepasida darhol ko'rinadi.
* **Oldingi davr bilan solishtirish** (▲/▼ %) va mini-grafiklar.
* **Oq yorliq (white-label)** — panel nomi va texnologik normativlar
  Sozlamalar → Rahbar paneli bo'limidan beriladi, kod o'zgarmaydi.

Qo'shimcha analitik hisobotlar: partiya tannarxi, yem tannarxi va ijara taqsimoti,
so'yish NRV taqsimoti, debitorlik muddatlari (aging), filiallar P&L.
    """,
    'author': "NOVA CODE",
    'website': "https://novaodoo.uz",
    'category': 'AgroNova/Analytics',
    'version': '19.0.3.0.0',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'base_setup',
        'account',
        'stock',
        'mrp',
        'analytic',
        'agronova_base',
        'agronova_boquv',
        'agronova_ona_tovuq',
        'agronova_inkubatoriya',
        'agronova_soyish',
        'agronova_yem_zavodi',
        'agronova_kassa',
        'agronova_savdo_moliya',
        'agronova_transport',
        'agronova_qishloq_xojaligi',
    ],
    'assets': {
        'web.assets_backend': [
            'agronova_dashboard/static/src/dashboard/dashboard.scss',
            'agronova_dashboard/static/src/dashboard/dashboard.xml',
            'agronova_dashboard/static/src/dashboard/scene3d.js',
            'agronova_dashboard/static/src/dashboard/dashboard.js',
        ],
        # Odoo «Dark» temasi: faqat rang tokenlari almashtiriladi.
        'web.assets_web_dark': [
            'agronova_dashboard/static/src/dashboard/dashboard.dark.scss',
        ],
    },
    'data': [
        'security/agronova_dashboard_security.xml',
        'security/ir.model.access.csv',
        'views/agronova_executive_dashboard_views.xml',
        'views/agronova_production_analytics_views.xml',
        'views/agronova_financial_analytics_views.xml',
        'views/agronova_batch_cost_report_views.xml',
        'views/agronova_feed_cost_report_views.xml',
        'views/agronova_slaughter_cost_report_views.xml',
        'views/agronova_debt_aging_report_views.xml',
        'views/agronova_branch_pl_report_views.xml',
        'views/res_config_settings_views.xml',
        'views/agronova_dashboard_menus.xml',
    ],
    'installable': True,
    'application': True,
    'sequence': 1,
}
