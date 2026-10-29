# -*- coding: utf-8 -*-
"""Yem zavodi — 30 kunlik demo ma'lumot (odoo shell uchun).

Hamma raqam Odoo'ning haqiqiy hujjatlari orqali o'tadi — to'g'ridan-to'g'ri
yozilgan «chiroyli» son yo'q:

    xarid buyurtmasi → tarozi (brutto/tara) → kirim (netto) → faktura
    reja → xomashyo tekshiruvi → ishlab chiqarish buyurtmasi → sarf (og'ish bilan)
      → yo'qotish (me'yoriy/haqiqiy) → qadoqlash (qop og'irligi) → smena hisoboti
    jo'natma → sotuv buyurtmasi / ichki ko'chirish → tarozi → faktura → to'lov
    energiya, to'xtashlar, xarajat taqsimoti, xomashyo zaxirasi

Ishga tushirish (bo'sh bazada, modullar o'rnatilgandan keyin):

    python run_odoo.py shell -c <conf> -d <db> --no-http < scripts/demo_yem_zavodi.py

Skript takror ishga tushirilsa qayta yaratmaydi (mahsulot kodlari bo'yicha tekshiradi).
"""
import random
from datetime import date, datetime, time, timedelta

import pytz

R = random.Random(2026)
TZ = pytz.timezone('Asia/Tashkent')
KUNLAR = 30
BUGUN = date.today()

env = env  # noqa: F821  (odoo shell beradi)
env = env(context=dict(env.context, tz='Asia/Tashkent', tracking_disable=True,
                       mail_create_nolog=True, mail_notrack=True))
company = env.company
P = env['product.product']
kg_uom = env.ref('uom.product_uom_kgm')
dona_uom = env.ref('uom.product_uom_unit')


def utc(kun, soat, daqiqa=0):
    """Toshkent vaqti → UTC naive datetime (Odoo saqlash formati)."""
    return TZ.localize(datetime.combine(kun, time(int(soat) % 24, daqiqa))).astimezone(pytz.utc).replace(tzinfo=None)


def log(*a):
    print("·", *a, flush=True)


if P.search([('default_code', '=', 'YZ-PK5')]):
    log("Demo ma'lumot allaqachon bor — to'xtatildi.")
    raise SystemExit

# =============================================================== 0. KORXONA
log("Korxona va sozlamalar")
uzs = env.ref('base.UZS')
uzs.write({'active': True, 'symbol': "so'm"})
try:
    company.write({'name': "Uychi Paranda", 'currency_id': uzs.id, 'country_id': env.ref('base.uz').id})
except Exception as e:  # valyutani faqat provodka bo'lmaganda almashtirsa bo'ladi
    log("valyuta o'zgarmadi:", e)
env.user.tz = 'Asia/Tashkent'
icp = env['ir.config_parameter'].sudo()
icp.set_param('agronova_yem.elektr_narx', 1000)
icp.set_param('agronova_yem.gaz_narx', 1800)
icp.set_param('agronova_yem.kwh_norma_t', 36)
icp.set_param('agronova.brand_name', 'AgroNova')

# =============================================================== 1. OMBORLAR
wh = env['stock.warehouse'].search([('company_id', '=', company.id)], limit=1)
wh.write({'name': "Yem zavodi", 'code': 'YZ'})
Loc = env['stock.location']
qadoq_loc = Loc.create({'name': "Qadoq materiallari", 'location_id': wh.lot_stock_id.id, 'usage': 'internal'})
wh_ot = env['stock.warehouse'].create({'name': "Ona tovuq xo'jaligi", 'code': 'OT', 'company_id': company.id})
wh_bq = env['stock.warehouse'].create({'name': "Boquv bo'limi", 'code': 'BQ', 'company_id': company.id})
icp.set_param('agronova_yem.qadoq_location_id', qadoq_loc.id)
icp.set_param('agronova_yem.ona_tovuq_location_id', wh_ot.lot_stock_id.id)
icp.set_param('agronova_yem.boquv_location_id', wh_bq.lot_stock_id.id)

# =============================================================== 2. HAMKORLAR
log("Hamkorlar va xodimlar")
Partner = env['res.partner']
vendors = {k: Partner.create({'name': n, 'is_company': True, 'supplier_rank': 1}) for k, n in [
    ('don', "Farg'ona Don Mahsulotlari MChJ"),
    ('soya', "Soya Import Trade MChJ"),
    ('moy', "Andijon Yog'-Moy Kombinati"),
    ('mineral', "Mineral Qo'shimchalar MChJ"),
    ('premiks', "Premiks Servis MChJ"),
    ('qop', "Polipak Qadoq MChJ"),
]}
customers = [Partner.create({'name': n, 'is_company': True, 'customer_rank': 1}) for n in [
    "Qo'qon Parranda MChJ", "Namangan Broyler fermer xo'jaligi", "Chust Tuxum MChJ",
    "Marg'ilon Agro fermer xo'jaligi", "Pop Parranda MChJ", "Rishton Broyler fermer xo'jaligi",
]]
Emp = env['hr.employee']
boshliqlar = [Emp.create({'name': n}) for n in ["Akmal Yusupov", "Sherzod Qodirov"]]
ishchilar = [Emp.create({'name': n}) for n in [
    "Bobur Tojiboyev", "Dilshod Rahimov", "Jasur Ergashev", "Otabek Nazarov", "Farrux Usmonov",
    "Ulug'bek Sobirov", "Islom Karimov", "Sardor Mirzayev"]]
