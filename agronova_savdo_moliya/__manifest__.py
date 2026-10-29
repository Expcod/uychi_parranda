# -*- coding: utf-8 -*-
{
    'name': "AgroNova — savdo va moliya (depozit yadrosi)",
    'summary': "Depozit egalari, depozit balansi va naqd xarajatning depozitdan chiqimi",
    'description': """
**Diqqat — bu modulning hozirgi hajmi ataylab minimal.**

TZ bo'yicha `agronova_savdo_moliya` katta modul: kassa, storno, chek, mijoz
qarzi, inkassatsiya. Ona Tovuq modulini yozish paytida bu modul hali
mavjud emas edi, lekin xarajat hujjatining «naqd» to'lov turi **depozitga**
bog'lanishi shart. Model egaligi (xmlid) keyin ko'chirilganda muammo
bo'lmasligi uchun `agronova.depozit` darhol o'z joyida — shu modulda —
yaratildi.

Hozircha shu narsa bor:

* `agronova.depozit` — depozit egasi (brigadir, ta'minotchi, bo'lim boshlig'i)
  va uning qoldig'i;
* `agronova.depozit.harakat` — depozitga kirim / depozitdan chiqim, har biri
  manba hujjatga bog'langan, o'chirilmaydi — faqat storno;
* `agronova.xarajat.mixin` kengaytmasi — naqd xarajatda depozit majburiy,
  tasdiqlanganda depozitdan avtomat chiqim yoziladi.

Kassa, chek va mijoz qarzi shu modulga keyingi bosqichda qo'shiladi.
""",
    'author': "NOVA CODE",
    'website': "https://novaodoo.uz",
    'category': 'AgroNova/Accounting',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'depends': [
        'agronova_base',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/agronova_depozit_data.xml',
        'views/agronova_depozit_views.xml',
    ],
    'installable': True,
    'application': False,
}
