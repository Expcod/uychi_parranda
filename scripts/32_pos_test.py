# -*- coding: utf-8 -*-
"""agronova_pos modulining uchdan-uchgacha sinovi (Odoo shell).

Ishga tushirish:

    echo "exec(open(r'agronova_custom/scripts/32_pos_test.py', \
        encoding='utf-8').read())" | python run_odoo.py shell \
        -c odoo-agronova.conf -d agronova_kassa_test --no-http

MUHIM: kutilayotgan xatolar `with env.cr.savepoint():` ichida chaqiriladi —
aks holda yiqilgan create tranzaksiyani buzib, keyingi tekshiruvlarni ham
noto'g'ri qilib qo'yadi.
"""
from datetime import datetime, timedelta

from odoo import fields
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
    (4, env.ref('point_of_sale.group_pos_manager').id),
    (4, env.ref('agronova_kassa.group_agronova_kassa_menejer').id),
    (4, env.ref('stock.group_stock_manager').id),
    (4, env.ref('stock.group_production_lot').id),
    (4, env.ref('account.group_account_invoice').id),
]})
env = env(user=admin.id)
company = env.company

print("\n=== 0. SOZLASH ===")
kassa = env['agronova.kassa'].search([('company_id', '=', company.id)], limit=1)
tekshir("Kassa mavjud", bool(kassa), kassa.name)

ombor = env['stock.warehouse'].search([('company_id', '=', company.id)], limit=1)
config = env['pos.config'].search([('company_id', '=', company.id)], limit=1)
if not config:
    config = env['pos.config'].create({'name': "Go'sht do'koni"})
config.write({
    'agronova_kassa_id': kassa.id,
    'agronova_fefo': True,
    'agronova_tannarx_nazorati': True,
    'agronova_kredit_nazorati': True,
})
tekshir("POS kassaga bog'landi", config.agronova_kassa_id == kassa)
tekshir("FEFO yoqilgan", config.agronova_fefo)

# Go'sht — kg, lot bilan, yaroqlilik muddati bilan.
gosht = env['product.product'].create({
    'name': 'POS sinov go\'shti (fileʼ)',
    'is_storable': True,
    'tracking': 'lot',
    'use_expiration_date': True,
    'available_in_pos': True,
    'uom_id': env.ref('uom.product_uom_kgm').id,
    'list_price': 34000.0,
    'standard_price': 25000.0,
})
tekshir("Mahsulot lot bilan kuzatiladi", gosht.tracking == 'lot')

joy = config.picking_type_id.default_location_src_id or ombor.lot_stock_id
bugun = fields.Datetime.now()
# Ikkita partiya: biri ertaroq buziladi — FEFO aynan shuni olishi kerak.
lot_eski = env['stock.lot'].create({
    'name': 'POS-ESKI', 'product_id': gosht.id,
    'expiration_date': bugun + timedelta(days=2),
})
lot_yangi = env['stock.lot'].create({
    'name': 'POS-YANGI', 'product_id': gosht.id,
    'expiration_date': bugun + timedelta(days=20),
})
for lot, qty in ((lot_eski, 3.0), (lot_yangi, 50.0)):
    env['stock.quant'].with_context(inventory_mode=True).create({
        'product_id': gosht.id, 'location_id': joy.id,
        'lot_id': lot.id, 'inventory_quantity': qty,
    }).action_apply_inventory()
tekshir("Ombordagi qoldiq to'ldirildi",
        env['stock.quant']._get_available_quantity(gosht, joy) == 53.0)

naqd_usul = config.payment_method_ids.filtered(lambda m: m.type == 'cash')[:1]
tekshir("Naqd to'lov usuli bor", bool(naqd_usul), naqd_usul.name)


def buyurtma_yarat(session, qatorlar, partner=None, tolov_usuli=None,
                   summa=None):
    """POS buyurtmasini yaratib to'laydi va ombor hujjatini ochadi."""
    jami = summa if summa is not None else sum(
        q['qty'] * q['price_unit'] for q in qatorlar)
    order = env['pos.order'].create({
        'session_id': session.id,
        'company_id': company.id,
        'partner_id': partner.id if partner else False,
        'amount_tax': 0.0,
        'amount_total': jami,
        'amount_paid': jami,
        'amount_return': 0.0,
        'lines': [(0, 0, {
            'product_id': q['product_id'],
            'qty': q['qty'],
            'price_unit': q['price_unit'],
            'discount': q.get('discount', 0.0),
            'price_subtotal': q['qty'] * q['price_unit'],
            'price_subtotal_incl': q['qty'] * q['price_unit'],
        }) for q in qatorlar],
    })
    order.add_payment({
        'pos_order_id': order.id,
        'amount': jami,
        'payment_method_id': (tolov_usuli or naqd_usul).id,
    })
    order.action_pos_order_paid()
    order._create_order_picking()
    return order


print("\n=== 1. FEFO — lot avtomat biriktiriladi ===")
session = env['pos.session'].create({'config_id': config.id,
                                     'user_id': admin.id})
session.action_pos_session_open()
tekshir("Smena ochildi", session.state in ('opened', 'opening_control'),
        session.state)

