# AgroNova — Telegram bot (transport)

Haydovchi telefonidan reys xarajatini **chek rasmi bilan** yuboradi, xarajat
Odooda `hr.expense` sifatida yaratilib reysga bog'lanadi va reys foydasi
avtomat qayta hisoblanadi.

## Arxitektura

```
Telegram  ⇄  bot.py (aiogram 3, long polling)  ⇄  Odoo (XML-RPC)
                                                   └ agronova_telegram moduli
```

Bot **aiogram 3** da yozilgan. XML-RPC blokirovka qiladigan kutubxona bo'lgani
uchun har bir Odoo chaqiruvi `asyncio.to_thread` orqali alohida oqimda
bajariladi — bot sikli to'xtab qolmaydi.

Bot Odoo ichida ishlamaydi. Sabab: Odoo worker'lari uzoq turadigan ulanishga
mo'ljallanmagan, bot esa doim tinglab turishi kerak. Butun biznes mantiq
Odoo tomonida — botda faqat suhbat oqimi. Shu sababli mantiqni o'zgartirish
uchun botni qayta ishga tushirish shart emas.

**Webhook emas, long polling** — Telegram webhook uchun amaldagi SSL sertifikat
talab qiladi, `demo.novaodoo.uz` da esa muddati o'tgan. Long polling sertifikatga
bog'liq emas.

## Ishga tushirish

### 1. Botni yaratish
Telegramda `@BotFather` → `/newbot` → nom va username → token oladi.

### 2. Kutubxona
```bash
/opt/odoo/venv/bin/pip install -r bot/requirements.txt   # aiogram>=3.7
```

### 3. Maxfiy ma'lumotlar
```bash
cat > /etc/agronova-telegram-bot.env <<'EOF'
AGRONOVA_KEY=<Odoo API key>
AGRONOVA_BOT_TOKEN=<BotFather token>
EOF
chmod 600 /etc/agronova-telegram-bot.env
```

### 4. Servis
```bash
cp bot/agronova-telegram-bot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now agronova-telegram-bot
journalctl -u agronova-telegram-bot -f
```

Sinash uchun servissiz ham ishga tushsa bo'ladi:
```bash
python bot/bot.py --key <API_KEY> --token <BOT_TOKEN> --no-verify-ssl
```

## Xodimni botga ulash

1. Xodim botga **/start** yozadi
2. Bot **ism-familiyasini** so'raydi, xodim yozadi va **«Jo'natish»** ni bosadi
3. Odooda: **Fleet → «Botga ulanish arizalari»** ro'yxatiga ariza tushadi.
   Ro'yxatda xodim yozgan ism, **Telegram username** va **Telegram
   profildagi ism** ko'rinadi — solishtirib ko'rish uchun
4. Administrator arizada **xodimni tanlaydi** va «Xodimga biriktirish» ni bosadi
5. Xodim yana /start bosadi — bot ishlay boshlaydi

Ariza qayta-qayta yuborilsa yangi yozuv yaratilmaydi, borlari yangilanadi.
Xodim ismni noto'g'ri yozgan bo'lsa botga **/qayta** deb yozadi.

Rad etilgan ariza qayta yuborilsa yana «Yangi» holatiga qaytadi.

Ulanishni uzish uchun xodim kartochkasidagi «Ulanishni uzish» tugmasi.

## Bot menyusi

| Tugma | Nima qiladi |
|---|---|
| 📋 Kunlik jurnal | Partiyani tanlaydi → savollarga **bittalab** javob beradi → Odooda qoralama jurnal ochiladi |
| 💸 Xarajat kiritish | Ochiq reys → xarajat turi → summa → **chek rasmi** → Odooda yaratiladi |
| 🚛 Mening reyslarim | Yakunlanmagan reyslar, yo'nalishi va joriy xarajati |
| 💰 Hisob-kitobim | Hisoblangan ulush va topshirilishi kerak bo'lgan qoldiq |

## Nazorat

- **Chek rasmi majburiy** — fotosiz xarajat qabul qilinmaydi (TZ talabi)
- Haydovchi **faqat o'z reysiga** xarajat yoza oladi
- Summa noto'g'ri bo'lsa rad etiladi; `850 000` kabi bo'sh joyli yozuv o'qiladi
- Bot faqat biriktirilgan xodim uchun ishlaydi
- Bitta Telegram akkaunt ikki xodimga biriktirilmaydi
- Kunlik jurnal **qoralama** bo'lib tushadi — yem ombordan chiqishi buxgalteriya amali, uni sex boshlig'i ko'rib tasdiqlaydi
- Bir partiyaga bir kunda ikkinchi jurnal ochilmaydi
- Savollar ro'yxati Odooda (`agronova.ona_tovuq.bot`) — jurnalga maydon qo'shilsa botni qayta yozish shart emas
- Barcha amallar `agronova.telegram.log` jurnalida: **Fleet → Telegram jurnali**

## Odoo tomonidagi metodlar

| Model | Metod | Vazifasi |
|---|---|---|
| `hr.employee` | `tg_link(code, chat_id, username)` | Kod bilan bog'lash |
| `hr.employee` | `tg_whoami(chat_id)` | Kim ekanini aniqlash |
| `agronova.trip` | `tg_open_trips(chat_id)` | Ochiq reyslar |
| `agronova.trip` | `tg_trip_summary(chat_id, trip_id)` | Bitta reys hisobi |
| `agronova.trip` | `tg_driver_balance(chat_id)` | Umumiy hisob-kitob |
| `hr.expense` | `tg_expense_products()` | Xarajat turlari |
| `hr.expense` | `tg_create_expense(...)` | Xarajat + chek yaratish |

Lokal sinovda 23/23 o'tdi.

## Keyingi bosqich (TZ M11)

Shu asosga qo'shiladi: ferma kunlik jurnali, hujjatni tasdiqlash tugmalari
(inline keyboard), eskalatsiya xabarlari, rahbariyat xabarnomalari, mijoz boti.