omborchi = Emp.create({'name': "Rustam Aliyev"})
texnolog = Emp.create({'name': "Nodira Hasanova"})

# =============================================================== 3. MAHSULOTLAR
log("Mahsulotlar va retsepturalar")
categ = env['product.category'].create({'name': "Yem zavodi", 'property_cost_method': 'fifo'})


def mahsulot(code, name, turi, narx, sotish=0.0, uom=kg_uom, vendor=None, **kw):
    vals = {
        'name': name, 'default_code': code, 'type': 'consu', 'is_storable': True,
        'uom_id': uom.id, 'categ_id': categ.id, 'standard_price': narx,
        'list_price': sotish or narx, 'agronova_yem_turi': turi,
        'purchase_ok': turi != 'yem', 'sale_ok': turi == 'yem',
    }
    vals.update(kw)
    if vendor:
        vals['seller_ids'] = [(0, 0, {'partner_id': vendor.id, 'price': narx, 'min_qty': 0})]
    return env['product.template'].create(vals).product_variant_id


X = {}
for code, name, narx, vend in [
    ('MAKK', "Makkajo'xori", 3300, 'don'), ('BUGD', "Bug'doy (yem)", 3000, 'don'),
    ('SOYA', "Soya shroti 46%", 6800, 'soya'), ('KUNG', "Kungaboqar shroti", 3900, 'moy'),
    ('BALQ', "Baliq uni 62%", 15000, 'soya'), ('MOY', "O'simlik moyi", 19000, 'moy'),
    ('OHAK', "Ohak (bo'r)", 700, 'mineral'), ('MKF', "Monokalsiyfosfat", 9800, 'mineral'),
    ('TUZ', "Osh tuzi", 1100, 'mineral'), ('LIZ', "L-lizin", 26000, 'premiks'),
    ('MET', "DL-metionin", 48000, 'premiks'),
]:
    X[code] = mahsulot('YZ-' + code, name, 'xomashyo', narx, vendor=vendors[vend])
for code, name, narx in [('PRB', "Premiks broyler 0,5%", 32000), ('PRL', "Premiks tuxum yo'nalishi 1%", 29000)]:
    X[code] = mahsulot('YZ-' + code, name, 'premiks', narx, vendor=vendors['premiks'])
QOP40 = mahsulot('YZ-QOP40', "PP qop 40 kg", 'qadoq', 2300, uom=dona_uom, vendor=vendors['qop'],
                 agronova_qop_vazn_kg=0.11)
QOP50 = mahsulot('YZ-QOP50', "PP qop 50 kg", 'qadoq', 2600, uom=dona_uom, vendor=vendors['qop'],
                 agronova_qop_vazn_kg=0.13)

# (kod, nom, sotuv narxi, qop, sig'im, liniya, yo'qotish %, retseptura 1000 kg ga)
YEMLAR = [
    ('PK5', "Broyler start PK-5 (granula)", 7400, QOP40, 40, 1, 1.5,
     {'MAKK': 540, 'SOYA': 330, 'BUGD': 40, 'BALQ': 25, 'MOY': 28, 'OHAK': 13, 'MKF': 12,
      'TUZ': 3, 'LIZ': 2, 'MET': 2, 'PRB': 5}),
    ('PK6', "Broyler o'sish PK-6 (granula)", 7050, QOP40, 40, 1, 1.5,
     {'MAKK': 580, 'SOYA': 290, 'BUGD': 60, 'MOY': 32, 'OHAK': 13, 'MKF': 11, 'TUZ': 3,
      'LIZ': 2, 'MET': 2, 'PRB': 7}),
    ('PK7', "Broyler finish PK-7 (granula)", 6800, QOP40, 40, 1, 1.6,
     {'MAKK': 620, 'SOYA': 240, 'BUGD': 70, 'MOY': 35, 'OHAK': 12, 'MKF': 10, 'TUZ': 3,
      'LIZ': 2, 'MET': 1, 'PRB': 7}),
    ('PK2', "Ona tovuq yemi PK-2", 5600, QOP50, 50, 2, 1.2,
     {'MAKK': 500, 'BUGD': 120, 'SOYA': 180, 'KUNG': 80, 'OHAK': 80, 'MKF': 12, 'TUZ': 3,
      'MET': 1, 'PRL': 10, 'MOY': 14}),
    ('PK1', "Tuxum yo'nalishi PK-1", 5450, QOP50, 50, 2, 1.2,
     {'MAKK': 520, 'BUGD': 100, 'SOYA': 200, 'KUNG': 60, 'OHAK': 85, 'MKF': 12, 'TUZ': 3,
      'MET': 1, 'PRL': 10, 'MOY': 9}),
]
YEM = {}
BOM = {}
for code, name, narx, qop, sigim, liniya, foiz, tarkib in YEMLAR:
    assert abs(sum(tarkib.values()) - 1000) < 0.01, code
    p = mahsulot('YZ-' + code, name, 'yem', 5200, sotish=narx, agronova_qop_sigim_kg=sigim,
                 agronova_qop_product_id=qop.id)
    YEM[code] = p
    bom = env['mrp.bom'].create({
        'product_tmpl_id': p.product_tmpl_id.id, 'product_qty': 1000, 'product_uom_id': kg_uom.id,
        'type': 'normal', 'consumption': 'flexible', 'agronova_yoqotish_foiz': foiz,
        'code': code,
        'bom_line_ids': [(0, 0, {'product_id': X[k].id, 'product_qty': v, 'product_uom_id': kg_uom.id,
                                 'agronova_ogish_foiz': 3.0 if k in ('PRB', 'PRL', 'LIZ', 'MET') else 2.0})
                         for k, v in tarkib.items()],
    })
    bom.action_agronova_tasdiqlash()
    BOM[code] = bom
