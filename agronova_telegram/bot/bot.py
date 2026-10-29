#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AgroNova — Telegram boti (aiogram 3).

Odoo dan mustaqil jarayon sifatida ishlaydi va u bilan XML-RPC orqali
gaplashadi. Butun biznes mantiq Odoo tomonida (`agronova_telegram` moduli,
kunlik jurnal esa `agronova.jurnal.bot` da), bu yerda faqat suhbat oqimi.

## Tugmalar pastda

Barcha tugmalar — bosh menyu ham, tanlovlar ham, «Orqaga» ham —
xabarning ichida emas, klaviatura o'rnida (ReplyKeyboard) chiqadi.
Telefonda barmoq shu yerda turadi, xabarlar oqimi esa toza qoladi:
eski xabarlarga qaytib tugma qidirish kerak emas.

Buning bir narxi bor: javob **matn** bo'lib keladi, ya'ni yorliqni
qiymatga qaytarish kerak. Shuning uchun har tanlovda `{yorliq: qiymat}`
lug'ati FSM holatiga yoziladi va javob shu bo'yicha o'qiladi.

Ishga tushirish:
    python bot.py --url https://demo.novaodoo.uz --db agronova_demo \\
                  --user agronova_demo --key <API_KEY> --token <BOT_TOKEN>

Yoki muhit o'zgaruvchilari orqali: AGRONOVA_URL, AGRONOVA_DB, AGRONOVA_USER, AGRONOVA_KEY,
AGRONOVA_BOT_TOKEN
"""
import argparse
import asyncio
import base64
import logging
import os
import ssl
import xmlrpc.client

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from aiogram.utils.keyboard import ReplyKeyboardBuilder

logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s', level=logging.INFO)
_log = logging.getLogger('agronova_bot')

# Bosh menyu va «Orqaga» tugmalari har qanday holatdan ustun turishi
# kerak: savolga javob kutayotgan handler ularni javob deb qabul qilib
# yubormasin. Aiogram routerlarni ro'yxatga olingan tartibda ko'radi,
# shuning uchun ular alohida — birinchi ulanadigan — routerda.
menyu_router = Router()
router = Router()


class Register(StatesGroup):
    """Botga ulanish arizasi: ism-familiya so'raladi, keyin jo'natiladi."""
    ism = State()
    tasdiq = State()


class Jurnal(StatesGroup):
    """Kunlik jurnalni to'ldirish: obyekt -> savol-javob -> tasdiq."""
    obyekt = State()
    javob = State()
    tasdiq = State()


class Arrive(StatesGroup):
    """«Yetib keldim»: qaysi reys."""
    trip = State()


class Expense(StatesGroup):
    """Xarajat kiritish suhbati."""
    trip = State()
    product = State()
    amount = State()
    photo = State()


class Odoo:
    """XML-RPC yordamchisi.

    `xmlrpc.client` blokirovka qiladigan kutubxona, shuning uchun har bir
    chaqiruv alohida oqimda bajariladi — bot sikli to'xtab qolmaydi.
    """

    def __init__(self, url, db, user, key, verify_ssl=True):
        self.db, self.key = db, key
        ctx = None if verify_ssl else ssl._create_unverified_context()
        common = xmlrpc.client.ServerProxy(url + '/xmlrpc/2/common', context=ctx)
        self.uid = common.authenticate(db, user, key, {})
        if not self.uid:
            raise SystemExit("Odoo ga ulanib bo'lmadi — user yoki API key noto'g'ri.")
        self.models = xmlrpc.client.ServerProxy(
            url + '/xmlrpc/2/object', context=ctx, allow_none=True)
        _log.info("Odoo ga ulandi: %s (uid=%s)", db, self.uid)

    # XML-RPC faqat 32-bitli butun sonni ko'taradi. Telegram chat va xabar
    # ID lari bundan katta bo'lishi mumkin — ular satr sifatida uzatiladi.
    INT32_MAX = 2 ** 31 - 1

    @classmethod
    def _safe(cls, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, int) and abs(value) > cls.INT32_MAX:
            return str(value)
        if isinstance(value, (list, tuple)):
            return [cls._safe(v) for v in value]
        if isinstance(value, dict):
            return {k: cls._safe(v) for k, v in value.items()}
        return value

    def _call(self, model, method, *args, **kw):
        return self.models.execute_kw(
            self.db, self.uid, self.key, model, method,
            [self._safe(a) for a in args], self._safe(kw))

    async def call(self, model, method, *args, **kw):
        return await asyncio.to_thread(self._call, model, method, *args, **kw)


