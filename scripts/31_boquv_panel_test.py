# -*- coding: utf-8 -*-
"""Boquv brigadir panelining uchdan-uchgacha sinovi (Odoo shell).

Ishga tushirish:

    echo "exec(open(r'agronova_custom/scripts/31_boquv_panel_test.py', \
        encoding='utf-8').read())" | python run_odoo.py shell \
        -c odoo-agronova.conf -d agronova_boquv_test --no-http

MUHIM: kutilayotgan xatolar `with env.cr.savepoint():` ichida chaqiriladi —
aks holda yiqilgan create tranzaksiyani buzib, keyingi tekshiruvlarni ham
noto'g'ri qilib qo'yadi.
"""
from odoo.exceptions import UserError, ValidationError

OK, FAIL = [], []


def tekshir(nom, shart, izoh=''):
    (OK if shart else FAIL).append(nom)
    print(("  [OK]   " if shart else "  [XATO] ") + nom
          + (" — %s" % izoh if izoh else ""))


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
admin.sudo().write({'group_ids': [
    (4, env.ref('agronova_boquv.group_boquv_hisobchi').id),
    (4, env.ref('agronova_base.group_agronova_bosh_buxgalter').id),
    (4, env.ref('analytic.group_analytic_accounting').id),
    (4, env.ref('stock.group_stock_manager').id),
]})
env = env(user=admin.id)

Partiya = env['agronova.boquv.partiya']
Bino = env['agronova.boquv.bino']
Filial = env['agronova.boquv.filial']

print("\n=== 0. SINOV MA'LUMOTLARI ===")
company = env.company
xodim = env['hr.employee'].search([('user_id', '=', admin.id)], limit=1)
if not xodim:
    xodim = env['hr.employee'].create({'name': 'Panel brigadiri',
                                       'user_id': admin.id})
else:
    xodim.user_id = admin.id

ombor = env['stock.warehouse'].search([('company_id', '=', company.id)], limit=1)
filial = Filial.search([], limit=1) or Filial.create({
    'name': 'Panel sinov filiali', 'code': 'PSF',
})
# Sarf ombordan chiqishi uchun filialga ombor biriktirilgan bo'lishi shart.
if not filial.warehouse_id and ombor:
    filial.warehouse_id = ombor.id
bino = Bino.create({
    'name': 'Panel sinov sexi', 'code': 'PSS-%s' % filial.id,
    'filial_id': filial.id, 'maydoni': 1000.0, 'sigimi': 20000,
    'brigadir_id': xodim.id,
})
tekshir("Bino yaratildi", bool(bino))
# Yangi bino «no aktiv» bo'lib tug'iladi — partiya ochilishidan oldin
# dizinfeksiyaga o'tkaziladi (TZ 8-band).
bino.action_dizinfeksiya()

partiya = Partiya.create({
    'filial_id': filial.id, 'bino_id': bino.id, 'brigadir_id': xodim.id,
})
partiya.action_ochish()
kirim = env['agronova.boquv.joja.kirim'].create({
    'partiya_id': partiya.id, 'dona': 20000, 'birlik_narx': 5000,
    'ortacha_vazn': 0.042,
})
kirim.action_tasdiqlash()
if partiya.holat != 'active':
    partiya.action_faollashtirish()
tekshir("Partiya faol holatga o'tdi", partiya.holat == 'active',
        partiya.holat)
tekshir("Boshlang'ich bosh soni kirdi", partiya.boshlangich_son == 20000,
        partiya.boshlangich_son)

# Lot/seriya bilan kuzatiladigan mahsulot sinovni chalg'itadi (Odoo lot
# so'raydi), shuning uchun ataylab kuzatilmaydiganini olamiz.
yem = env['product.product'].create({
    'name': 'Panel sinov yemi', 'is_storable': True, 'tracking': 'none',
    'uom_id': env.ref('uom.product_uom_kgm').id,
})
# Ombordan chiqishi uchun zaxira kerak — aks holda tasdiqlash yiqiladi.
if ombor:
    env['stock.quant'].with_context(inventory_mode=True).create({
        'product_id': yem.id,
        'location_id': ombor.lot_stock_id.id,
        'inventory_quantity': 100000,
    }).action_apply_inventory()