# Versiya tarixi: PK-6 bir oy oldin moy 28 kg bilan ishlangan, keyin texnolog 32 kg ga oshirgan.
eski = BOM['PK6']
yangi_act = eski.action_agronova_yangi_versiya()
v2 = env['mrp.bom'].browse(yangi_act['res_id'])
# v1 aslida birinchi bo'lgani uchun v2 ni «yangi» qilib, v1 dagi moyni 28 qilib qo'yamiz
eski.with_context(agronova_bom_ruxsat=True).bom_line_ids.filtered(
    lambda l: l.product_id == X['MOY']).product_qty = 28
eski.with_context(agronova_bom_ruxsat=True).bom_line_ids.filtered(
    lambda l: l.product_id == X['MAKK']).product_qty = 584
v2.agronova_izoh = "Yozgi issiqda energiya zichligini oshirish: moy 28 → 32 kg, makkajo'xori 584 → 580 kg."
v2.action_agronova_tasdiqlash()
BOM['PK6'] = v2

# =============================================================== 4. LINIYA, TAROZI
log("Liniyalar, tarozilar, smenalar")
T = env['agronova.tarozi']
t_avto = T.create({'name': "Kirish avtotarozisi (60 t)", 'kod': 'AVTO-1', 'turi': 'avto', 'protokol': 'tcp',
                   'manzil': '192.168.10.21:4001', 'joy': "Asosiy darvoza", 'max_vazn_kg': 60000, 'aniqlik_kg': 20})
t_q1 = T.create({'name': "Qadoqlash dozatori — 1-liniya (jamlovchi)", 'kod': 'QDQ-1', 'turi': 'qadoq',
                 'protokol': 'rs485', 'max_vazn_kg': 50000, 'aniqlik_kg': 0.05})
t_q2 = T.create({'name': "Qadoqlash dozatori — 2-liniya (jamlovchi)", 'kod': 'QDQ-2', 'turi': 'qadoq',
                 'protokol': 'rs485', 'max_vazn_kg': 50000, 'aniqlik_kg': 0.05})
wc1 = env['mrp.workcenter'].create({'name': "Granulyatsiya liniyasi", 'code': 'GR', 'costs_hour': 0})
wc2 = env['mrp.workcenter'].create({'name': "Sochiluvchan yem liniyasi", 'code': 'SCH', 'costs_hour': 0})
Lin = env['agronova.yem.liniya']
L = {1: Lin.create({'name': "1-liniya · granula", 'kod': 'L1', 'quvvat_t_soat': 12, 'workcenter_id': wc1.id,
                    'tarozi_id': t_q1.id}),
     2: Lin.create({'name': "2-liniya · sochiluvchan", 'kod': 'L2', 'quvvat_t_soat': 10, 'workcenter_id': wc2.id,
                    'tarozi_id': t_q2.id})}
SM = env['agronova.yem.smena.turi'].search([], order='sequence')
S1, S2 = SM[0], SM[1]

# Minimum / maksimum (kg; qop — dona)
for code, mn, mx in [('MAKK', 80000, 330000), ('SOYA', 37000, 150000), ('BUGD', 11000, 45000),
                     ('KUNG', 3500, 18000), ('BALQ', 700, 6000), ('MOY', 3700, 14000), ('OHAK', 5000, 25000),
                     ('MKF', 1600, 8000), ('TUZ', 450, 2500), ('LIZ', 200, 1300), ('MET', 210, 1300),
                     ('PRB', 650, 3200), ('PRL', 500, 2600)]:
    env['stock.warehouse.orderpoint'].create({'product_id': X[code].id, 'warehouse_id': wh.id,
                                              'location_id': wh.lot_stock_id.id, 'trigger': 'manual',
                                              'product_min_qty': mn, 'product_max_qty': mx})
for qop, mn, mx in [(QOP40, 5000, 20000), (QOP50, 4000, 15000)]:
    env['stock.warehouse.orderpoint'].create({'product_id': qop.id, 'warehouse_id': wh.id,
                                              'location_id': qadoq_loc.id, 'trigger': 'manual',
                                              'product_min_qty': mn, 'product_max_qty': mx})

