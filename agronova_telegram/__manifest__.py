# -*- coding: utf-8 -*-
{
    'name': "AgroNova — Telegram bot (transport)",
    'summary': "Haydovchi reys xarajatini chek rasmi bilan Telegram orqali yuboradi",
    'description': """
Transport bo'limi uchun Telegram bot.

Bot Odoo ichida emas, **alohida jarayon** sifatida ishlaydi (`bot/bot.py`) va
Odoo bilan XML-RPC orqali gaplashadi. Butun biznes mantiq shu modulda —
botda faqat suhbat oqimi.

Imkoniyatlari:

* `/start` → ism-familiya so'raladi, ariza Odooga tushadi,
  administrator uni xodimga biriktiradi
* «Xarajat kiritish» → ochiq reysni tanlash → xarajat turi → summa →
  **chek rasmi (majburiy)** → Odooda `hr.expense` yaratiladi va reysga bog'lanadi
* «Mening reyslarim» → ochiq reyslar ro'yxati
* «Hisob-kitobim» → hisoblangan ulush va topshirilishi kerak bo'lgan qoldiq
* Barcha amallar `agronova.telegram.log` jurnaliga yoziladi

Keyingi bosqichda shu asosga ferma kunlik jurnali, tasdiqlash tugmalari va
rahbariyat xabarnomalari qo'shiladi (TZ M11).
""",
    'author': "NOVA CODE",
    'website': "https://novaodoo.uz",
    'category': 'Human Resources/Fleet',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'depends': [
        'agronova_transport',
        'hr',
        'hr_expense',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/hr_employee_views.xml',
        'views/telegram_log_views.xml',
        'views/telegram_request_views.xml',
    ],
    'installable': True,
    'application': False,
}