def son(v):
    """1234567.0 -> '1 234 567'"""
    return "{:,.0f}".format(v or 0).replace(",", " ")


# ------------------------------------------------------------------ tugmalar
JURNAL = "📋 Kunlik jurnal"
KELDIM = "📍 Yetib keldim"
XARAJAT = "💸 Xarajat kiritish"
REYSLAR = "🚛 Mening reyslarim"
HISOB = "💰 Hisob-kitobim"
ORQAGA = "⬅️ Orqaga"
SAQLA = "✅ Saqlash"
BOSHIDAN = "🔄 Boshidan"
JONAT = "✅ Jo'natish"
QAYTA_YOZ = "✏️ Qayta yozish"

MENYU = [JURNAL, KELDIM, XARAJAT, REYSLAR, HISOB]

TANLANG = "Pastdagi tugmalardan birini tanlang."


def _klaviatura(tugmalar):
    kb = ReplyKeyboardBuilder()
    for t in tugmalar:
        kb.button(text=t[:64])
    kb.adjust(1)
    return kb.as_markup(resize_keyboard=True, is_persistent=True)


def menu():
    """Bosh menyu — doim pastda turadi."""
    return _klaviatura(MENYU)


def tanlov_kb(yorliqlar):
    """Tanlov ro'yxati + «Orqaga»."""
    return _klaviatura(list(yorliqlar) + [ORQAGA])


def orqaga_kb():
    """Erkin javob kutilayotganda: faqat «Orqaga»."""
    return _klaviatura([ORQAGA])


SORAB = ("Botdan foydalanish uchun avval ro'yxatdan o'tasiz.\n\n"
         "<b>Ism va familiyangizni</b> yozib yuboring:")

KUTILMOQDA = ("Arizangiz yuborilgan, ko'rib chiqilmoqda.\n\n"
              "Siz yozgan ism: <b>%s</b>\n\n"
              "Biriktirilgandan keyin /start bosing. Ismni o'zgartirish "
              "kerak bo'lsa /qayta yozing.")

RAD = ("Arizangiz rad etilgan.\n\n"
       "Ism-familiyangizni qaytadan yozib yuboring:")

NOT_LINKED = "Akkauntingiz hali biriktirilmagan. /start bosing."


async def not_linked(message, res):
    """Javob bog'lanmaganlikni bildirsa — /start ga yo'naltiradi.

    Ro'yxatdan o'tish oqimi /start da, shuning uchun bu yerda takrorlanmaydi.
    True qaytsa, handler ishini to'xtatadi.
    """
    if isinstance(res, dict) and res.get('not_linked'):
        await message.answer(NOT_LINKED)
        return True
    return False


async def bosh_menyu(message, state, matn="Bosh menyu."):
    await state.clear()
    await message.answer(matn, reply_markup=menu())


# --------------------------------------------------------------------- /start
@router.message(CommandStart())
async def start(message: Message, state: FSMContext, odoo: Odoo):
    await state.clear()
    who = await odoo.call('hr.employee', 'tg_whoami', str(message.chat.id),
                          message.from_user.username or '')
    if who.get('ok'):
        await message.answer(
            "Assalomu alaykum, <b>%s</b>!\nLavozim: %s"
            % (who['name'], who.get('job') or '-'), reply_markup=menu())
        return

    # Biriktirilmagan. Ariza allaqachon tushgan bo'lsa qayta so'ramaymiz.
    holat = who.get('ariza_holati')
    if holat == 'yangi':
        res = await odoo.call('agronova.telegram.request', 'tg_holat',
                              str(message.chat.id))
        await message.answer(KUTILMOQDA % (res.get('ism') or '-'))
        return
    await message.answer("Assalomu alaykum!\n\n"
                         + (RAD if holat == 'rad' else SORAB))
    await state.set_state(Register.ism)


