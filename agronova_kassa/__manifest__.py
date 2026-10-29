# -*- coding: utf-8 -*-
{
    'name': "AgroNova — Kassa (naqd pul)",
    'summary': "Kassa kitobi, kirim/chiqim orderi, kunlik yopish, "
               "kassalararo transfer, inkassatsiya va 80mm chek",
    'description': """
AgroNova ERP — M04 Kassa moduli.

Kassir naqd pulni shu yerda yuritadi, buxgalter esa hech narsani qo'lda
ko'chirmaydi — har bir yozuv o'z provodkasini o'zi yozadi.

**Nima bor:**

* **Kassa kartochkasi — 3 tur:** markaziy (bosh kassa), filial kassasi,
  valyuta kassasi. Har biri o'z korxonasiga (filialiga) va o'z naqd
  jurnaliga bog'lanadi, qoldig'i real vaqtda ko'rinadi.
* **Kirim / chiqim orderi** — modda, kontragent yoki xodim, izoh va
  **analitik kesim**. TZ ning eng qattiq talabi shu yerda ham amal qiladi:
  analitikasiz chiqim saqlanmaydi.
* **Storno** — tasdiqlangan yozuv hech qachon o'chirilmaydi, faqat teskari
  yoziladi (TZ: «o'chirish taqiq»).
* **Kunlik yopish** — kassir smena oxirida pulni sanaydi, farq darhol
  ko'rinadi; yopilgan kunga yozuv qo'shilmaydi (menejer qayta ochmaguncha).
* **Kassalararo transfer** — TZ dagi to'liq zanjir bilan:
  `qoralama → yo'lda → tasdiqlandi / rad etildi`. «Yo'lda» bosqichida pul
  **5710 «Yo'ldagi pul»** hisobida turadi, ya'ni na u kassada, na bu kassada
  yo'qolib qolmaydi.
* **Inkassatsiya** — kassadan bankka topshirish, xuddi shu uch bosqich bilan
  (bank ko'chirmasi kelgach tasdiqlanadi).
* **Depozit bilan bog'lanish** — brigadir/ta'minotchiga kassadan naqd
  berilganda `agronova.depozit` ga avtomat kirim yoziladi; qaytarilganda
  chiqim. Depozitdagi pul ikki marta sanalmaydi.
* **Mijoz qarzi** — sotuvdan tushum moddasi bo'yicha kirim yozilganda
  `account.payment` yaratilib mijozning ochiq hisob-fakturalari bilan
  yarashtiriladi, qarz avtomat kamayadi.
* **80mm chek + QR** — har yozuvga chek chiqadi, QR kod ochiq tekshirish
  sahifasiga (`/kassa/chek/<token>`) olib boradi.
* **Kassa kitobi** — kunlik rasmiy shakl (ochilish, kirim, chiqim, qoldiq)
  PDF sifatida.
* **Kassir paneli** — OWL ekran: kassalar, kun xulosasi, kirim/chiqim
  tugmalari, transfer, kunni yopish.

**Nima yo'q (keyingi bosqich):** SMS tasdiq (Eskiz.uz), chekni Telegram/
WhatsApp orqali yuborish va tasdiqlanmagan hujjat bo'yicha har 5 daqiqada
eskalatsiya — bularning hammasi tashqi xizmat kaliti kelgach qo'shiladi.
""",
    'author': "NOVA CODE",
    'website': "https://novaodoo.uz",
    'category': 'AgroNova/Accounting',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'depends': [
        'account',
        'hr',
        'agronova_savdo_moliya',
    ],
    'data': [
        'security/agronova_kassa_groups.xml',
        'security/ir.model.access.csv',
        'security/agronova_kassa_security.xml',
        'data/agronova_kassa_data.xml',
        'data/agronova_kassa_paperformat.xml',
        'report/kassa_chek_templates.xml',
        'report/kassa_kitobi_templates.xml',
        'report/kassa_reports.xml',
        'views/agronova_kassa_views.xml',
        'views/agronova_kassa_modda_views.xml',
        'views/agronova_kassa_harakat_views.xml',
        'views/agronova_kassa_otkazma_views.xml',
        'views/agronova_kassa_inkassatsiya_views.xml',
        'views/agronova_kassa_kun_views.xml',
        'views/agronova_depozit_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'agronova_kassa/static/src/**/*',
        ],
    },
    'post_init_hook': '_agronova_kassa_post_init',
    'application': True,
    'installable': True,
}
