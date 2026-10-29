# -*- coding: utf-8 -*-
{
    'name': "AgroNova — Yem zavodi",
    'summary': "Yem zavodi: reja, retseptura versiyalari, smena, sarf va yo'qotish nazorati, "
               "qadoqlash, tarozi, jo'natma, zaxira, energiya va tannarx",
    'description': """
AgroNova ERP — Yem ishlab chiqarish zavodi.

Bitta zanjir, ma'lumot bir marta kiritiladi:

**xarid → tarozi → xomashyo kirimi → reja → ishlab chiqarish buyurtmasi →
haqiqiy sarf → yo'qotish → qadoqlash → tayyor mahsulot ombori → jo'natma
(tarozi) → tannarx va moliyaviy natija**

* **Ishlab chiqarish rejasi** — kunlik/haftalik/oylik, mahsulot va liniya
  kesimida; xomashyo yetarliligi tekshiriladi, yetishmayotgani uchun xarid
  talabi yaratiladi; reja-fakt va kechikish nazorati.
* **Retseptura versiyalari** — tasdiqlangan retseptura o'zgarmaydi, o'zgarish
  faqat yangi versiya orqali; har buyurtmada qaysi versiya ishlatilgani
  qayd etiladi. Komponent bo'yicha ruxsat etilgan og'ish, standart yo'qotish.
* **Sarf nazorati** — reja va haqiqiy sarf har komponent bo'yicha; ruxsat
  etilgan og'ishdan oshsa buyurtma boshliq tasdig'isiz yopilmaydi.
* **Yo'qotishlar** — me'yoriy va haqiqiy yo'qotish alohida; yo'qotishlar
  reyestri sabab, mas'ul, dalolatnoma va moliyaviy ta'siri bilan.
* **Smena hisoboti** — reja, fakt, xomashyo, qadoqlangan mahsulot, brak,
  to'xtashlar; tasdiqlangandan keyin o'zgarmaydi, tuzatish izi qoladi.
* **Qadoqlash** — qop soni, nominal va bo'sh qop og'irligi, brutto/netto,
  kam yoki ortiqcha to'ldirish; qop sarfi ombordan chiqadi.
* **Jo'natma** — tashqi sotuv va ichki xo'jaliklarga (ona tovuq, boquv)
  alohida; tarozi bilan tafovut nazorati.
* **Xomashyo zaxirasi** — minimum/maksimum, o'rtacha sarf, necha kunga
  yetishi, tugash arafasidagi xomashyo ogohlantirishi.
* **Energiya** — elektr va gaz, bir tonnaga sarf, me'yordan farq.
* **Tannarx** — xomashyo, qadoq va taqsimlangan ishlab chiqarish
  xarajatlari bilan 1 kg / 1 tonna haqiqiy tannarx, reja bilan solishtirish.
""",
    'author': "NOVA CODE",
    'website': "https://novaodoo.uz",
    'category': 'AgroNova/Manufacturing',
    'version': '19.0.2.0.0',
    'license': 'LGPL-3',
    'depends': [
        'mrp', 'mrp_account', 'stock_account', 'purchase_stock', 'sale_stock', 'hr',
        'agronova_base', 'agronova_tarozi', 'agronova_telegram',
    ],
    'data': [
        'security/agronova_yem_groups.xml',
        'security/ir.model.access.csv',
        'security/agronova_yem_rules.xml',
        'data/agronova_yem_data.xml',
        'views/product_views.xml',
        'views/agronova_yem_liniya_views.xml',
        'views/mrp_bom_views.xml',
        'views/mrp_production_views.xml',
        'views/agronova_yem_reja_views.xml',
        'views/agronova_yem_smena_views.xml',
        'views/agronova_yem_qadoqlash_views.xml',
        'views/agronova_yem_jonatma_views.xml',
        'views/agronova_yem_yoqotish_views.xml',
        'views/agronova_yem_toxtash_views.xml',
        'views/agronova_yem_energiya_views.xml',
        'views/agronova_yem_zaxira_views.xml',
        'views/agronova_yem_xarajat_views.xml',
        'views/res_config_settings_views.xml',
        'views/agronova_yem_menus.xml',
    ],
    'installable': True,
    'application': True,
}
