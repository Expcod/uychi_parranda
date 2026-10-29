# -*- coding: utf-8 -*-
{
    'name': "AgroNova — Ona Tovuq",
    'summary': "Ona tovuq partiyalari, sexlar, kunlik jurnal, tuxum tannarxi va sotuvi",
    'description': """
AgroNova ERP — Ona Tovuq bo'limi moduli.

Ona tovuq yo'nalishining to'liq sikli:

**Jo'ja o'stirish partiyasi** (jo'ja kirimi → kunlik jurnal → yopilish, 1 bosh
tannarxi qotadi) → **Ona tovuq partiyasi** (tannarx meros bo'lib o'tadi, bozor
narxida qayta baholash yo'q) → kunlik tuxum jurnali → **tuxum omboriga
kirim** (lot bilan) → **ichki sotuv** (Inkubatsiyaga) yoki **tashqi sotuv**
(standart Sales) → tuxum berish % normadan tushganda poda **so'yishga ichki
sotuv** sifatida o'tkaziladi.

Asosiy mexanizmlar:

* barcha xarajat va daromad `account.analytic.line` ga yig'iladi — tannarx,
  foyda-zarar va rentabellik faqat shundan hisoblanadi;
* xarajat hujjati `agronova.xarajat.mixin` dan meros (naqd/qarz, foto majburiy,
  tahrirlash muddati 12/24/36 soat, storno);
* xarajat taqsimlash: m² / bosh soni / teng / to'g'ridan-to'g'ri;
* ish haqi — sexga biriktirilgan operator to'g'ridan-to'g'ri, biriktirilmagan
  xodim m² bo'yicha, oy o'rtasida ko'chsa kunlar bo'yicha bo'linadi;
* tannarx maydoni **barcha rollar uchun readonly** — qo'lda kiritilmaydi;
* ichki narx: sotuv bo'limi taklif qiladi, bosh buxgalter tasdiqlaydi,
  tarix o'zgartirilmaydi.
""",
    'author': "NOVA CODE",
    'website': "https://novaodoo.uz",
    'category': 'AgroNova/Manufacturing',
    'version': '19.0.1.0.0',
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
        'agronova_base',
        'agronova_savdo_moliya',
        # Eskirgan poda so'yishga o'tkazilganda So'yish bo'limida qabul
        # hujjati ochiladi — `agronova.soyish.qabul` ga bog'lanish shundan.
        # Aylanma bog'liqlik yo'q: agronova_soyish faqat agronova_base ga tayanadi.
        'agronova_soyish',
        # Ish haqi taqsimoti summani shu moduldan oladi.
        'agronova_ish_haqi',
        # Kunlik jurnalni sex operatori Telegram bot orqali to'ldiradi —
        # xodimni chat ID bo'yicha topish shu modulda.
        'agronova_telegram',
    ],
    'data': [
        'security/agronova_ona_tovuq_groups.xml',
        'security/ir.model.access.csv',
        'security/agronova_ona_tovuq_rules.xml',
        'data/agronova_ona_tovuq_data.xml',
        'data/agronova_ona_tovuq_normativ_data.xml',
        'views/agronova_ona_tovuq_views.xml',
        'views/agronova_ona_tovuq_jurnal_views.xml',
        'views/agronova_ona_tovuq_hujjat_views.xml',
        'views/agronova_ona_tovuq_ish_haqi_views.xml',
        'views/agronova_ona_tovuq_elminatsiya_views.xml',
        'views/agronova_ona_tovuq_pl_views.xml',
        'views/agronova_ona_tovuq_hisobot_views.xml',
        'views/hr_employee_views.xml',
        'views/sale_order_views.xml',
        'views/res_config_settings_views.xml',
        'views/agronova_ona_tovuq_menus.xml',
    ],
    'installable': True,
    'application': True,
}
