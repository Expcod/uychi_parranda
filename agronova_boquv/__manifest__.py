# -*- coding: utf-8 -*-
{
    'name': "AgroNova — Boquv",
    'summary': "Go'sht yo'nalishi: filial, bino, partiya, kunlik jurnal, tannarx va so'yishga topshirish",
    'description': """
AgroNova ERP — Boquv (M05) bo'limi moduli.

Go'sht yo'nalishida boqilayotgan jo'jalarni **partiya asosida** yuritadi va
**har kuni 1 bosh hamda 1 kg tirik vazn tannarxini** hisoblaydi.

Zanjir: **filial → bino → partiya → jo'ja kirimi → kunlik jurnal → vazn →
tannarx → so'yishga jo'natish → foyda/zarar**.

Asosiy mexanizmlar:

* **Bino holati** tannarxga ta'sir qiladi: `dizinfeksiya` (m² ulushi to'liq),
  `aktiv` (m² ulushi), `no_aktiv` (xarajat kelmaydi);
* **ikkita sana** — partiya ochilgan va jo'ja kelgan; kutish normasi 15 kun,
  ortiqcha kun partiyaga emas, «bo'sh turish zarari» hisobiga;
* bitta binoda **bir necha aktiv partiya** bo'lishi mumkin (har xil yoshdagi
  jo'jalar) — Ona Tovuqdan farqi shu;
* kunlik jurnal: nobud, yem (kg), suv, dori — yem ombordan FIFO bo'yicha
  hisobdan chiqadi va partiya analitikasiga tushadi;
* **obxod** kuniga kamida 3 marta: harorat, holat, muammo, chora;
* avtomat ko'rsatkichlar: **FCR, yashovchanlik %, o'rtacha kunlik o'sish,
  EPEF**, nobudgarchilik %;
* **kunlik tannarx snapshot** — bugungi va kechagi tannarxni solishtirish
  va dinamika grafigi uchun;
* so'yimga jo'natish: mashina, yuk xati, manzil; **yo'l yo'qotishi 3% gacha**
  binoga, ortig'i tekshiruv aktiga;
* tannarx maydonlari **barcha rollar uchun readonly** — qo'lda kiritilmaydi.

Xarajat hujjati va analitik hisob mexanizmi `agronova_base` dan meros olinadi —
Ona Tovuq va Qishloq xo'jaligi bilan bir xil uslub.
""",
    'author': "NOVA CODE",
    'website': "https://novaodoo.uz",
    'category': 'AgroNova/Manufacturing',
    'version': '19.0.1.1.0',
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
        'purchase',
        'agronova_base',
        # Brigader kunlik jurnalni Telegram bot orqali to'ldiradi.
        'agronova_telegram',
        'agronova_savdo_moliya',
    ],
    'data': [
        'security/agronova_boquv_groups.xml',
        'security/ir.model.access.csv',
        'security/agronova_boquv_rules.xml',
        'data/agronova_boquv_data.xml',
        'data/agronova_boquv_normativ_data.xml',
        'views/agronova_boquv_filial_views.xml',
        'views/agronova_boquv_bino_views.xml',
        'views/agronova_boquv_partiya_views.xml',
        'views/agronova_boquv_jurnal_views.xml',
        'views/agronova_boquv_hujjat_views.xml',
        'views/agronova_boquv_ish_haqi_views.xml',
        'views/agronova_boquv_pl_views.xml',
        'report/agronova_boquv_partiya_tannarx.xml',
        'views/agronova_boquv_menus.xml',
        # Menyulardan KEYIN — panel `menu_boquv_operatsiya` ga ilinadi.
        'views/agronova_boquv_panel_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'agronova_boquv/static/src/**/*',
        ],
    },
    'installable': True,
    'application': True,
}