print("\n=== 1. ui_home ===")
home = Partiya.ui_home()
tekshir("Panel ochildi", isinstance(home, dict) and 'partiyalar' in home)
kart = [k for k in home['partiyalar'] if k['id'] == partiya.id]
tekshir("Yangi partiya panelda ko'rinadi", len(kart) == 1)
kart = kart[0] if kart else {}
tekshir("Kartochkada tirik jo'ja soni", kart.get('joriy_son') == 20000,
        kart.get('joriy_son'))
tekshir("Obxod normasi 3 (TZ 10-band)", kart.get('obxod_norma') == 3)
tekshir("Bugun obxod qilinmagan", kart.get('obxod_bugun') == 0)
tekshir("Bugun jurnal yo'q", kart.get('jurnal_bugun') is False)
ogohlar = [o for o in home['ogohlar'] if o['partiya_id'] == partiya.id]
turlar = {o['tur'] for o in ogohlar}
tekshir("Jurnalsizlik ogohlantirishi chiqdi", 'jurnal' in turlar, turlar)
tekshir("Obxod yetishmasligi ogohlantirishi chiqdi", 'obxod' in turlar)
tekshir("Ma'lumotnomalar berildi",
        bool(home['nobud_sabablari']) and bool(home['sarf_turlari'])
        and bool(home['holat_baholari']))

print("\n=== 2. OBXOD ===")
detail = Partiya.ui_partiya(partiya.id)
tekshir("ui_partiya batafsil qaytardi",
        'kart' in detail and 'normativ' in detail and 'obxodlar' in detail)
res = Partiya.ui_obxod({
    'partiya_id': partiya.id, 'harorat': 32.0,
    'jojalar_holati': 'yaxshi', 'yem_holati': 'yaxshi',
    'suv_holati': 'qoniqarli', 'olgan_joja': 3,
    'muammo': 'Suv idishi ifloslangan', 'chora': 'Yuvildi',
})
tekshir("Obxod yozildi", bool(res.get('id')))
tekshir("Obxod soni oshdi", res['partiya']['kart']['obxod_bugun'] == 1,
        res['partiya']['kart']['obxod_bugun'])
tekshir("Obxod ro'yxatda ko'rinadi", len(res['partiya']['obxodlar']) == 1)
tekshir("Obxodda mas'ul brigadir avtomat qo'yildi",
        env['agronova.boquv.obxod'].browse(res['id']).brigadir_id == xodim)

for _i in range(2):
    res = Partiya.ui_obxod({'partiya_id': partiya.id, 'harorat': 31.5})
tekshir("Uch marta obxoddan keyin norma bajarildi",
        res['partiya']['kart']['obxod_bugun'] == 3)
home2 = Partiya.ui_home()
turlar = {o['tur'] for o in home2['ogohlar'] if o['partiya_id'] == partiya.id}
tekshir("Obxod ogohlantirishi yo'qoldi", 'obxod' not in turlar, turlar)

print("\n=== 3. KUNLIK JURNAL ===")
res = Partiya.ui_jurnal({
    'partiya_id': partiya.id,
    'nobud_son': 40, 'nobud_sabab': 'kasallik',
    'suv_litr': 1200, 'harorat': 31.0,
    'izoh': 'Panel orqali',
    'sarflar': [{'product_id': yem.id, 'tur': 'yem', 'miqdor': 900}],
})
jurnal = env['agronova.boquv.jurnal'].browse(res['id'])
tekshir("Jurnal qoralama holida yaratildi", res['holat'] == 'draft')
tekshir("Sarf qatori yozildi", len(jurnal.sarf_ids) == 1)
tekshir("Jurnal ogohlantirishi yo'qoldi",
        not [o for o in Partiya.ui_home()['ogohlar']
             if o['partiya_id'] == partiya.id and o['tur'] == 'jurnal'])