# =============================================================== 5. YORDAMCHILAR
Picking = env['stock.picking']


def sana_yoz(records, dt):
    """Hujjat va uning harakatlariga o'tgan sanani yozadi (tasdiqlagandan keyin)."""
    moves = env['stock.move']
    if records._name == 'stock.picking':
        records.write({'date_done': dt, 'scheduled_date': dt, 'date_deadline': dt})
        moves = records.move_ids
    elif records._name == 'mrp.production':
        # Yopilgan buyurtmani ORM «ko'chirishga» qo'ymaydi — demo tarixi uchun SQL.
        env.cr.execute("UPDATE mrp_production SET date_finished = %s WHERE id IN %s",
                       (dt, tuple(records.ids)))
        records.invalidate_recordset(['date_finished'])
        moves = records.move_raw_ids | records.move_finished_ids
    elif records._name == 'stock.move':
        moves = records
    moves.write({'date': dt})
    moves.move_line_ids.write({'date': dt})


def tortish(ticket, brutto, tara, dt, sabab=None):
    """Tarozi agenti ko'rsatkich yuborgandek: 1- va 2-tortish."""
    birinchi, ikkinchi = (brutto, tara) if ticket.yonalish == 'kirim' else (tara, brutto)
    ticket.tarozi_id.vazn_qabul(birinchi)
    ticket.action_vazn1()
    ticket.tarozi_id.vazn_qabul(ikkinchi)
    ticket.action_vazn2()
    if ticket.tafovut in ('tasdiq', 'kritik'):
        ticket.tafovut_sabab = sabab or R.choice([
            "Namlik farqi: laboratoriya 14,8% ko'rsatdi", "Hujjatdagi xato — yetkazib beruvchi bilan solishtirildi",
            "Tentda yomg'ir suvi to'plangan", "Mashina idishida qoldiq bor edi"])
        ticket.action_tafovut_tasdiq()
    ticket.action_yakunlash()
    ticket.write({'sana': dt, 'vazn1_vaqt': dt - timedelta(minutes=R.randint(25, 70)), 'vazn2_vaqt': dt})


def avto_raqam():
    return "%02d %s %03d %s" % (R.choice([40, 50, 60, 30, 10]), R.choice("ABDEKLMNOS"), R.randint(100, 999),
                                 "".join(R.choice("ABCDEFHKLMNOPRSTUX") for _ in range(2)))


HAYDOVCHI = ["Anvar To'xtasinov", "Murod Hakimov", "Shuhrat Ismoilov", "Ravshan Odilov", "Elyor Qosimov",
             "Botir Yo'ldoshev", "Komil Mamatov"]


def xarid(code, kg, kun, soat=10, dest=None):
    """Xarid → tarozi → kirim → faktura."""
    prod = X[code] if code in X else code
    dt = utc(kun, soat, R.randint(0, 50))
    po = env['purchase.order'].create({
        'partner_id': prod.seller_ids[:1].partner_id.id, 'picking_type_id': wh.in_type_id.id,
        'order_line': [(0, 0, {'product_id': prod.id, 'product_qty': kg})],
    })
    po.button_confirm()
    pick = po.picking_ids[:1]
    if dest:
        pick.write({'location_dest_id': dest.id})
        pick.move_ids.write({'location_dest_id': dest.id})
    if prod.uom_id == kg_uom:
        t = env['agronova.tarozi.tortish'].browse(pick.action_agronova_tortish()['res_id'])
        t.write({'avto_raqam': avto_raqam(), 'haydovchi': R.choice(HAYDOVCHI), 'tarozi_id': t_avto.id})
        r = R.random()
        farq = R.randint(-45, 30) if r < 0.82 else (R.choice([-1, 1]) * R.randint(110, 180) if r < 0.95
                                                   else -R.randint(320, 420))
        tara = R.randint(13800, 15600)
        tortish(t, tara + kg + farq, tara, dt)
    else:
        for m in pick.move_ids:
            m.quantity = m.product_uom_qty
            m.picked = True
    pick.with_context(skip_backorder=True, picking_ids_not_to_backorder=pick.ids).button_validate()
    sana_yoz(pick, dt)
    po.write({'date_order': dt, 'date_approve': dt})
    try:
        po.action_create_invoice()
        bill = po.invoice_ids[:1]
        bill.invoice_date = kun
        bill.action_post()
    except Exception as e:  # noqa: BLE001
        log("faktura (xarid):", e)
    return pick


# =============================================================== 6. BOSHLANG'ICH QOLDIQ
log("Boshlang'ich qoldiq (inventarizatsiya)")
boshi = BUGUN - timedelta(days=KUNLAR + 1)
for code, kg in [('MAKK', 150000), ('SOYA', 75000), ('BUGD', 30000), ('KUNG', 15000), ('BALQ', 4000),
                 ('MOY', 6500), ('OHAK', 16000), ('MKF', 4500), ('TUZ', 1600), ('LIZ', 900), ('MET', 700),
                 ('PRB', 2600), ('PRL', 1800)]:
    q = env['stock.quant'].with_context(inventory_mode=True).create({
        'product_id': X[code].id, 'location_id': wh.lot_stock_id.id, 'inventory_quantity': kg})
    q.action_apply_inventory()
