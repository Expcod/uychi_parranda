# -*- coding: utf-8 -*-
"""agronova_kassa modulining uchdan-uchgacha sinovi (Odoo shell).

Ishga tushirish:

    python run_odoo.py shell -c odoo-agronova.conf -d agronova_kassa_test \
        --no-http < agronova_custom/scripts/30_kassa_test.py

MUHIM: kutilayotgan xatolar `with env.cr.savepoint():` ichida chaqiriladi —
aks holda yiqilgan create tranzaksiyani buzib, keyingi tekshiruvlarni ham
noto'g'ri qilib qo'yadi.
"""
from odoo.exceptions import UserError, ValidationError

OK, FAIL = [], []


def tekshir(nom, shart, izoh=''):
    (OK if shart else FAIL).append(nom)
    print(("  [OK]   " if shart else "  [XATO] ") + nom + (" — %s" % izoh if izoh else ""))


def xato_kutamiz(nom, fn, xatolar=(UserError, ValidationError)):
    try:
        with env.cr.savepoint():
            fn()
    except xatolar as e:
        tekshir(nom, True, str(e).split('\n')[0][:70])
        return
    except Exception as e:  # noqa: BLE001
        tekshir(nom, False, "kutilmagan xato: %s" % e)
        return
    tekshir(nom, False, "xato chiqmadi")


env = env  # noqa: F821  (Odoo shell beradi)
admin = env.ref('base.user_admin')
# Kassa guruhlari alohida — admin ham ularga qo'shilmasa yozolmaydi
# (bu record rule/ACL to'g'ri ishlayotganining birinchi dalili).
admin.sudo().write({'group_ids': [
    (4, env.ref('agronova_kassa.group_agronova_kassa_menejer').id),
    (4, env.ref('agronova_base.group_agronova_bosh_buxgalter').id),
    (4, env.ref('analytic.group_analytic_accounting').id),
]})
env = env(user=admin.id)

Kassa = env['agronova.kassa']
Harakat = env['agronova.kassa.harakat']
Modda = env['agronova.kassa.modda']
Kun = env['agronova.kassa.kun']
Otkazma = env['agronova.kassa.otkazma']
Inkas = env['agronova.kassa.inkassatsiya']

print("\n=== 0. O'RNATISH NATIJASI ===")
kassalar = Kassa.search([])
tekshir("Har korxona uchun kassa yaratildi",
        len(kassalar) == env['res.company'].search_count([]),
        "%d ta kassa" % len(kassalar))
tekshir("Kassalarda hisob va jurnal bor",
        all(k.account_id and k.journal_id for k in kassalar))
tekshir("Yo'ldagi pul hisobi biriktirilgan",
        all(k._transit_account() for k in kassalar))
tekshir("Har kassaning o'z jurnali",
        len(set(kassalar.mapped('journal_id').ids)) == len(kassalar))

markaziy = kassalar.filtered(lambda k: k.turi == 'markaziy')[:1]
filial = kassalar.filtered(
    lambda k: k.turi == 'filial' and k.company_id.parent_id == markaziy.company_id)[:1]
markaziy.opening_balance = 10_000_000
markaziy.kun_yopish_majburiy = False
filial.kun_yopish_majburiy = False
# Bazada oldingi sinovlardan yozuv qolgan bo'lishi mumkin, shuning uchun
# mutlaq son emas, O'ZGARISH tekshiriladi.
boshlangich = markaziy.balance
tekshir("Boshlang'ich qoldiq qoldiqqa qo'shildi", boshlangich >= 10_000_000,
        boshlangich)

m_boshqa_kirim = env.ref('agronova_kassa.modda_boshqa_kirim')
m_xojalik = env.ref('agronova_kassa.modda_xojalik')
m_depozit_out = env.ref('agronova_kassa.modda_depozit_berildi')
m_depozit_in = env.ref('agronova_kassa.modda_depozit_qaytdi')
m_sotuv = env.ref('agronova_kassa.modda_sotuv')

print("\n=== 1. ODDIY KIRIM VA PROVODKA ===")
kirim = Harakat.create({
    'kassa_id': markaziy.id, 'direction': 'in', 'amount': 500_000,
    'modda_id': m_boshqa_kirim.id, 'izoh': 'Test kirim', 'state': 'posted',
})
tekshir("Kirim orderi KKO bilan raqamlandi", kirim.name.startswith('KKO/'))
tekshir("Qoldiq oshdi", markaziy.balance == boshlangich + 500_000,
        markaziy.balance)