@router.message(Command("qayta"))
async def qayta(message: Message, state: FSMContext):
    """Ismni noto'g'ri yozgan bo'lsa qaytadan kiritadi."""
    await state.clear()
    await message.answer(SORAB)
    await state.set_state(Register.ism)


@router.message(Register.ism, F.text)
async def register_ism(message: Message, state: FSMContext):
    ism = (message.text or "").strip()
    if len(ism) < 3:
        await message.answer(
            "Ism juda qisqa. To'liq ism-familiyangizni yozing:")
        return
    await state.update_data(ism=ism)
    await state.set_state(Register.tasdiq)
    await message.answer("Shu ma'lumot jo'natilsinmi?\n\n<b>%s</b>" % ism,
                         reply_markup=_klaviatura([JONAT, QAYTA_YOZ]))


@router.message(Register.tasdiq, F.text == QAYTA_YOZ)
async def register_again(message: Message, state: FSMContext):
    await state.set_state(Register.ism)
    await message.answer(SORAB)


@router.message(Register.tasdiq, F.text == JONAT)
async def register_send(message: Message, state: FSMContext, odoo: Odoo):
    data = await state.get_data()
    ism = data.get('ism')
    if not ism:
        await state.set_state(Register.ism)
        await message.answer(SORAB)
        return
    u = message.from_user
    # Telegram profildagi ism ham yuboriladi: administrator xodim yozgan
    # ism bilan solishtirib ko'radi.
    tg_ism = " ".join(x for x in (u.first_name, u.last_name) if x)
    res = await odoo.call('agronova.telegram.request', 'tg_register',
                          str(message.chat.id), ism, u.username or '', tg_ism)
    await state.clear()
    if res.get('holat') == 'biriktirilgan':
        await message.answer("Siz allaqachon biriktirilgansiz. /start bosing.")
        return
    await message.answer(
        "Arizangiz yuborildi.\n\n<b>%s</b>\n\n"
        "Administrator sizni xodimga biriktirgandan keyin /start bosing."
        % ism)


@router.message(Register.tasdiq, F.text)
async def register_tasdiq_boshqa(message: Message):
    await message.answer(TANLANG)


@router.message(Command("id"))
async def show_id(message: Message):
    await message.answer("Sizning chat ID: <code>%s</code>" % message.chat.id)


# --------------------------------------------------------- orqaga va bekor
@menyu_router.message(F.text == ORQAGA)
async def orqaga(message: Message, state: FSMContext):
    """Har qanday suhbatni to'xtatib bosh menyuga qaytaradi."""
    await bosh_menyu(message, state)


@menyu_router.message(Command("bekor"))
async def cancel_cmd(message: Message, state: FSMContext):
    await bosh_menyu(message, state, "Bekor qilindi.")


# ------------------------------------------------------- kunlik jurnal
# Savollarni Odoo beradi: bot faqat so'raydi, javobni saqlaydi va
# keyingisini so'raydi. Shunda jurnalga maydon qo'shilsa bot o'zgarmaydi.