for qop, n in [(QOP40, 12000), (QOP50, 8000)]:
    q = env['stock.quant'].with_context(inventory_mode=True).create({
        'product_id': qop.id, 'location_id': qadoq_loc.id, 'inventory_quantity': n})
    q.action_apply_inventory()
env['stock.move'].search([('is_inventory', '=', True)]).write({'date': utc(boshi, 9)})

# Kunlik o'rtacha sarf (kg) — xarid rejasi uchun
REJA_KUNLIK = {'PK5': 9000, 'PK6': 13000, 'PK7': 11000, 'PK2': 10000, 'PK1': 6000}
sarf_kun = {}
for code, kg in REJA_KUNLIK.items():
    for k, v in [(X_code, qty) for X_code, qty in YEMLAR[[y[0] for y in YEMLAR].index(code)][7].items()]:
        sarf_kun[k] = sarf_kun.get(k, 0) + kg * v / 1000.0
YUK = {'MAKK': 28000, 'SOYA': 24000, 'BUGD': 22000, 'KUNG': 18000, 'BALQ': 5000, 'MOY': 6000, 'OHAK': 15000,
       'MKF': 5000, 'TUZ': 2000, 'LIZ': 1000, 'MET': 1000, 'PRB': 2000, 'PRL': 2000}
# Taqdimotda ko'rinsin: tuxum premiksi va metionin oxirgi haftada xarid qilinmagan.
TOXTATILGAN = {'PRL': 17, 'MET': 15}

# =============================================================== 7. KUNLAR
Mrp = env['mrp.production']
Smena = env['agronova.yem.smena']
fg_qoldiq = {c: 0.0 for c in YEM}
statistika = {'mo': 0, 'ogish': 0, 'ortiq': 0, 'kirim': 0, 'jonatma': 0}


def mahsulot_qoldiq(prod, loc):
    return prod.with_context(location=loc.id).qty_available


