# -*- coding: utf-8 -*-
{
    'name': "AgroNova — Xarid (Zakupka)",
    'summary': "Zayavka → ruxsat → xarid → tranzit → ombor → Didox: to'liq xarid sikli",
    'description': """
AgroNova ERP — Xarid (Zakupka) bo'limi moduli.

**Arxitektura qarori (texzadaniya 0.5-bandiga javob).**
OCA `purchase_request` va `base_tier_validation` bu o'rnatmaning
addons_path ida yo'q (faqat Odoo core + Enterprise, 1397 modul) va OCA da
19.0 uchun barqaror port ham hali chiqmagan. Shuning uchun `agronova.zayavka`
va `agronova.ruxsat` shu modulda yoziladi — lekin **ataylab yupqa**:
ular faqat so'rov va tasdiqlash qatlamini olib yuradi, tovar harakati va
moliyaviy yozuv esa to'liq Odoo standartiga (`stock.picking`,
`account.move`, `stock.landed.cost`, `account.asset`) topshiriladi.
Ya'ni 15-bo'limdagi «tayyor modulni ishlat» talabi buzilmaydi — faqat
tasdiqlash zanjiri va zayavka qobig'i o'z qo'limizda.

Asosiy mexanizmlar:

* **Tovar va faktura — ikki alohida hujjat.** `stock.picking` omborchida,
  `account.move` buxgalterda. Didox fakturasi 1-2 kun kech kelsa ham oqim
  to'xtamaydi (MSFO: qarz tovar nazorati o'tgan zahoti tan olinadi).
* **Zakupchik tranziti** — har bir zakupchikka shaxsiy ombor joyi; sotib
  olingan, lekin omborchi qabul qilmagan tovar shu yerda, zakupchik
  zimmasida turadi.
* **Uch qatlamli narx normasi** — xarid tarixi → kategoriya limiti →
  «birinchi xarid» (kamida 3 taklif). Og'ish foizi tovar → kategoriya →
  umumiy tartibida aniqlanadi; chegaradan oshsa kirim hujjati saqlanmaydi.
* **Ketma-ket uch bosqichli tasdiqlash**, o'z-o'zini tasdiqlash taqiqi va
  avtomat bir pog'ona yuqoriga ko'tarish.
* **Muddat nazorati** — barcha muddatlar bitta markazlashgan ish vaqti
  kalendaridan (`resource.calendar`) hisoblanadi, `ir.cron` eskalatsiya
  qiladi.
* **KPI** — uch o'lchovli omborchi bahosi, narx tejami, e'tiroz (nizo)
  mexanizmi, oy yopilgach qulf. Faqat bonusga ta'sir qiladi.
* **Didox** — avtomat tortish va STIR+summa+sana bo'yicha solishtirish,
  ikki tomonlama hisobot (tovar bor/faktura yo'q va aksincha).
* **Import (C1/C2)** — GTD, bojxona, Landed Cost; C2 uskuna omborga
  tushmaydi, `account.asset` orqali amortizatsiya qilinadi.

Depozit, storno, foto majburiyati va tahrirlash muddati pog'onasi
qaytadan yozilmagan — `agronova_base` va `agronova_savdo_moliya` dan meros.
""",
    'author': "NOVA CODE",
    'website': "https://novaodoo.uz",
    'category': 'AgroNova/Purchase',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'resource',
        'hr',
        'stock',
        'stock_account',
        'purchase',
        'purchase_stock',
        'account',
        'stock_landed_costs',
        'product_expiry',
        'account_asset',
        'agronova_base',
        'agronova_savdo_moliya',
    ],
    'data': [
        'security/agronova_zakupka_groups.xml',
        'security/ir.model.access.csv',
        'security/agronova_zakupka_rules.xml',
        'data/agronova_zakupka_sequence.xml',
        'data/agronova_zakupka_data.xml',
        'data/agronova_zakupka_cron.xml',
        'views/res_partner_views.xml',
        'views/res_users_views.xml',
        'views/product_views.xml',
        'views/stock_location_views.xml',
        'views/agronova_zayavka_views.xml',
        'views/agronova_ruxsat_views.xml',
        'views/agronova_narx_views.xml',
        'views/agronova_kirim_views.xml',
        'views/agronova_qaytarish_views.xml',
        'views/agronova_import_views.xml',
        'views/agronova_nomenklatura_views.xml',
        'views/agronova_kpi_views.xml',
        'views/agronova_didox_views.xml',
        'wizard/agronova_qabul_wizard_views.xml',
        'report/agronova_zakupka_reports.xml',
        'views/res_config_settings_views.xml',
        'views/agronova_zakupka_menus.xml',
    ],
    'installable': True,
    'application': True,
}