async def jurnal_savol(message, state: FSMContext, odoo: Odoo, javoblar=None):
    """Keyingi savolni so'raydi yoki tasdiqlash tugmasini chiqaradi."""
    data = await state.get_data()
    res = await odoo.call('agronova.jurnal.bot', 'tg_jurnal_keyingi',
                          str(message.chat.id), data['kod'], data['tur'],
                          data['obyekt_id'],
                          javoblar if javoblar is not None
                          else data.get('javoblar', {}))
    if await not_linked(message, res):
        await state.clear()
        return
    if res.get('xato'):
        # Javoblar bir-biriga zid — o'sha savolni qaytadan so'raymiz.
        javoblar = dict(data.get('javoblar', {}))
        javoblar.pop(res['qayta_kalit'], None)
        await state.update_data(javoblar=javoblar)
        await message.answer("⚠️ %s\n\nQaytadan kiriting." % res['xato'])
        await jurnal_savol(message, state, odoo, javoblar)
        return
    if res.get('tugadi'):
        await state.update_data(javoblar=res['javoblar'])
        await state.set_state(Jurnal.tasdiq)
        await message.answer(
            "Kiritilgan ma'lumot:\n\n%s\n\nSaqlaymizmi?" % res['xulosa'],
            reply_markup=_klaviatura([SAQLA, BOSHIDAN, ORQAGA]))
        return

    await state.update_data(javoblar=res['javoblar'], kalit=res['kalit'],
                            savol_turi=res['tur'])
    matn = "<b>%s</b>" % res['savol']
    if res.get('yordam'):
        matn += "\n<i>%s</i>" % res['yordam']

    if res['tur'] == 'tanlov' and res.get('tanlovlar'):
        # Ro'yxatdan tanlanadigan savol: qo'lda yozdirmaymiz — imlo xatosi
        # bilan yozilsa hisobotda guruhlab bo'lmaydi. Yorliq pastdagi
        # tugmada chiqadi, javob esa matn bo'lib qaytadi — shuning uchun
        # yorliqni qiymatga qaytaruvchi lug'at holatda saqlanadi.
        xarita = {t['yorliq'][:64]: t['qiymat'] for t in res['tanlovlar']}
        await state.update_data(tanlov_xarita=xarita)
        await state.set_state(Jurnal.javob)
        await message.answer(matn, reply_markup=tanlov_kb(xarita))
        return

    await state.update_data(tanlov_xarita={})
    await state.set_state(Jurnal.javob)
    await message.answer(matn, reply_markup=orqaga_kb())


@menyu_router.message(F.text == JURNAL)
async def jurnal_start(message: Message, state: FSMContext, odoo: Odoo):
    await state.clear()
    res = await odoo.call('agronova.jurnal.bot', 'tg_jurnal_royxat',
                          str(message.chat.id))
    if await not_linked(message, res):
        return
    obyektlar = res.get('obyektlar') or []
    if not obyektlar:
        await message.answer("Sizga biriktirilgan faol partiya yo'q.",
                             reply_markup=menu())
        return

    ochiq = [o for o in obyektlar if not o['bugun_toldirilgan']]
    if not ochiq:
        await message.answer(
            "Bugungi jurnal hamma partiya uchun to'ldirilgan. Rahmat!",
            reply_markup=menu())
        return

    # Yorliqni Odoo yasaydi — joyni qanday atash bo'limga bog'liq.
    # Eski provayderlar uchun zaxira variant qoldirilgan.
    xarita = {}
    for o in ochiq:
        yorliq = (o.get('yorliq')
                  or "%s · %s bosh" % (o['joy'], o['bosh_soni']))[:64]
        xarita[yorliq] = [o['kod'], o['tur'], o['obyekt_id']]
    await state.update_data(obyekt_xarita=xarita)
    await state.set_state(Jurnal.obyekt)
    await message.answer("Qaysi joy uchun bugungi jurnalni to'ldiramiz?",
                         reply_markup=tanlov_kb(xarita))


@router.message(Jurnal.obyekt, F.text)
async def jurnal_obyekt(message: Message, state: FSMContext, odoo: Odoo):
    data = await state.get_data()
    xarita = data.get('obyekt_xarita') or {}
    tanlangan = xarita.get((message.text or "").strip())
    if not tanlangan:
        await message.answer(TANLANG, reply_markup=tanlov_kb(xarita))
        return
    kod, tur, obyekt_id = tanlangan
    await state.set_data({'kod': kod, 'tur': tur,
                          'obyekt_id': int(obyekt_id), 'javoblar': {}})
    await message.answer(
        "Savollarga bittalab javob bering. To'xtatish uchun «%s»." % ORQAGA,
        reply_markup=orqaga_kb())
    await jurnal_savol(message, state, odoo, {})