tekshir("Provodka yozildi", bool(kirim.move_id) and kirim.move_id.state == 'posted')
dt = kirim.move_id.line_ids.filtered(lambda l: l.debit)
kt = kirim.move_id.line_ids.filtered(lambda l: l.credit)
tekshir("KIRIM: Dt kassa hisobi", dt.account_id == markaziy.account_id)
tekshir("KIRIM: Kt modda hisobi", kt.account_id == m_boshqa_kirim.account_id)
tekshir("Kassa kitobi varag'i ochildi", bool(kirim.kun_id))
tekshir("Chek tokeni berildi", bool(kirim.chek_token) and len(kirim.chek_token) == 32)

print("\n=== 2. CHIQIM, ANALITIKA VA QOLDIQ NAZORATI ===")
xato_kutamiz("Analitikasiz xarajat saqlanmaydi", lambda: Harakat.create({
    'kassa_id': markaziy.id, 'direction': 'out', 'amount': 100_000,
    'modda_id': m_xojalik.id, 'izoh': 'Analitikasiz', 'state': 'posted',
}))

plan = env['account.analytic.plan'].search([], limit=1)
ana = env['account.analytic.account'].search([('plan_id', '=', plan.id)], limit=1)
if not ana:
    ana = env['account.analytic.account'].create({'name': 'Test analitika',
                                                  'plan_id': plan.id})
chiqim = Harakat.create({
    'kassa_id': markaziy.id, 'direction': 'out', 'amount': 300_000,
    'modda_id': m_xojalik.id, 'izoh': 'Xo\'jalik xarajati',
    'analytic_distribution': {str(ana.id): 100}, 'state': 'posted',
})
tekshir("Chiqim orderi KCHO bilan raqamlandi", chiqim.name.startswith('KCHO/'))
tekshir("Qoldiq kamaydi", markaziy.balance == boshlangich + 200_000,
        markaziy.balance)
dt = chiqim.move_id.line_ids.filtered(lambda l: l.debit)
kt = chiqim.move_id.line_ids.filtered(lambda l: l.credit)
tekshir("CHIQIM: Dt modda hisobi", dt.account_id == m_xojalik.account_id)
tekshir("CHIQIM: Kt kassa hisobi", kt.account_id == markaziy.account_id)
tekshir("Analitika modda tomonida", bool(dt.analytic_distribution))
tekshir("Analitik qator yaratildi",
        bool(env['account.analytic.line'].search([('move_line_id', '=', dt.id)])))

xato_kutamiz("Bor puldan ko'p chiqim qilinmaydi", lambda: Harakat.create({
    'kassa_id': markaziy.id, 'direction': 'out', 'amount': 99_000_000_000,
    'modda_id': m_xojalik.id, 'izoh': 'Juda katta',
    'analytic_distribution': {str(ana.id): 100}, 'state': 'posted',
}))

print("\n=== 3. STORNO ===")
oldingi = markaziy.balance
chiqim.action_storno(sabab='Sinov storno')
tekshir("Holat storno bo'ldi", chiqim.state == 'storno')
tekshir("Qoldiq qaytdi", markaziy.balance == oldingi + 300_000, markaziy.balance)
tekshir("Teskari provodka yozildi",
        bool(chiqim.storno_move_id) and chiqim.storno_move_id.state == 'posted')
tekshir("Asl provodka o'chirilmadi (audit izi)",
        chiqim.move_id.state == 'posted')
xato_kutamiz("Tasdiqlangan yozuv o'chirilmaydi", lambda: kirim.unlink())
xato_kutamiz("Ikki marta storno qilinmaydi", lambda: chiqim.action_storno())

print("\n=== 4. DEPOZIT BILAN BOG'LANISH ===")
xodim = env['hr.employee'].search([], limit=1)
if not xodim:
    xodim = env['hr.employee'].create({'name': 'Test brigadir'})
