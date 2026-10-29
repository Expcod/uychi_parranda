# -*- coding: utf-8 -*-
{
    'name': "AgroNova — Inkubatoriya",
    'summary': "Tuxum qabuli, inkubatsiya partiyasi, jo'ja ochilishi va tannarxi",
    'description': """
AgroNova ERP — Inkubatoriya bo'limi moduli.

Asosiy talab (TZ 13-band): **tuxumdan jo'jagacha zanjir uzilmasligi**.

    Ona tovuq filiali → Tuxum ombori → Tuxum partiyasi →
    Inkubatsiya partiyasi → Jo'ja partiyasi → Jo'ja tannarxi →
    Ichki sotuv (Boquv) / Tashqi sotuv

Standart Odoo bilan qoplanmaydigan qismlar shu modulda:

* **Tuxum qabuli** — Ona tovuqning ichki sotuv hujjatidan avtomat
  qoralama ochiladi. Tuxum jismonan allaqachon ko'chgan bo'ladi, bu
  hujjat uning **kelib chiqishi va qiymatini** inkubatsiya partiyasiga
  bog'laydi;
* **Inkubatsiya partiyasi** — inkubator raqami, mas'ul, qo'yilgan sana,
  kutilayotgan va haqiqiy ochilish sanasi;
* **Ochilish hujjati** — ochilgan jo'ja, ochilmagan tuxum, nobud va brak.
  Ochilish foizi, nobudgarchilik va brak foizi, 1 tuxumdan jo'ja
  koeffitsienti avtomat hisoblanadi. Tuxum ombordan hisobdan chiqadi,
  jo'ja omborga kiradi;
* **Jo'ja tannarxi** — tuxum qiymati + elektr + gaz + suv + ish haqi +
  veterinariya + dori. Analitik qatlam yagona manba, tannarx maydonlari
  qo'lda yozilmaydi;
* **Jo'jani Boquvga berish** — TZ 8-band bo'yicha bo'lim daromadi
  shakllanadigan ichki sotuv, oddiy ko'chirish emas;
* **Elminatsiya** — realizatsiya qilinmagan ichki marja konsolidatsiyada
  chiqarib tashlanadi;
* **Foyda-zarar sahifasi** — boshqa bo'limlardagi bilan bir xil.

Tashqi mijozga jo'ja sotuvi standart Sales bilan ketadi; tannarxdan past
sotuv nazorati `agronova_ona_tovuq` da butun loyiha uchun qo'yilgan.
""",
    'author': "NOVA CODE",
    'website': "https://novaodoo.uz",
    'category': 'AgroNova/Manufacturing',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'depends': [
        'base', 'mail', 'stock', 'stock_account', 'account', 'analytic',
        'hr', 'sale_management', 'agronova_base', 'agronova_savdo_moliya',
        # Tuxum Ona tovuq bo'limidan keladi: qabul hujjati o'sha yerdagi
        # ichki sotuvga va tuxum partiyasiga bog'lanadi — zanjir shundan
        # uzilmaydi (TZ 13-band). Bog'liqlik bir yo'nalishli: quyi bo'lim
        # yuqorisiga tayanadi, aksincha emas.
        'agronova_ona_tovuq',
    ],
    'data': [
        'security/agronova_inkubatoriya_groups.xml',
        'security/ir.model.access.csv',
        'security/agronova_inkubatoriya_rules.xml',
        'data/agronova_inkubatoriya_data.xml',
        'views/agronova_ink_inkubator_views.xml',
        'views/agronova_ink_qabul_views.xml',
        'views/agronova_ink_partiya_views.xml',
        'views/agronova_ink_ochilish_views.xml',
        'views/agronova_ink_hujjat_views.xml',
        'views/agronova_ink_pl_views.xml',
        'views/agronova_ink_hisobot_views.xml',
        'views/sale_order_views.xml',
        'views/agronova_ink_menus.xml',
    ],
    'installable': True,
    'application': True,
}