@router.message(Jurnal.javob, F.text)
async def jurnal_javob(message: Message, state: FSMContext, odoo: Odoo):
    data = await state.get_data()
    matn = (message.text or "").strip()
    tur = data.get('savol_turi')

    if tur == 'tanlov':
        xarita = data.get('tanlov_xarita') or {}
        if matn not in xarita:
            await message.answer(TANLANG, reply_markup=tanlov_kb(xarita))
            return
        qiymat = xarita[matn]
    elif tur in ('int', 'float'):
        # `1 200` yoki `1,5` kabi yozuvlar ham qabul qilinsin.
        tozalangan = matn.replace(" ", "").replace(",", ".")
        try:
            qiymat = float(tozalangan)
        except ValueError:
            await message.answer("Raqam kiriting. Masalan: 12")
            return
        if qiymat < 0:
            await message.answer("Manfiy son bo'lmaydi.")
            return
        qiymat = int(qiymat) if tur == 'int' else qiymat
    else:
        qiymat = matn

    javoblar = dict(data.get('javoblar', {}))
    javoblar[data['kalit']] = qiymat
    await state.update_data(javoblar=javoblar)
    await jurnal_savol(message, state, odoo, javoblar)


@router.message(Jurnal.tasdiq, F.text == BOSHIDAN)
async def jurnal_qayta(message: Message, state: FSMContext, odoo: Odoo):
    await state.update_data(javoblar={})
    await message.answer("Boshidan boshlaymiz.", reply_markup=orqaga_kb())
    await jurnal_savol(message, state, odoo, {})


@router.message(Jurnal.tasdiq, F.text == SAQLA)
async def jurnal_saqla(message: Message, state: FSMContext, odoo: Odoo):
    data = await state.get_data()
    res = await odoo.call('agronova.jurnal.bot', 'tg_jurnal_saqlash',
                          str(message.chat.id), data['kod'], data['tur'],
                          data['obyekt_id'], data.get('javoblar', {}))
    if await not_linked(message, res):
        await state.clear()
        return
    await state.clear()
    if not res.get('ok'):
        await message.answer("⚠️ %s" % res.get('error', "Saqlanmadi."),
                             reply_markup=menu())
        return
    matn = ("✅ Jurnal saqlandi.\n\n<b>%s</b> · %s\nKun oxiridagi bosh soni: %s"
            % (res['partiya'], res['sana'], res['kun_oxiri']))
    if res.get('ogohlantirish'):
        matn += "\n\n⚠️ %s" % res['ogohlantirish']
    matn += "\n\nSex boshlig'i ko'rib tasdiqlaydi."
    await message.answer(matn, reply_markup=menu())


@router.message(Jurnal.tasdiq, F.text)
async def jurnal_tasdiq_boshqa(message: Message):
    await message.answer(TANLANG)


# ------------------------------------------------------------------- reyslar
@menyu_router.message(F.text == REYSLAR)
async def show_trips(message: Message, state: FSMContext, odoo: Odoo):
    await state.clear()
    res = await odoo.call('agronova.trip', 'tg_open_trips', str(message.chat.id))
    if await not_linked(message, res):
        return
    trips = res.get('trips') or []
    if not trips:
        await message.answer("Sizda ochiq reys yo'q.", reply_markup=menu())
        return
    lines = ["🚛 <b>Ochiq reyslaringiz</b>\n"]
    for t in trips:
        lines.append("<b>%s</b>  %s\n%s\n%s · xarajat: %s so'm\n"
                     % (t['name'], t['date'], t['route'], t['state'],
                        son(t['expense_total'])))
    await message.answer("\n".join(lines), reply_markup=menu())


@menyu_router.message(F.text == HISOB)
async def show_balance(message: Message, state: FSMContext, odoo: Odoo):
    await state.clear()
    b = await odoo.call('agronova.trip', 'tg_driver_balance', str(message.chat.id))
    if await not_linked(message, b):
        return
    await message.answer(
        "💰 <b>%s</b>\n\nOchiq reyslar: %s ta\nJami xarajat: %s so'm\n"
        "Hisoblangan ulush: %s so'm\nTopshirilishi kerak: %s so'm"
        % (b['name'], b['trip_count'], son(b['expense_total']),
           son(b['driver_share']), son(b['balance_due'])),
        reply_markup=menu())


