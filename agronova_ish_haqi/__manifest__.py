# -*- coding: utf-8 -*-
{
    'name': "AgroNova — Ish haqi",
    'summary': "Tarif, oylik hisoblash, xodim balansi va provodka",
    'description': """
AgroNova ERP — ish haqi moduli (TZ M09).

Odooning `hr_payroll` moduli o'rniga yozilgan. Sababi: O'zbekiston uchun
payroll lokalizatsiyasi mavjud emas, ya'ni barcha hisoblash qoidasini
baribir qo'lda yozish kerak bo'lardi — Odooning qoida dvigateli esa
Python parchalari bilan ishlaydi va uni brigadir ham, ishchi ham o'qiy
olmaydi. TZ talab qiladigan hisob esa sodda va aniq.

Nima bor:

* **uch xil tarif** — 26 kunlik oklad, 30 kunlik oklad, soatbay;
  tarif tarixi bilan yuritiladi, tasdiqlangani o'zgartirilmaydi;
* **oylik hisoblash hujjati** — xodimlar yig'iladi, ishlagan kun/soat
  davomatdan olinadi (bo'lmasa norma bo'yicha to'ldiriladi), avans,
  jarima va bonus qo'lda kiritiladi;
* **xodim balansi** — hisoblandi / berildi / qoldiq, brigadir depoziti
  bilan bir xil uslubda;
* **buxgalteriya provodkasi** — Dt ish haqi xarajati / Kt xodimga qarz;
* **storno** — provodka teskarilanadi, balans qatorlari o'chiriladi.

Ish haqini sex va partiyalarga taqsimlash bu modulning ishi emas — uni
bo'lim modullari qiladi (`agronova.ona_tovuq.ish_haqi` va h.k.), summani esa
shu yerdan oladi. Aks holda xarajat ikki marta sanalgan bo'lardi.
""",
    'author': "NOVA CODE",
    'website': "https://novaodoo.uz",
    'category': 'AgroNova/Human Resources',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'depends': [
        'base', 'mail', 'hr', 'hr_attendance', 'account', 'analytic',
        'agronova_base', 'agronova_kassa',
    ],
    'data': [
        'security/agronova_ish_haqi_groups.xml',
        'security/ir.model.access.csv',
        'data/agronova_ish_haqi_data.xml',
        'views/agronova_ish_haqi_views.xml',
        'views/hr_employee_views.xml',
        'views/res_config_settings_views.xml',
        'views/agronova_ish_haqi_menus.xml',
    ],
    'installable': True,
    'application': True,
}