depozit = env['agronova.depozit'].create({
    'name': 'Test depozit', 'egasi_id': xodim.id,
    'company_id': markaziy.company_id.id,
})
xato_kutamiz("Depozit moddasida depozit majburiy", lambda: Harakat.create({
    'kassa_id': markaziy.id, 'direction': 'out', 'amount': 1_000_000,
    'modda_id': m_depozit_out.id, 'state': 'posted',
}))
berish = Harakat.create({
    'kassa_id': markaziy.id, 'direction': 'out', 'amount': 1_000_000,
    'modda_id': m_depozit_out.id, 'depozit_id': depozit.id, 'state': 'posted',
})
tekshir("Depozit balansi oshdi", depozit.balans == 1_000_000, depozit.balans)
tekshir("Depozit harakati bog'landi", bool(berish.depozit_harakat_id))
tekshir("Depozit yozuvi KIRIM", berish.depozit_harakat_id.turi == 'kirim')

qaytarish = Harakat.create({
    'kassa_id': markaziy.id, 'direction': 'in', 'amount': 400_000,
    'modda_id': m_depozit_in.id, 'depozit_id': depozit.id, 'state': 'posted',
})
tekshir("Qaytarilganda depozit kamaydi", depozit.balans == 600_000, depozit.balans)

berish_oldin = depozit.balans
berish.action_storno(sabab='Depozit storno sinovi')
tekshir("Depozit storno to'g'ri hisoblandi (ikki barobar emas)",
        depozit.balans == berish_oldin - 1_000_000, depozit.balans)

print("\n=== 5. MIJOZ QARZINI YOPISH ===")
mijoz = env['res.partner'].create({'name': 'Test mijoz (kassa)'})
mahsulot = env['product.product'].search([('type', '!=', 'combo')], limit=1)
faktura = env['account.move'].with_company(markaziy.company_id).create({
    'move_type': 'out_invoice', 'partner_id': mijoz.id,
    'invoice_line_ids': [(0, 0, {
        'product_id': mahsulot.id, 'quantity': 1, 'price_unit': 250_000,
        'tax_ids': [(5, 0, 0)],
    })],
})
faktura.action_post()
tekshir("Faktura qarzi bor", faktura.amount_residual == 250_000)
tolov = Harakat.create({
    'kassa_id': markaziy.id, 'direction': 'in', 'amount': 250_000,
    'modda_id': m_sotuv.id, 'partner_id': mijoz.id, 'state': 'posted',
})
tekshir("To'lov hujjati yaratildi", bool(tolov.payment_id))
tekshir("Mijoz qarzi yopildi", faktura.amount_residual == 0,
        faktura.amount_residual)
tekshir("To'lov ikki marta yozilmadi (mirror yo'q)",
        Harakat.search_count([('payment_id', '=', tolov.payment_id.id)]) == 1)

print("\n=== 6. KASSALARARO TRANSFER (3 BOSQICH) ===")
markaziy_oldin, filial_oldin = markaziy.balance, filial.balance
transfer = Otkazma.create({
    'from_kassa_id': markaziy.id, 'to_kassa_id': filial.id,
    'amount': 2_000_000, 'izoh': 'Filialga oylik uchun',
})
transfer.action_jonatish()
tekshir("Holat: yo'lda", transfer.state == 'transit')
tekshir("Manba kassadan chiqdi",
        markaziy.balance == markaziy_oldin - 2_000_000, markaziy.balance)
tekshir("Qabul qiluvchiga HALI kirmadi",
        filial.balance == filial_oldin, filial.balance)
tekshir("Yo'ldagi pul ko'rsatkichi", markaziy.transit_balance == 2_000_000)
transit_hisob = transfer._transit_hisob()
transit_qoldiq = sum(env['account.move.line'].search([
    ('account_id', '=', transit_hisob.id), ('parent_state', '=', 'posted'),
]).mapped('balance'))
tekshir("5710 tranzit hisobida pul turibdi", transit_qoldiq == 2_000_000,
        transit_qoldiq)

xato_kutamiz("Noto'g'ri sanoq bilan qabul qilinmaydi",
             lambda: transfer.action_qabul(sanoq=1_900_000))
transfer.action_qabul(sanoq=2_000_000)
tekshir("Holat: tasdiqlangan", transfer.state == 'done')
tekshir("Qabul qiluvchiga kirdi",
        filial.balance == filial_oldin + 2_000_000, filial.balance)
transit_qoldiq = sum(env['account.move.line'].search([
    ('account_id', '=', transit_hisob.id), ('parent_state', '=', 'posted'),
]).mapped('balance'))
tekshir("Tranzit hisobi yopildi", transit_qoldiq == 0, transit_qoldiq)