# --------------------------------------------------------------- yetib keldim
def _reys_xarita(trips):
    return {("%s · %s" % (t['name'], t['route']))[:64]: t['id'] for t in trips}


@menyu_router.message(F.text == KELDIM)
async def arrived_start(message: Message, state: FSMContext, odoo: Odoo):
    await state.clear()
    res = await odoo.call('agronova.trip', 'tg_arrivable_trips',
                          str(message.chat.id))
    if await not_linked(message, res):
        return
    trips = res.get('trips') or []
    if not trips:
        await message.answer("Yo'ldagi reysingiz yo'q.", reply_markup=menu())
        return
    xarita = _reys_xarita(trips)
    await state.update_data(reys_xarita=xarita)
    await state.set_state(Arrive.trip)
    await message.answer("Qaysi reysga yetib keldingiz?",
                         reply_markup=tanlov_kb(xarita))


@router.message(Arrive.trip, F.text)
async def mark_arrived(message: Message, state: FSMContext, odoo: Odoo):
    data = await state.get_data()
    xarita = data.get('reys_xarita') or {}
    trip_id = xarita.get((message.text or "").strip())
    if not trip_id:
        await message.answer(TANLANG, reply_markup=tanlov_kb(xarita))
        return
    res = await odoo.call('agronova.trip', 'tg_mark_delivered',
                          str(message.chat.id), trip_id)
    await state.clear()
    if await not_linked(message, res):
        return
    if not res.get('ok'):
        await message.answer("❌ %s" % res.get('error'), reply_markup=menu())
        return
    await message.answer(
        "✅ Qabul qilindi\n\n<b>%s</b>\n%s\nHolat: %s\nVaqt: <b>%s</b>"
        % (res['name'], res['route'], res['state'], res['time']),
        reply_markup=menu())


# ------------------------------------------------------------------- xarajat
@menyu_router.message(F.text == XARAJAT)
async def expense_start(message: Message, state: FSMContext, odoo: Odoo):
    await state.clear()
    res = await odoo.call('agronova.trip', 'tg_open_trips', str(message.chat.id))
    if await not_linked(message, res):
        return
    trips = res.get('trips') or []
    if not trips:
        await message.answer("Ochiq reysingiz yo'q — xarajat kiritib bo'lmaydi.",
                             reply_markup=menu())
        return
    xarita = _reys_xarita(trips)
    await state.update_data(reys_xarita=xarita)
    await state.set_state(Expense.trip)
    await message.answer("Qaysi reysga?", reply_markup=tanlov_kb(xarita))


@router.message(Expense.trip, F.text)
async def pick_trip(message: Message, state: FSMContext, odoo: Odoo):
    data = await state.get_data()
    xarita = data.get('reys_xarita') or {}
    trip_id = xarita.get((message.text or "").strip())
    if not trip_id:
        await message.answer(TANLANG, reply_markup=tanlov_kb(xarita))
        return
    await state.update_data(trip_id=trip_id)
    products = await odoo.call('hr.expense', 'tg_expense_products')
    tur_xarita = {p['name'][:64]: p['id'] for p in products}
    await state.update_data(tur_xarita=tur_xarita)
    await state.set_state(Expense.product)
    await message.answer("Xarajat turi?", reply_markup=tanlov_kb(tur_xarita))


@router.message(Expense.product, F.text)
async def pick_product(message: Message, state: FSMContext):
    data = await state.get_data()
    xarita = data.get('tur_xarita') or {}
    product_id = xarita.get((message.text or "").strip())
    if not product_id:
        await message.answer(TANLANG, reply_markup=tanlov_kb(xarita))
        return
    await state.update_data(product_id=product_id)
    await state.set_state(Expense.amount)
    await message.answer("Summani yozing (faqat raqam, so'mda):",
                         reply_markup=orqaga_kb())