# Ikkinchi marta yuborish — qoralama ustiga yoziladi, sarf ikkilanmaydi.
res = Partiya.ui_jurnal({
    'partiya_id': partiya.id,
    'nobud_son': 50, 'nobud_sabab': 'kasallik',
    'suv_litr': 1300, 'harorat': 31.2,
    'sarflar': [{'product_id': yem.id, 'tur': 'yem', 'miqdor': 950}],
})
jurnal = env['agronova.boquv.jurnal'].browse(res['id'])
tekshir("Qoralama ustiga yozildi (yangi jurnal yaratilmadi)",
        env['agronova.boquv.jurnal'].search_count([
            ('partiya_id', '=', partiya.id)]) == 1)
tekshir("Sarf qatori ikkilanmadi", len(jurnal.sarf_ids) == 1,
        len(jurnal.sarf_ids))
tekshir("Yangi qiymat yozildi", jurnal.nobud_son == 50)

res = Partiya.ui_jurnal({
    'partiya_id': partiya.id,
    'nobud_son': 50, 'nobud_sabab': 'kasallik',
    'suv_litr': 1300, 'harorat': 31.2,
    'sarflar': [{'product_id': yem.id, 'tur': 'yem', 'miqdor': 950}],
    'tasdiqlash': True,
})
tekshir("Jurnal tasdiqlandi", res['holat'] == 'posted')
tekshir("Nobud partiyaga o'tdi",
        res['partiya']['kart']['joriy_son'] == 19950,
        res['partiya']['kart']['joriy_son'])
tekshir("Yem sarfi partiyaga tushdi", partiya.yem_sarf_kg == 950,
        partiya.yem_sarf_kg)
tekshir("Sarf ombordan chiqdi", bool(jurnal.sarf_ids.move_id))

xato_kutamiz("Tasdiqlangan kunni panel qayta yozmaydi",
             lambda: Partiya.ui_jurnal({
                 'partiya_id': partiya.id, 'nobud_son': 1,
                 'nobud_sabab': 'boshqa', 'sarflar': [],
             }))
xato_kutamiz("Nobud bosh sonidan ko'p bo'lmaydi",
             lambda: Partiya.ui_jurnal({
                 'partiya_id': partiya.id, 'sana': '2026-01-02',
                 'nobud_son': 999999, 'nobud_sabab': 'boshqa',
                 'sarflar': [],
             }))

print("\n=== 4. VAZN ===")
res = Partiya.ui_vazn({
    'partiya_id': partiya.id, 'tortilgan_son': 100,
    'ortacha_vazn': 1.85, 'min_vazn': 1.60, 'max_vazn': 2.10,
})
vazn = env['agronova.boquv.vazn'].browse(res['id'])
tekshir("Vazn yozuvi yaratildi", bool(vazn))
tekshir("Jami tirik vazn hisoblandi",
        abs(vazn.jami_tirik_vazn - 19950 * 1.85) < 1.0,
        vazn.jami_tirik_vazn)
tekshir("Kartochkada o'rtacha vazn yangilandi",
        res['partiya']['kart']['ortacha_vazn'] == 1.85,
        res['partiya']['kart']['ortacha_vazn'])
xato_kutamiz("Vaznsiz yozuv qabul qilinmaydi",
             lambda: Partiya.ui_vazn({
                 'partiya_id': partiya.id, 'tortilgan_son': 0,
                 'ortacha_vazn': 0,
             }))

print("\n=== 5. XARAJAT (depozit bilan) ===")
depozit = env['agronova.depozit'].create({
    'name': 'Panel brigadiri depoziti', 'egasi_id': xodim.id,
    'company_id': company.id,
})
env['agronova.depozit.harakat'].create({
    'depozit_id': depozit.id, 'turi': 'kirim', 'summa': 5_000_000,
    'holat': 'tasdiqlangan', 'izoh': 'Sinov uchun',
})
tekshir("Depozitda pul bor", depozit.balans == 5_000_000)
home = Partiya.ui_home()
tekshir("Panel depozit qoldig'ini ko'rsatadi",
        home['depozit'] and home['depozit']['balans'] == 5_000_000)

kategoriya = env['agronova.xarajat.kategoriya'].search([], limit=1)
tekshir("Xarajat kategoriyasi mavjud", bool(kategoriya))

xato_kutamiz("Naqd xarajat fotosiz saqlanmaydi",
             lambda: Partiya.ui_xarajat({
                 'partiya_id': partiya.id, 'kategoriya_id': kategoriya.id,
                 'nom': 'Fotosiz', 'miqdor': 1, 'narx': 100000,
                 'tolov_turi': 'naqd', 'depozit_id': depozit.id,
             }))