order = buyurtma_yarat(session, [
    {'product_id': gosht.id, 'qty': 2.0, 'price_unit': 34000.0},
])
picking = order.picking_ids[:1]
tekshir("Ombor hujjati yaratildi", bool(picking))
tekshir("Ombor hujjati YAKUNLANDI (jimgina ochiq qolmadi)",
        picking.state == 'done', picking.state)
satrlar = picking.move_ids.move_line_ids
tekshir("Lot avtomat biriktirildi", all(s.lot_id for s in satrlar))
tekshir("FEFO: muddati oldin tugaydigan partiya olindi",
        satrlar.lot_id == lot_eski, satrlar.lot_id.mapped('name'))
tekshir("Kassir lot terishi shart bo'lmadi",
        not order.lines.pack_lot_ids)

print("\n=== 2. FEFO — bir necha partiyaga bo'linadi ===")
order2 = buyurtma_yarat(session, [
    {'product_id': gosht.id, 'qty': 5.0, 'price_unit': 34000.0},
])
satrlar2 = order2.picking_ids.move_ids.move_line_ids
tekshir("Ikkinchi sotuv ham yakunlandi",
        order2.picking_ids[:1].state == 'done')
lotlar = {s.lot_id.name: s.quantity for s in satrlar2}
tekshir("Eski partiyaning qoldig'i to'liq ishlatildi",
        abs(lotlar.get('POS-ESKI', 0) - 1.0) < 0.001, lotlar)
tekshir("Qolgani yangi partiyadan olindi",
        abs(lotlar.get('POS-YANGI', 0) - 4.0) < 0.001, lotlar)

print("\n=== 3. FEFO — zaxira yetmasa sotuv to'xtamaydi ===")
order3 = buyurtma_yarat(session, [
    {'product_id': gosht.id, 'qty': 100.0, 'price_unit': 34000.0},
])
picking3 = order3.picking_ids[:1]
tekshir("Zaxiradan ko'p sotilsa ham hujjat yopildi",
        picking3.state == 'done', picking3.state)
xabarlar = picking3.message_ids.mapped('body')
tekshir("Ogohlantirish yozildi (qoldiq manfiyga tushdi)",
        any('yetmadi' in (x or '') for x in xabarlar))
qoldiq = sum(env['stock.quant'].search([
    ('product_id', '=', gosht.id), ('location_id', 'child_of', joy.id),
]).mapped('quantity'))
tekshir("Qoldiq manfiy bo'lib ko'rinadi (yashirilmadi)", qoldiq < 0, qoldiq)

print("\n=== 4. TANNARXDAN PAST SOTUV TAQIQI (TZ M08) ===")
xato = env['pos.order'].agronova_tekshir(config.id, [{
    'product_id': gosht.id, 'price_unit': 34000.0,
    'discount': 50.0, 'qty': 1.0,
}])
tekshir("Chegirma tannarxdan pastga tushsa ushlanadi", bool(xato),
        (xato or '').split('\n')[0][:60])
yaxshi = env['pos.order'].agronova_tekshir(config.id, [{
    'product_id': gosht.id, 'price_unit': 34000.0,
    'discount': 10.0, 'qty': 1.0,
}])
tekshir("Tannarxdan yuqori sotuvga ruxsat", not yaxshi)

tannarxsiz = env['product.product'].create({
    'name': 'Tannarxsiz mahsulot', 'is_storable': True,
    'standard_price': 0.0, 'list_price': 1000.0,
})
tekshir("Tannarxi 0 mahsulot savdoni to'xtatmaydi",
        not env['pos.order'].agronova_tekshir(config.id, [{
            'product_id': tannarxsiz.id, 'price_unit': 1.0,
            'discount': 0.0, 'qty': 1.0}]))

xato_kutamiz("Sinxronlashda ham ushlanadi (oflayn POS uchun)",
             lambda: env['pos.order']._agronova_kirish_tekshiruvi({
                 'session_id': session.id, 'state': 'paid',
                 'lines': [(0, 0, {'product_id': gosht.id, 'qty': 1.0,
                                   'price_unit': 34000.0, 'discount': 50.0})],
             }))

config.agronova_tannarx_nazorati = False
tekshir("Nazorat o'chirilsa tekshirilmaydi",
        not env['pos.order'].agronova_tekshir(config.id, [{
            'product_id': gosht.id, 'price_unit': 1.0,
            'discount': 0.0, 'qty': 1.0}]))
config.agronova_tannarx_nazorati = True

print("\n=== 5. KREDIT LIMITI (TZ M08) ===")
mijoz = env['res.partner'].create({
    'name': 'POS sinov mijozi', 'credit_limit': 500_000.0,
})
qarz_usul = config.payment_method_ids.filtered(
    lambda m: m.type == 'pay_later')[:1]
if not qarz_usul:
    qarz_usul = env['pos.payment.method'].create({
        'name': 'Qarzga (mijoz hisobi)',
        'company_id': company.id,
        'split_transactions': True,
    })
    config.payment_method_ids = [(4, qarz_usul.id)]