@router.message(Expense.amount, F.text)
async def ask_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(' ', '').replace(',', '.'))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Summa noto'g'ri. Faqat raqam yozing:")
        return
    await state.update_data(amount=amount)
    await state.set_state(Expense.photo)
    await message.answer(
        "Endi <b>chek rasmini</b> yuboring.\n"
        "Chek bo'lmasa xarajat qabul qilinmaydi.", reply_markup=orqaga_kb())


@router.message(Expense.photo, F.photo)
async def ask_photo(message: Message, state: FSMContext, odoo: Odoo, bot: Bot):
    photo = message.photo[-1]                    # eng katta o'lchamdagisi
    buf = await bot.download(photo)
    data = await state.get_data()

    res = await odoo.call(
        'hr.expense', 'tg_create_expense',
        str(message.chat.id), data['trip_id'], data['product_id'],
        data['amount'], message.caption or '',
        base64.b64encode(buf.read()).decode(),
        'chek_%s.jpg' % photo.file_unique_id,
    )
    await state.clear()
    if await not_linked(message, res):
        return
    if not res.get('ok'):
        await message.answer("❌ %s" % res.get('error'), reply_markup=menu())
        return
    await message.answer(
        "✅ Xarajat qabul qilindi\n\n<b>%s</b>\nSumma: %s so'm\n"
        "Reys xarajati: %s so'm\nReys foydasi: %s so'm"
        % (res['trip_name'], son(res['amount']),
           son(res['expense_total']), son(res['profit'])),
        reply_markup=menu())


@router.message(Expense.photo)
async def photo_required(message: Message):
    await message.answer(
        "Chek rasmi kerak. Rasmni <b>surat sifatida</b> yuboring "
        "(fayl emas), yoki «%s» tugmasini bosing." % ORQAGA)


@router.error()
async def on_error(event, exception=None):
    """Handlerdagi har qanday xato — foydalanuvchiga xabar, jurnalga to'liq matn.

    Busiz nosozlik yuz berganda foydalanuvchi hech qanday javob olmaydi va
    bot ishlamayotgandek tuyuladi.
    """
    exc = getattr(event, 'exception', exception)
    _log.exception("Handler xatosi: %s", exc)
    update = getattr(event, 'update', None)
    target = getattr(update, 'message', None) or getattr(
        getattr(update, 'callback_query', None), 'message', None)
    if target is not None:
        try:
            await target.answer(
                "⚠️ Texnik nosozlik. Administratorga xabar bering.",
                reply_markup=menu())
        except Exception:                 # javob ham ketmasa — faqat jurnal
            _log.exception("Xato haqida xabar yuborib bo'lmadi")
    return True


async def run(args):
    odoo = Odoo(args.url, args.db, args.user, args.key, not args.no_verify_ssl)
    bot = Bot(token=args.token,
              default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    # Tartib muhim: menyu va «Orqaga» har qanday holatdan oldin ko'riladi.
    dp.include_router(menyu_router)
    dp.include_router(router)
    _log.info("Bot ishga tushdi (long polling)")
    await dp.start_polling(bot, odoo=odoo)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--url', default=os.getenv('AGRONOVA_URL', 'https://demo.novaodoo.uz'))
    p.add_argument('--db', default=os.getenv('AGRONOVA_DB', 'agronova_demo'))
    p.add_argument('--user', default=os.getenv('AGRONOVA_USER', 'agronova_demo'))
    p.add_argument('--key', default=os.getenv('AGRONOVA_KEY'))
    p.add_argument('--token', default=os.getenv('AGRONOVA_BOT_TOKEN'))
    p.add_argument('--no-verify-ssl', action='store_true',
                   help="Sertifikat muddati o'tgan bo'lsa")
    args = p.parse_args()
    if not args.key or not args.token:
        raise SystemExit("--key va --token majburiy (yoki AGRONOVA_KEY / AGRONOVA_BOT_TOKEN)")
    asyncio.run(run(args))


if __name__ == '__main__':
    main()