print("\n=== 7. TRANSFERNI RAD ETISH ===")
markaziy_oldin = markaziy.balance
rad = Otkazma.create({
    'from_kassa_id': markaziy.id, 'to_kassa_id': filial.id, 'amount': 500_000,
})
rad.action_jonatish()
tekshir("Jo'natilganda pul chiqdi",
        markaziy.balance == markaziy_oldin - 500_000)
rad.action_rad(sabab='Pul yetib kelmadi')
tekshir("Rad etilgach pul qaytdi", markaziy.balance == markaziy_oldin,
        markaziy.balance)
tekshir("Holat: rad etilgan", rad.state == 'rad')
transit_qoldiq = sum(env['account.move.line'].search([
    ('account_id', '=', transit_hisob.id), ('parent_state', '=', 'posted'),
]).mapped('balance'))
tekshir("Tranzit hisobi yana nolda", transit_qoldiq == 0, transit_qoldiq)

print("\n=== 8. INKASSATSIYA ===")
bank = env['account.journal'].search([
    ('type', '=', 'bank'),
    ('company_id', 'in', markaziy.company_id.parent_ids.ids),
], limit=1)
if bank:
    markaziy_oldin = markaziy.balance
    inkas = Inkas.create({
        'kassa_id': markaziy.id, 'bank_journal_id': bank.id,
        'amount': 1_500_000, 'inkassator': 'Test inkassator',
    })
    inkas.action_topshirish()
    tekshir("Inkassatsiya: kassadan chiqdi",
            markaziy.balance == markaziy_oldin - 1_500_000)
    tekshir("Inkassatsiya: yo'lda", inkas.state == 'transit')
    bank_oldin = sum(env['account.move.line'].search([
        ('account_id', '=', bank.default_account_id.id),
        ('parent_state', '=', 'posted'),
    ]).mapped('balance'))
    inkas.action_bank_tasdiq()
    bank_keyin = sum(env['account.move.line'].search([
        ('account_id', '=', bank.default_account_id.id),
        ('parent_state', '=', 'posted'),
    ]).mapped('balance'))
    tekshir("Bank hisobiga tushdi", bank_keyin - bank_oldin == 1_500_000,
            bank_keyin - bank_oldin)
    tekshir("Inkassatsiya yakunlandi", inkas.state == 'done')
else:
    print("  (bank jurnali topilmadi — inkassatsiya sinovi o'tkazilmadi)")

print("\n=== 9. KUNNI YOPISH ===")
kun = Kun._kun_topish(markaziy, kirim.date_day)
kun.sanoq = kun.closing
kun.action_yopish()
tekshir("Kun yopildi", kun.state == 'closed')
tekshir("Farq nol", kun.farq == 0)
xato_kutamiz("Yopilgan kunga yozuv qo'shilmaydi", lambda: Harakat.create({
    'kassa_id': markaziy.id, 'direction': 'in', 'amount': 1_000,
    'modda_id': m_boshqa_kirim.id, 'izoh': 'Yopilgan kunga',
    'date': kirim.date, 'state': 'posted',
}))
kun.action_ochish()
tekshir("Menejer kunni qayta ochdi", kun.state == 'open')

print("\n=== 10. TO'LOVNI KASSAGA KO'CHIRISH (mirror) ===")
mirror_oldin = markaziy.balance
pay = env['account.payment'].with_company(markaziy.company_id).create({
    'payment_type': 'inbound', 'partner_type': 'customer',
    'partner_id': mijoz.id, 'amount': 123_000,
    'journal_id': markaziy.journal_id.id,
})
pay.action_post()
tekshir("Naqd jurnaldagi to'lov kassaga tushdi", bool(pay.agronova_harakat_id))
tekshir("Ko'chirilgan yozuv avtomatik", pay.agronova_harakat_id.auto)
tekshir("Mirror qoldiqqa ta'sir qildi",
        markaziy.balance == mirror_oldin + 123_000, markaziy.balance)
# Ko'chirilgan yozuv O'Z provodkasini YOZMASLIGI kerak — to'lovning
# provodkasi allaqachon bor, ikkinchisi yozilsa pul ikki marta tushardi.
tekshir("Mirror o'z provodkasini yozmadi", not pay.agronova_harakat_id.move_id)
tekshir("To'lovning o'z provodkasi joyida",
        bool(pay.move_id) and pay.move_id.state == 'posted')