tekshir("«Keyin to'lash» usuli bor", qarz_usul.type == 'pay_later',
        qarz_usul.type)

xato = env['pos.order'].agronova_tekshir(
    config.id, [], partner_id=mijoz.id, qarz_summa=600_000.0)
tekshir("Limitdan oshgan qarz bloklanadi", bool(xato),
        (xato or '').split('\n')[0][:60])
tekshir("Limit ichidagi qarzga ruxsat",
        not env['pos.order'].agronova_tekshir(
            config.id, [], partner_id=mijoz.id, qarz_summa=100_000.0))
limitsiz = env['res.partner'].create({'name': 'Limitsiz mijoz'})
tekshir("Limiti yo'q mijoz tekshirilmaydi",
        not env['pos.order'].agronova_tekshir(
            config.id, [], partner_id=limitsiz.id, qarz_summa=99_000_000.0))

print("\n=== 6. SMENA → KASSA KITOBI (TZ M04) ===")
kassa_oldin = kassa.balance
naqd_jami = sum(session.order_ids.payment_ids.filtered(
    lambda p: p.payment_method_id.is_cash_count).mapped('amount'))
# `action_pos_session_closing_control` naqd nazorati yo'q bo'lsa
# smenani o'zi yopib yuboradi — ikkinchi marta chaqirilmasin.
session.action_pos_session_closing_control()
if session.state != 'closed':
    session.action_pos_session_close()
tekshir("Smena yopildi", session.state == 'closed', session.state)

yozuv = env['agronova.kassa.harakat'].search([
    ('pos_session_id', '=', session.id)], limit=1)
tekshir("Kassa kitobiga yozuv tushdi", bool(yozuv), yozuv.name)
tekshir("Yozuv KIRIM", yozuv.direction == 'in')
tekshir("Summa smena naqdiga teng",
        abs(yozuv.amount - naqd_jami) < 1.0,
        "%s / %s" % (yozuv.amount, naqd_jami))
tekshir("Manba — POS", yozuv.manba == 'pos')
tekshir("Avtomatik yozuv (qo'lda tahrirlanmaydi)", yozuv.auto)
tekshir("Provodka TAKRORLANMADI (smena o'zi yozgan)", not yozuv.move_id)
tekshir("Kassa qoldig'i oshdi",
        abs(kassa.balance - kassa_oldin - naqd_jami) < 1.0,
        kassa.balance)
tekshir("Yozuv kassa kitobining varag'iga bog'landi", bool(yozuv.kun_id))
tekshir("Manba hujjat — smenaning o'zi",
        bool(yozuv) and yozuv.action_open_source()['res_model'] == 'pos.session')
xato_kutamiz("POS yozuvini kassir qo'lda storno qila olmaydi",
             lambda: yozuv.action_storno(sabab='Sinov'))

soni = env['agronova.kassa.harakat'].search_count(
    [('pos_session_id', '=', session.id)])
session._agronova_kassaga_yozish()
tekshir("Qayta chaqirilsa ikkinchi yozuv yaratilmaydi",
        env['agronova.kassa.harakat'].search_count(
            [('pos_session_id', '=', session.id)]) == soni, soni)

print("\n=== 7. KASSASIZ POS ===")
config2 = config.copy({'name': 'Kassasiz do\'kon', 'agronova_kassa_id': False})
sessiya2 = env['pos.session'].create({'config_id': config2.id,
                                      'user_id': admin.id})
tekshir("Kassa bog'lanmagan POS ham ishlaydi",
        sessiya2._agronova_kassaga_yozish() is False)

print("\n=== 8. TAROZI SHTRIX KODI ===")
# Odooning standart qoidasi — modul hech narsa qo'shmaydi.
qoida = env['barcode.rule'].search([
    ('type', '=', 'weight'), ('encoding', '=', 'ean13')], limit=1)
tekshir("Standart vazn qoidasi mavjud", bool(qoida), qoida.name)
tekshir("Shablon tarozi formatida", qoida.pattern == '21.....{NNDDD}',
        qoida.pattern)
tekshir("Dublikat qoida qo'shilmadi",
        env['barcode.rule'].search_count([
            ('type', '=', 'weight'), ('encoding', '=', 'ean13')]) == 1)
nom = env.ref('barcodes.default_barcode_nomenclature')
# 21 + 00123 (mahsulot) + 01500 (1.500 kg) + 9 (nazorat raqami)
natija = nom.parse_barcode('2100123015009')
tekshir("Vaznli barcode o'qildi",
        isinstance(natija, dict) and natija.get('type') == 'weight',
        natija.get('type') if isinstance(natija, dict) else natija)
tekshir("Vazn to'g'ri ajratildi (1.5 kg)",
        isinstance(natija, dict) and abs(natija.get('value', 0) - 1.5) < 0.001,
        natija.get('value') if isinstance(natija, dict) else '')

print("\n" + "=" * 60)
print("NATIJA: %d ta o'tdi, %d ta yiqildi" % (len(OK), len(FAIL)))
if FAIL:
    print("YIQILGANLAR:")
    for f in FAIL:
        print("  - " + f)
print("=" * 60)
env.cr.rollback()
