# -*- coding: utf-8 -*-
{
    'name': "AgroNova — POS (savdo nuqtasi)",
    'summary': "Go'sht do'koni uchun POS: tarozi, FEFO lot, kassa kitobiga "
               "ulanish, tannarxdan past sotuv taqiqi va kredit limiti",
    'description': """
AgroNova ERP — savdo nuqtasi (POS).

**TZ holati.** Texnik topshiriqda POS uchun alohida bo'lim YO'Q — u bir
marta, M08 (Sotuv) bandining oxirida «POS — keyingi bosqichda» deb tilga
olinadi. Shuning uchun bu modul POS ni noldan o'ylab topmaydi, balki
qo'shni bandlarning POS ga tegishli talablarini bajaradi:

* **M08** — narx ro'yxatlari, tannarxdan past sotuv taqiqi, kredit
  limiti, tarozi, sotuvchi kesimida hisobot;
* **M04** — 80mm chek, kun (smena) yopish majburiyati, naqd pulning
  kassa kitobiga tushishi;
* **M06** — go'sht lot va yaroqlilik muddati bilan yuritiladi, tarozida
  aniq vazn;
* **M01** — FEFO: muddati oldin tugaydigan partiya birinchi ketadi.

**Odoo POS ustiga qurilgan.** Loyihaning prinsipi — «tayyor Odoo
modullaridan maksimal foydalanish». Offline rejim, chek printeri, smena,
barcode va to'lov usullari `point_of_sale` da allaqachon bor; bu modul
faqat standartda yo'q narsani qo'shadi:

1. **FEFO lot avtomat** — go'sht mahsulotlari lot bilan kuzatiladi, lekin
   kassir har bir tarozi urishida lot terib o'tira olmaydi. Modul
   sotuvdan keyin lotni omborda muddati eng oldin tugaydiganidan avtomat
   biriktiradi. Standart Odoo bunday holatda ombor hujjatini **jimgina
   ochiq qoldiradi** (xatosi `try/except` da yutiladi) — ya'ni pul olindi,
   tovar esa hisobdan chiqmadi. Shu tuzoq yopiladi.
2. **Kassa kitobiga ulanish** — smena yopilganda naqd tushum
   `agronova.kassa` ga kirim bo'lib tushadi. Busiz korxonada ikkita parallel
   naqd hisobi paydo bo'lardi va kassir kechqurun pulni sanaganda hisob
   chiqmasdi.
3. **Tannarxdan past sotuv taqiqi** (M08) — chegirma tannarxdan pastga
   tushsa POS yopmaydi. Tannarxi noma'lum (0) mahsulot tekshirilmaydi.
4. **Kredit limiti** (M08) — «keyin to'lash» usulida mijozning jami qarzi
   limitdan oshsa sotuv bloklanadi.
5. **Tarozi barcode** — vazn joylashtirilgan EAN-13 shtrix kodini o'qish
   qoidasi.
""",
    'author': "NOVA CODE",
    'website': "https://novaodoo.uz",
    'category': 'AgroNova/Sales',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'depends': [
        'point_of_sale',
        'stock',
        'product_expiry',
        'agronova_kassa',
    ],
    'data': [
        'data/agronova_pos_data.xml',
        'views/pos_config_views.xml',
        'views/pos_order_views.xml',
        'views/agronova_kassa_harakat_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'agronova_pos/static/src/**/*',
        ],
    },
    'post_init_hook': '_agronova_pos_post_init',
    'installable': True,
    'application': False,
}