xato_kutamiz("Avtomatik yozuv qo'lda storno qilinmaydi",
             lambda: pay.agronova_harakat_id.action_storno())
pay.action_draft()
tekshir("To'lov qoralamaga qaytsa mirror storno bo'ldi",
        pay.agronova_harakat_id.state == 'storno')
tekshir("Qoldiq qaytdi", markaziy.balance == mirror_oldin, markaziy.balance)

print("\n=== 11. KUN YOPISH MAJBURIYATI ===")
filial.kun_yopish_majburiy = True
eski = Harakat.create({
    'kassa_id': filial.id, 'direction': 'in', 'amount': 10_000,
    'modda_id': m_boshqa_kirim.id, 'izoh': 'Eski kun',
    'date': '2026-01-05 09:00:00', 'state': 'posted',
})
tekshir("O'tgan kunga yozildi (admin — cheklovsiz)", eski.state == 'posted')
xato_kutamiz("Oldingi kun yopilmasa yangi kunga yozilmaydi",
             lambda: Harakat.create({
                 'kassa_id': filial.id, 'direction': 'in', 'amount': 10_000,
                 'modda_id': m_boshqa_kirim.id, 'izoh': 'Yangi kun',
                 'date': '2026-02-05 09:00:00', 'state': 'posted',
             }))

print("\n=== 12. KASSA KITOBI HISOBOTI ===")
kitob_kun = Kun._kun_topish(markaziy, kirim.date_day)
try:
    html = env['ir.actions.report']._render_qweb_html(
        'agronova_kassa.report_kassa_kitobi', kitob_kun.ids)[0]
    tekshir("Kassa kitobi shabloni renderlandi", b'KASSA KITOBI' in html)
except Exception as e:  # noqa: BLE001
    tekshir("Kassa kitobi shabloni renderlandi", False, str(e)[:80])
try:
    html = env['ir.actions.report']._render_qweb_html(
        'agronova_kassa.report_kassa_chek', kirim.ids)[0]
    tekshir("80mm chek shabloni renderlandi",
            b'KASSA KIRIM ORDERI' in html and b'/report/barcode/' in html)
except Exception as e:  # noqa: BLE001
    tekshir("80mm chek shabloni renderlandi", False, str(e)[:80])

print("\n=== 13. PANEL RPC ===")
home = Kassa.ui_home()
tekshir("ui_home kassalarni qaytardi", len(home['kassalar']) == len(kassalar))
tekshir("Hujjat moddalari panelda ko'rinmaydi",
        all(not Modda.browse(m['id']).faqat_hujjat for m in home['moddalar']))
day = Kassa.ui_day(markaziy.id)
tekshir("ui_day qoldiqni qaytardi", 'closing' in day and 'lines' in day)
tekshir("ui_day qoldig'i kassa qoldig'iga mos",
        abs(day['opening'] + day['kirim'] - day['chiqim'] - day['closing']) < 0.01)
kut = Kassa.ui_kutilayotgan()
tekshir("ui_kutilayotgan ishladi", isinstance(kut, list))

print("\n=== 14. KASSIR HUQUQLARI (record rule) ===")
kassir_user = env['res.users'].create({
    'name': 'Test kassir', 'login': 'test_kassir_kassa',
    'company_id': markaziy.company_id.id,
    'company_ids': [(6, 0, [markaziy.company_id.id, filial.company_id.id])],
    'group_ids': [(4, env.ref('agronova_kassa.group_agronova_kassir').id),
                  (4, env.ref('base.group_user').id)],
})
markaziy.user_ids = [(4, kassir_user.id)]
kassir_env = env(user=kassir_user.id)
korgan = kassir_env['agronova.kassa'].search([])
tekshir("Kassir faqat o'z kassasini ko'radi",
        korgan == markaziy, korgan.mapped('name'))
korgan_harakat = kassir_env['agronova.kassa.harakat'].search([])
tekshir("Kassir faqat o'z kassasi yozuvlarini ko'radi",
        all(h.kassa_id == markaziy for h in korgan_harakat),
        "%d ta yozuv" % len(korgan_harakat))
xato_kutamiz("Kassir kassa kartochkasini o'zgartira olmaydi",
             lambda: kassir_env['agronova.kassa'].browse(markaziy.id).write(
                 {'allow_negative': True}),
             xatolar=(Exception,))