for i in range(KUNLAR, -1, -1):
    kun = BUGUN - timedelta(days=i)
    bugunmi = i == 0
    log("Kun", kun, "(bugun)" if bugunmi else "")

    # --- 7.1 Xomashyo xaridi: qoldiq 3 kunlik sarfdan kam bo'lsa — mashina keladi
    for code, kunlik in sarf_kun.items():
        if code in TOXTATILGAN and i <= TOXTATILGAN[code]:
            continue
        qoldiq = mahsulot_qoldiq(X[code], wh.lot_stock_id)
        reys = 0
        while qoldiq < kunlik * 8 and reys < 4:
            hajm = int(YUK[code] * R.uniform(0.92, 1.05) / 10) * 10
            xarid(code, hajm, kun, soat=R.choice([8, 9, 10, 11, 14, 15]))
            qoldiq += hajm
            reys += 1
            statistika['kirim'] += 1
    for qop in (QOP40, QOP50):
        if mahsulot_qoldiq(qop, qadoq_loc) < 6000 and not bugunmi:
            xarid(qop, 10000, kun, soat=11, dest=qadoq_loc)

    # --- 7.2 Smena hisobotlari
    smenalar = {}
    for l in (1, 2):
        for s in (S1, S2):
            if bugunmi and s == S2:
                continue
            smenalar[(l, s.id)] = Smena.create({
                'sana': kun, 'smena_turi_id': s.id, 'liniya_id': L[l].id,
                'boshliq_id': boshliqlar[0 if s == S1 else 1].id,
                'ishchi_ids': [(6, 0, [e.id for e in R.sample(ishchilar, 3)])],
            })

    # --- 7.3 Kunlik reja → buyurtmalar
    reja = env['agronova.yem.reja'].create({
        'davr': 'kunlik', 'sana_dan': kun, 'sana_gacha': kun, 'warehouse_id': wh.id,
        'qator_ids': [],
    })
    qatorlar = []
    for code, kg in REJA_KUNLIK.items():
        l = 1 if code in ('PK5', 'PK6', 'PK7') else 2
        hajm = int(kg * R.uniform(0.85, 1.15) / 500) * 500
        # Bitta mahsulot ikki smenaga bo'linadi
        bir = int(hajm * R.uniform(0.45, 0.6) / 500) * 500
        for s, miqdor in ((S1, bir), (S2, hajm - bir)):
            if bugunmi and s == S2:
                continue
            qatorlar.append((0, 0, {'product_id': YEM[code].id, 'miqdor_kg': miqdor, 'muddat': kun,
                                     'liniya_id': L[l].id, 'smena_turi_id': s.id,
                                     'ustuvorlik': '1' if code == 'PK5' else '0'}))
    reja.qator_ids = qatorlar
    reja.action_tasdiqlash()
    reja.with_context(tz='Asia/Tashkent').action_buyurtmalar_yarat()
    mos = reja.qator_ids.mapped('production_ids')

    for mo in mos:
        s = mo.agronova_smena_turi_id
        l = 1 if mo.agronova_liniya_id == L[1] else 2
        smena = smenalar.get((l, s.id))
        boshlanish = utc(kun, s.boshlanish + R.randint(0, 6), R.choice([0, 15, 30, 45]))
        mo.write({'date_start': boshlanish, 'agronova_smena_id': smena.id if smena else False})
        # Bugungi 1-smenaning oxirgi buyurtmasi hali jarayonda qoladi
        if bugunmi and mo == mos.filtered(lambda m: m.agronova_liniya_id == L[1])[-1:]:
            mo.action_assign()
            continue
        mo.action_assign()
        bom_kg = 1000.0
        # Haqiqiy sarf: odatda ±1,2% ichida, ba'zan bitta komponent me'yordan oshadi
        ogish_bormi = R.random() < 0.07
        ogish_komp = R.choice(mo.move_raw_ids.filtered(lambda m: m.product_id.agronova_yem_turi == 'xomashyo')
                              .mapped('product_id').ids) if ogish_bormi else None
        kirim = 0.0
        foiz = mo.bom_id.agronova_yoqotish_foiz
        r = R.random()
        yoq = foiz * (R.uniform(0.62, 0.97) if r < 0.9 else R.uniform(1.35, 1.8))
        rejadagi = {}
        for m in mo.move_raw_ids:
            reja_kg = m.bom_line_id.product_qty * mo.product_qty / bom_kg
            if ogish_komp and m.product_id.id == ogish_komp:
                q = reja_kg * (1 + R.uniform(0.026, 0.045))
            else:
                q = reja_kg * (1 + R.uniform(-0.012, 0.012))
            rejadagi[m.id] = round(q, 1)
            kirim += rejadagi[m.id]
        chiqim = round(kirim * (1 - yoq / 100.0) / 10) * 10
        mo.qty_producing = chiqim
        mo._set_qty_producing()
        for m in mo.move_raw_ids:
            m.quantity = rejadagi[m.id]
            m.picked = True
        if mo.agronova_sarf_ogish:
            mo.agronova_sarf_sabab = R.choice([
                "Makkajo'xori namligi 15,5% — quruq modda bo'yicha me'yorga yetkazildi",
                "Dozator tarozisi kalibrlanmagan — keyingi smenada tuzatildi",
                "Soya shrotining protein miqdori past keldi, texnolog ko'rsatmasi bilan qo'shildi"])
            mo.action_agronova_sarf_tasdiq()
            statistika['ogish'] += 1
        res = mo.with_context(skip_backorder=True, skip_redirection=True).button_mark_done()
        assert mo.state == 'done', (mo.name, res)
        tugash = boshlanish + timedelta(hours=round(mo.product_qty / 1000.0 / L[l].quvvat_t_soat + R.uniform(0.2, 0.6), 2))
        sana_yoz(mo, tugash)
        mo.agronova_yoqotish_ids.write({'sana': tugash})
        statistika['mo'] += 1
        if mo.agronova_ortiqcha_yoqotish_kg > 0.05:
            statistika['ortiq'] += 1
        fg_qoldiq[[c for c, p in YEM.items() if p == mo.product_id][0]] += mo.agronova_miqdor_kg

        # --- qadoqlash: granula mijozlarga qopda, sochiluvchanning bir qismi qopda
        code = [c for c, p in YEM.items() if p == mo.product_id][0]
        ulush = 0.65 if l == 1 else 0.3
        sigim = mo.product_id.agronova_qop_sigim_kg
        qop_soni = int(mo.agronova_miqdor_kg * ulush // sigim)
        if qop_soni:
            qop = mo.product_id.agronova_qop_product_id
            rr = R.random()
            tol = R.uniform(-0.25, 0.3) if rr < 0.9 else R.choice([-1, 1]) * R.uniform(0.7, 1.1)
            netto = qop_soni * sigim * (1 + tol / 100.0)
            brutto = round(netto + qop_soni * qop.agronova_qop_vazn_kg, 2)
            qd = env['agronova.yem.qadoqlash'].create({
                'production_id': mo.id, 'product_id': mo.product_id.id, 'liniya_id': L[l].id,
                'smena_id': smena.id if smena else False, 'qop_product_id': qop.id, 'qop_soni': qop_soni,
                'qop_sigim_kg': sigim, 'qop_vazn_kg': qop.agronova_qop_vazn_kg, 'tarozi_id': L[l].tarozi_id.id,
            })
            L[l].tarozi_id.vazn_qabul(brutto)
            qd.action_tarozidan()
            qd.action_tasdiqlash()
            qd.sana = tugash
            if qd.qop_move_id:
                sana_yoz(qd.qop_move_id, tugash)

    # --- 7.4 To'xtashlar, qo'shimcha yo'qotish, energiya; smenani tasdiqlash
    for (l, sid), smena in smenalar.items():
        s = smena.smena_turi_id
        for _n in range(R.choice([0, 0, 0, 1, 1, 2])):
            sabab, uskuna = R.choice([
                ('uskuna', "Granulyator matritsasi"), ('uskuna', "Bolg'ali tegirmon"), ('elektr', ""),
                ('xomashyo', ""), ('rejali', "Bunker tozalash"), ('qadoq', ""), ('uskuna', "Elevator lentasi")])
            bosh = utc(kun, s.boshlanish + R.randint(1, 9), R.choice([0, 10, 20, 40]))
            env['agronova.yem.toxtash'].create({
                'liniya_id': L[l].id, 'smena_id': smena.id, 'boshlanish': bosh,
                'tugash': bosh + timedelta(minutes=R.choice([12, 20, 25, 35, 45, 60, 90])),
                'sabab': sabab, 'uskuna': uskuna or False, 'masul_id': smena.boshliq_id.id,
            })
        if R.random() < 0.25 and smena.production_ids:
            mo = smena.production_ids[:1]
            y = env['agronova.yem.yoqotish'].create({
                'sana': utc(kun, s.boshlanish + 5), 'production_id': mo.id, 'product_id': mo.product_id.id,
                'liniya_id': L[l].id, 'smena_id': smena.id,
                'turi': R.choice(['tokilish', 'qadoqlash', 'brak', 'namlik']),
                'miqdor_kg': R.choice([25, 40, 55, 80, 120]), 'meyoriy_kg': 30,
                'masul_id': smena.boshliq_id.id, 'dalolatnoma': "DL-%s" % R.randint(100, 999),
                'sabab': R.choice(["Shnek ulanishida to'kilish", "Yirtilgan qoplar qayta qadoqlandi",
                                   "Granula sifati past — qayta ishlashga", "Bunkerda namlangan qism"]),
            })
            y.action_tekshiruvga()
            if not bugunmi or R.random() < 0.5:
                y.action_tasdiqlash()
        fakt_t = smena.fakt_kg / 1000.0
        if fakt_t:
            env['agronova.yem.energiya'].create({
                'sana': kun, 'liniya_id': L[l].id, 'smena_id': smena.id,
                'elektr_kwh': round(fakt_t * R.uniform(31, 40.5) * (1.12 if l == 1 else 0.85), 1),
                'gaz_m3': round(fakt_t * R.uniform(6.5, 8.5), 1) if l == 1 else 0.0,
            })
        if not (bugunmi and s == S1):
            smena.action_tasdiqlash()

    # Avtomatik yo'qotishlar: me'yordan ortig'ini boshliq ko'rib chiqadi
    for y in env['agronova.yem.yoqotish'].search([('state', '=', 'tekshiruvda'), ('avtomatik', '=', True)]):
        if i > 2 or R.random() < 0.3:
            y.sabab = (y.sabab or "") + "\n" + R.choice([
                "Siklonda chang yo'qotishi oshgan — filtr almashtirildi",
                "Granulyatorda konditsionerlash bug'i ko'p berilgan, namlik bug'lanishi",
                "Smena oxirida liniyani bo'shatishda qoldiq"])
            y.action_tasdiqlash()

    # --- 7.5 Jo'natmalar (kechagi va bugungi ishlab chiqarishdan)
    for code, prod in YEM.items():
        mavjud = mahsulot_qoldiq(prod, wh.lot_stock_id)
        if mavjud < 3000:
            continue
        sigim = prod.agronova_qop_sigim_kg
        jonatiladi = mavjud * (R.uniform(0.75, 0.95) if not bugunmi else 0.4)
        bolaklar = []
        if code in ('PK2', 'PK1'):
            bolaklar.append(('ona_tovuq', jonatiladi * 0.7))
            bolaklar.append(('sotuv', jonatiladi * 0.3))
        else:
            bolaklar.append(('boquv', jonatiladi * 0.35))
            bolaklar.append(('sotuv', jonatiladi * 0.65))
        for turi, miqdor in bolaklar:
            while miqdor >= 2000:
                bir = min(miqdor, R.choice([10000, 15000, 20000, 22000]))
                qop_soni = int(bir // sigim) if turi == 'sotuv' else 0
                kg = qop_soni * sigim if qop_soni else int(bir / 10) * 10
                miqdor -= kg
                dt = utc(kun, R.choice([9, 10, 11, 13, 15, 16, 17]), R.randint(0, 55))
                j = env['agronova.yem.jonatma'].create({
                    'turi': turi, 'warehouse_id': wh.id,
                    'partner_id': R.choice(customers).id if turi == 'sotuv' else False,
                    'qabul_location_id': (wh_ot if turi == 'ona_tovuq' else wh_bq).lot_stock_id.id
                    if turi != 'sotuv' else False,
                    'avto_raqam': avto_raqam(), 'haydovchi': R.choice(HAYDOVCHI),
                    'qator_ids': [(0, 0, {'product_id': prod.id, 'qop_soni': qop_soni, 'miqdor_kg': kg,
                                          'narx_kg': prod.list_price if turi == 'sotuv' else 0})],
                })
                j.action_tasdiqlash()
                t = env['agronova.tarozi.tortish'].browse(j.action_tortish()['res_id'])
                t.tarozi_id = t_avto
                rr = R.random()
                farq = R.randint(-35, 40) if rr < 0.85 else R.choice([-1, 1]) * R.randint(60, 160)
                tara = R.randint(13500, 15200)
                # qoplar og'irligi ham yuk bilan tortiladi
                qoplar = qop_soni * prod.agronova_qop_product_id.agronova_qop_vazn_kg
                tortish(t, tara + kg + qoplar + farq, tara, dt + timedelta(minutes=40),
                        sabab="Qop og'irligi va namlik farqi" if abs(farq) > 100 else None)
                # Bugun bitta mashina hali tarozida — ochiq qoladi
                j.action_jonatish()
                j.write({'sana': dt})
                sana_yoz(j.picking_id, dt + timedelta(minutes=50))
                if j.sale_id:
                    j.sale_id.write({'date_order': dt})
                    try:
                        inv = j.sale_id._create_invoices()
                        inv.invoice_date = kun
                        inv.action_post()
                        if R.random() < 0.7 and i > 2:
                            env['account.payment.register'].with_context(
                                active_model='account.move', active_ids=inv.ids).create({
                                    'payment_date': kun + timedelta(days=R.randint(0, 2)),
                                    'amount': inv.amount_total * R.choice([1, 1, 0.5]),
                                })._create_payments()
                    except Exception as e:  # noqa: BLE001
                        log("faktura (sotuv):", e)
                statistika['jonatma'] += 1
    env.cr.commit()

# =============================================================== 8. BUGUNGI JONLI HOLAT
log("Bugungi jonli holat")
# Tarozida turgan mashina (1-tortish qilingan)
po = env['purchase.order'].create({'partner_id': vendors['don'].id, 'picking_type_id': wh.in_type_id.id,
                                   'order_line': [(0, 0, {'product_id': X['MAKK'].id, 'product_qty': 27500})]})
po.button_confirm()
t = env['agronova.tarozi.tortish'].browse(po.picking_ids[:1].action_agronova_tortish()['res_id'])
t.write({'avto_raqam': avto_raqam(), 'haydovchi': R.choice(HAYDOVCHI), 'tarozi_id': t_avto.id})
t_avto.vazn_qabul(42320)
t.action_vazn1()
# Hozir to'xtab turgan liniya
env['agronova.yem.toxtash'].create({
    'liniya_id': L[2].id, 'boshlanish': datetime.utcnow() - timedelta(minutes=35), 'sabab': 'uskuna',
    'uskuna': "Bolg'ali tegirmon podshipnigi", 'masul_id': boshliqlar[0].id,
    'izoh': "Ta'mirlash brigadasi chaqirildi"})

# =============================================================== 9. XARAJATLAR VA ZAXIRA
log("Xarajat taqsimoti va zaxira")
for oy_boshi in sorted({(BUGUN - timedelta(days=d)).replace(day=1) for d in range(KUNLAR + 1)}):
    x = env['agronova.yem.xarajat'].create({'oy': oy_boshi, 'qator_ids': [
        (0, 0, {'kategoriya': 'ish_haqi', 'summa': 186_000_000}),
        (0, 0, {'kategoriya': 'xizmat', 'summa': 24_500_000}),
        (0, 0, {'kategoriya': 'amortizatsiya', 'summa': 38_000_000}),
        (0, 0, {'kategoriya': 'bilvosita', 'summa': 17_800_000}),
    ]})
    x.action_energiyadan()
    try:
        x.action_taqsimlash()
    except Exception as e:  # noqa: BLE001
        log("taqsimot:", e)
env['agronova.yem.zaxira'].action_yangilash()
env.cr.commit()

# =============================================================== 10. TEKSHIRUV
log("Tekshiruv")
done = Mrp.search([('state', '=', 'done'), ('agronova_yem', '=', True)])
kg = sum(done.mapped('agronova_miqdor_kg'))
assert done and kg > 0
assert all(m.agronova_bom_versiya for m in done)
assert sum(done.mapped('agronova_xomashyo_qiymat')) > 0, "FIFO qiymati hisoblanmadi"
pk6 = done.filtered(lambda m: m.product_id == YEM['PK6'])
assert set(pk6.mapped('agronova_bom_versiya')) == {'v2'}
qd = env['agronova.yem.qadoqlash'].search([('state', '=', 'tasdiqlangan')])
assert qd and all(abs(r.netto_kg - (r.brutto_kg - r.qoplar_kg)) < 0.01 for r in qd)
tt = env['agronova.tarozi.tortish'].search([('state', '=', 'done')])
assert all(abs(t.netto - (t.brutto - t.tara)) < 0.01 for t in tt)
assert env['agronova.yem.smena'].search_count([('state', '=', 'tasdiqlangan')]) > 0
z = env['agronova.yem.zaxira'].search([('holat', 'in', ('kritik', 'kam'))])
log("Buyurtmalar: %s · ishlab chiqarildi %.1f t · og'ish tasdiqlangan: %s · me'yordan ortiq yo'qotish: %s"
    % (statistika['mo'], kg / 1000, statistika['ogish'], statistika['ortiq']))
log("Kirim reyslari: %s · jo'natmalar: %s · tortishlar: %s · qadoqlash: %s"
    % (statistika['kirim'], statistika['jonatma'], len(tt), len(qd)))
log("O'rtacha 1 kg tannarx: %.0f so'm · xavfli zaxira: %s"
    % (sum(done.mapped('agronova_toliq_tannarx')) / kg, ", ".join(z.mapped('product_id.name'))))
log("TAYYOR")
