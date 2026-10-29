# -*- coding: utf-8 -*-
{
    'name': "AgroNova — Transport reyslari",
    'summary': "Reys, reys loti, xarajat yig'ish, foyda va haydovchi ulushi",
    'description': """
AgroNova ERP transport bo'limi moduli.

Odooning `fleet` moduli mashina, haydovchi, texnik xizmat va shartnomalarni
yuritadi, lekin «reys» tushunchasi yo'q. Bu modul shuni qo'shadi:

* **Reys** (`agronova.trip`) — ichki yoki tashqi, 7 bosqichli holat zanjiri
* Har reysga **avtomat analitik hisob (lot)** ochiladi — TZ talabi
* Xarajatlar reysga yig'iladi: `hr.expense` (haydovchi cheklari) +
  `fleet.vehicle.log.services` (yo'ldagi ta'mir) + qo'lda kiritilgani
* `Foyda = daromad − xarajat`, `haydovchi ulushi = foyda × %` —
  **sof foydadan**, tushumdan emas
* Haydovchining olgan / topshirgan puli va qoldiq qarzi
* Avtomobil, haydovchi, mijoz va davr kesimida tahlil (pivot, grafik)
""",
    'author': "NOVA CODE",
    'website': "https://novaodoo.uz",
    'category': 'Human Resources/Fleet',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'depends': [
        'fleet',
        'hr_expense',
        'analytic',
        'stock',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/agronova_transport_rules.xml',
        'data/agronova_transport_data.xml',
        'views/agronova_trip_views.xml',
        'views/hr_expense_views.xml',
        'views/stock_picking_views.xml',
        'views/fleet_vehicle_views.xml',
        'wizard/agronova_trip_attach_picking_views.xml',
    ],
    'installable': True,
    'application': False,
}