kassir_home = kassir_env['agronova.kassa'].ui_home()
tekshir("Panel kassirga faqat bitta kassa beradi",
        len(kassir_home['kassalar']) == 1)
# Panel tanlagichlari kassir huquqi bilan ishlashi kerak — hr.employee ni
# o'qish odatda faqat HR Officer'da bo'ladi, shuning uchun modul kassirga
# alohida o'qish huquqini beradi.
try:
    xodimlar = kassir_env['agronova.kassa'].ui_search_employees('')
    tekshir("Kassir xodimlarni qidira oladi", isinstance(xodimlar, list))
except Exception as e:  # noqa: BLE001
    tekshir("Kassir xodimlarni qidira oladi", False, str(e)[:70])
try:
    kassir_env['agronova.kassa.harakat'].browse(berish.id).read(
        ['employee_id', 'depozit_id'])
    tekshir("Kassir yozuvdagi xodim/depozit maydonini o'qiy oladi", True)
except Exception as e:  # noqa: BLE001
    tekshir("Kassir yozuvdagi xodim/depozit maydonini o'qiy oladi", False,
            str(e)[:70])

print("\n=== 15. DEPOZITNI KASSADAN BOSHQARISH ===")
# Depozit menyusi Kassa ilovasida turadi, demak kassa menejeri yangi
# depozit ocha olishi kerak (TZ M04: «depozit egalari» kassa qamrovida).
menejer_user = env['res.users'].create({
    'name': 'Test kassa menejeri', 'login': 'test_kassa_menejer',
    'company_id': markaziy.company_id.id,
    'group_ids': [(4, env.ref('agronova_kassa.group_agronova_kassa_menejer').id),
                  (4, env.ref('base.group_user').id)],
})
menejer_env = env(user=menejer_user.id)
try:
    yangi_dep = menejer_env['agronova.depozit'].create({
        'name': 'Menejer ochgan depozit', 'egasi_id': xodim.id,
        'company_id': markaziy.company_id.id,
    })
    tekshir("Kassa menejeri yangi depozit ocha oladi", bool(yangi_dep))
except Exception as e:  # noqa: BLE001
    tekshir("Kassa menejeri yangi depozit ocha oladi", False, str(e)[:70])
xato_kutamiz("Menejer depozitni o'chira olmaydi (tarix saqlanadi)",
             lambda: menejer_env['agronova.depozit'].browse(depozit.id).unlink(),
             xatolar=(Exception,))

print("\n=== 16. CHEK TOKENI (ochiq sahifa) ===")
topilgan = env['agronova.kassa.harakat'].sudo().search(
    [('chek_token', '=', kirim.chek_token)], limit=1)
tekshir("Token bo'yicha yozuv topiladi", topilgan == kirim)
tekshir("Token 32 belgili tasodifiy uuid",
        len(kirim.chek_token) == 32 and kirim.chek_token != chiqim.chek_token)
tekshir("Chek havolasi to'g'ri shakllangan",
        '/kassa/chek/' in (kirim.chek_url or ''))
tekshir("QR manzili barcode marshrutiga ishora qiladi",
        '/report/barcode/' in (kirim.chek_qr_src or '')
        and 'barcode_type=QR' in (kirim.chek_qr_src or ''))
# Sahifaning o'zi `web.frontend_layout` ga tayanadi — u HTTP so'rovsiz
# renderlanmaydi ("object is not bound"), shuning uchun shell'da faqat
# shablon mavjudligi tekshiriladi. Marshrutning o'zi HTTP sinovida
# (tools bilan curl) tekshiriladi.
sahifa = env.ref('agronova_kassa.chek_sahifa', raise_if_not_found=False)
tekshir("Ochiq tekshirish sahifasi shabloni o'rnatildi", bool(sahifa))
tekshir("Sahifa 'chek haqiqiy' holatini ko'rsatadi",
        bool(sahifa) and 'Chek haqiqiy' in (sahifa.arch or ''))
tekshir("Topilmadi sahifasi ham bor",
        bool(env.ref('agronova_kassa.chek_topilmadi', raise_if_not_found=False)))

print("\n" + "=" * 60)
print("NATIJA: %d ta o'tdi, %d ta yiqildi" % (len(OK), len(FAIL)))
if FAIL:
    print("YIQILGANLAR:")
    for f in FAIL:
        print("  - " + f)
print("=" * 60)
env.cr.rollback()