FOTO = ('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk'
        'YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==')
res = Partiya.ui_xarajat({
    'partiya_id': partiya.id, 'kategoriya_id': kategoriya.id,
    'nom': 'Sexga lampochka', 'miqdor': 10, 'narx': 15000,
    'tolov_turi': 'naqd', 'depozit_id': depozit.id,
    'foto': FOTO, 'foto_filename': 'chek.png',
    'tasdiqlash': True,
})
xarajat = env['agronova.boquv.xarajat'].browse(res['id'])
tekshir("Xarajat tasdiqlandi", res['holat'] == 'tasdiqlangan')
tekshir("Depozitdan chiqim yozildi", depozit.balans == 4_850_000,
        depozit.balans)
tekshir("Panel yangi qoldiqni qaytardi",
        res['depozit_balans'] == 4_850_000, res['depozit_balans'])
tekshir("Xarajat partiyaga to'g'ridan-to'g'ri bog'landi",
        xarajat.partiya_id == partiya and xarajat.maqsad_turi == 'bitta')
tekshir("Analitik qator partiyaga yozildi",
        bool(xarajat.analytic_line_ids),
        len(xarajat.analytic_line_ids))
tekshir("Xarajat partiya tannarxiga tushdi",
        partiya.jami_xarajat > 0, partiya.jami_xarajat)

print("\n=== 6. MAHSULOT QIDIRUVI ===")
natija = Partiya.ui_search_product('', 'yem')
tekshir("Mahsulot tanlagichi ishladi", isinstance(natija, list) and natija)
tekshir("Tanlagich o'lchov birligini beradi",
        all('uom_id' in r and 'uom' in r for r in natija))

print("\n=== 7. HUQUQLAR (record rule) ===")
begona_user = env['res.users'].create({
    'name': 'Begona brigadir', 'login': 'begona_brigadir_boquv',
    'company_id': company.id,
    'group_ids': [(4, env.ref('agronova_boquv.group_boquv_brigadir').id),
                  (4, env.ref('base.group_user').id)],
})
begona_env = env(user=begona_user.id)
korgan = begona_env['agronova.boquv.partiya'].search([])
tekshir("Begona brigadir o'zga partiyani ko'rmaydi",
        partiya not in korgan, korgan.mapped('name'))
begona_home = begona_env['agronova.boquv.partiya'].ui_home()
tekshir("Panel ham begona partiyani bermaydi",
        all(k['id'] != partiya.id for k in begona_home['partiyalar']))

begona_xodim = env['hr.employee'].create({
    'name': 'Begona brigadir', 'user_id': begona_user.id,
})
bino.brigadir_id = begona_xodim.id
partiya.brigadir_id = begona_xodim.id
begona_home = begona_env['agronova.boquv.partiya'].ui_home()
tekshir("Brigadir biriktirilgach partiya panelda paydo bo'ldi",
        any(k['id'] == partiya.id for k in begona_home['partiyalar']))

print("\n=== 8. FAOL BO'LMAGAN PARTIYA ===")
yopiq = Partiya.create({
    'filial_id': filial.id, 'bino_id': bino.id, 'brigadir_id': xodim.id,
})
xato_kutamiz("Faol bo'lmagan partiyaga obxod yozilmaydi",
             lambda: Partiya.ui_obxod({'partiya_id': yopiq.id,
                                       'harorat': 30}))
xato_kutamiz("Faol bo'lmagan partiyaga jurnal yozilmaydi",
             lambda: Partiya.ui_jurnal({'partiya_id': yopiq.id,
                                        'nobud_son': 0, 'sarflar': []}))
tekshir("Qoralama partiya panelda ko'rinmaydi",
        all(k['id'] != yopiq.id for k in Partiya.ui_home()['partiyalar']))

print("\n" + "=" * 60)
print("NATIJA: %d ta o'tdi, %d ta yiqildi" % (len(OK), len(FAIL)))
if FAIL:
    print("YIQILGANLAR:")
    for f in FAIL:
        print("  - " + f)
print("=" * 60)
env.cr.rollback()
