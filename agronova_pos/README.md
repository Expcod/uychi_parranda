# AgroNova — POS (savdo nuqtasi)

## TZ holati — buni birinchi o'qing

**Texnik topshiriqda POS uchun talab yo'q.** Butun hujjatlar to'plamida u
bir marta tilga olinadi — `docs/TZ_XULOSA.md:55`, M08 (Sotuv) bandining
oxirida: *«POS — keyingi bosqichda»*. Ya'ni buyurtmachi POS ni ataylab
keyinga qoldirgan va uning talablarini yozmagan.

Shuning uchun bu modul POS ni noldan o'ylab topmaydi. U qo'shni
bandlarning POS ga **tegishli** talablarini bajaradi:

| Manba | Talab | Bu yerda qanday bajarilgan |
|---|---|---|
| M08 Sotuv | Tannarxdan past sotuv taqiqi | `agronova_tannarx_nazorati` |
| M08 Sotuv | Kredit limiti | `agronova_kredit_nazorati` |
| M08 Sotuv | Tarozi | Odooning standart qoidasi yetarli (pastga qarang) |
| M08 Sotuv | Sotuvchi KPI | `report.pos.order` ustidagi pivot |
| M04 Kassa | Naqd kassa kitobiga tushsin | `agronova_kassa_id` + smena yopilganda yozuv |
| M06 So'yish | Lot va yaroqlilik muddati | FEFO avtomat biriktirish |
| M01 Ombor | FEFO | `agronova_fefo` |

Buyurtmachidan POS bo'yicha aniq TZ kelganda bu modul o'sha talablarga
moslanadi — hozirgi qamrov yuqoridagi jadval bilan cheklangan.

## Nega Odoo POS ustiga

Loyihaning o'z prinsipi — «tayyor Odoo modullaridan maksimal
foydalanish» (`agronova_zakupka` manifestidagi arxitektura qarori bilan bir
xil). Offline rejim, chek printeri, smena, barcode skaneri, to'lov
usullari va mijoz ekrani `point_of_sale` da allaqachon bor va sinovdan
o'tgan. Ularni qayta yozish foyda bermaydi.

Shu sababli modul **yupqa**: 5 ta model kengaytmasi, 1 ta post-init hook
va 1 ta kichik JS patch. Standartda yo'q narsagina qo'shilgan.

## Asosiy qism: FEFO lot avtomat

Go'sht lot va yaroqlilik muddati bilan yuritiladi (bazadagi 26 ta go'sht
kartochkasining hammasi `tracking='lot'`, `use_expiration_date=True`),
lekin kassir har tarozi urishida lot raqamini terib o'tira olmaydi —
do'konda navbat turadi.

**Standart Odooning bu holatdagi xatti-harakati xavfli.** POS ombor
hujjatini yaratadi, `_action_done()` esa «You need to supply a Lot/Serial
Number» bilan yiqiladi va bu xato `point_of_sale/models/stock_picking.py`
dagi `try/except (UserError, ValidationError): pass` blokida **jimgina
yutiladi**. Natija: pul olindi, chek chiqdi, tovar esa ombordan hisobdan
chiqmadi. Qoldiq asta-sekin haqiqatdan uzoqlashadi va buni hech kim
sezmaydi.

Modul sotuvdan keyin lotni o'zi biriktiradi: muddati eng oldin
tugaydigan partiya birinchi ketadi. Zaxira yetmasa sotuv **to'xtatilmaydi**
(do'konda tarozi farqi tufayli bu odatiy hol) — qolgan miqdor eng erta
lotga yoziladi va ombor hujjatiga ogohlantirish qoldiriladi, ya'ni
manfiy qoldiq ko'rinmay qolmaydi.

## Kassa kitobiga ulanish

Smena yopilganda naqd tushum `agronova.kassa` ga **bitta yig'ma yozuv**
bo'lib tushadi (`manba='pos'`). Har chek uchun emas: kassa kitobi rasmiy
hujjat, unda kun davomidagi 300 ta chek emas, «POS smenasi №… tushumi»
qatori turishi kerak.

Yozuv avtomatik — provodkani smenaning o'zi yozgan, kassa harakati
faqat kitobdagi qatorni beradi. Kassir uni qo'lda tahrirlay ham, storno
qila ham olmaydi.

**Summa qanday olinadi.** `statement_line_ids` yig'indisi ISHLATILMAYDI:
smena yopilganda Odoo o'sha ro'yxatga «sanoq farqi» satrini ham qo'shadi
va yig'indi kamayib ketadi. Kassa kitobiga sotuvdan tushgan naqd
yoziladi, kamomad esa kitobning o'z mexanizmi bilan — kun yopilganda
sanoq va farq orqali (TZ M04) ko'rsatiladi. Aks holda kamomad ikki marta
hisobga olinardi.

Kassadan qilinadigan kirim/chiqim (inkassatsiya, xarajat) POS oynasidan
emas, kassa modulining o'z hujjatlaridan kiritiladi — u yerda modda,
provodka va tasdiqlash zanjiri bor.

## Tannarx nazorati va TZ M13

Tekshiruv **serverda** turadi. Tannarxni brauzerga yuklab JS da
tekshirish tezroq bo'lardi, lekin TZ M13 tannarxni maydon darajasida
yopishni talab qiladi — kassirning brauzeriga tannarx tushmasligi kerak.

Shuning uchun POS to'lovdan oldin serverga bitta so'rov yuboradi
(`pos.order.agronova_tekshir`). Aloqa uzilgan bo'lsa tekshiruv o'tkazib
yuboriladi va sotuv davom etadi — POS oflayn ishlashi kerak. Qoida
baribir buzilmaydi: buyurtma sinxronlanganda `_process_order` uni
ushlaydi.

Tannarxi kiritilmagan (0) mahsulot tekshirilmaydi — bazadagi ko'p
kartochkada `standard_price = 0`, aks holda butun savdo to'xtab qolardi.

## Tarozi — qo'shimcha sozlash kerak emas

Odooning standart nomenklaturasida vazn qoidasi allaqachon bor:

```
«Weight Barcodes 3 Decimals», shablon  21.....{NNDDD}
```

ya'ni `21` + 5 xonali mahsulot kodi + 5 xonali vazn (kg, 3 kasr) +
nazorat raqami. Namuna: `2100123015009` → «00123» mahsuloti, 1.500 kg.

Do'kondagi tarozi shu formatda chop etsa kifoya. Modul ataylab dublikat
qoida qo'shmaydi: ikkalasi bir xil shablonga mos kelib, qaysi biri
ishlashi tartib raqamiga bog'liq bo'lib qolardi.

## O'rnatish tuzog'i (post_init hal qiladi)

Smena yopilganda Odoo naqd tushum uchun oraliq provodka yozadi va uning
hisobi `res.company.account_default_pos_receivable_account_id` dan
olinadi. **Bu maydon bo'sh bo'lsa smena umuman yopilmaydi** —
`account_move_line_check_accountable_required_fields` cheklovi buziladi
va kassir tushunarsiz SQL xatosini ko'radi.

AgroNova bazasida bu maydon bo'sh edi (buxgalteriya auditida
qayd etilgan), shuning uchun `hooks.py` uni o'zi to'ldiradi: **4011 «POS
hisob-kitoblari (oraliq)»** hisobi ochiladi. 4010 ishlatilmaydi — u
xaridorlarning haqiqiy qarzi, POS oraliq hisobi esa bir kun ichida
ochilib yopiladigan texnik hisob; ikkalasini aralashtirish debitor qarz
hisobotini POS aylanmasi bilan ifloslantirardi.

Eski bazaga o'rnatishda `agronova_base` ni ham yangilash kerak:

```bash
python run_odoo.py -c odoo-agronova.conf -d <db> \
    -u agronova_base -i agronova_kassa,agronova_pos --stop-after-init
```

## Sozlash (POS kartochkasida)

| Maydon | Ma'nosi |
|---|---|
| Kassa kitobi | Smena naqdi qaysi kassaga tushadi. **Bo'sh qoldirilmasin** — aks holda ikkita parallel naqd hisobi paydo bo'ladi |
| FEFO | Lot avtomat tanlansinmi (yoqilgan bo'lsin) |
| Tannarxdan past sotuv taqiqi | TZ M08 |
| Kredit limitini tekshirish | TZ M08, «keyin to'lash» usuli uchun |

Qarzga sotish uchun POS ga `pay_later` turidagi to'lov usuli
qo'shiladi va mijoz kartochkasida `credit_limit` to'ldiriladi. Qarzni
keyin kassadan yopish `agronova_kassa` dagi «Sotuvdan tushum» moddasi
orqali bo'ladi — u ochiq hisob-fakturalarni o'zi yarashtiradi.

## Sinov

```bash
echo "exec(open(r'agronova_custom/scripts/32_pos_test.py', encoding='utf-8').read())" \
  | python run_odoo.py shell -c odoo-agronova.conf -d agronova_pos_test --no-http
```

45 ta tekshiruv: FEFO (bitta lot, bir necha lotga bo'linish, zaxira
yetmagani), tannarx taqiqi (chegirma, tannarxsiz mahsulot, oflayn
sinxronlash, nazoratni o'chirish), kredit limiti, smena → kassa kitobi
(summa, manba, provodka takrorlanmasligi, idempotentlik), kassasiz POS
va tarozi barcode'i.

## Qamrovga kirmagani

* **Didox faktura** (M08) — tashqi xizmat kaliti kerak;
* **mijoz Telegram boti** (M08/M11) — `agronova_telegram` infratuzilmasiga
  ulanadi, alohida ish;
* **IoT tarozi** (`pos_iot_adam_scale`) — hozircha barcode orqali
  ishlanadi, IoT box kelganda yoqiladi;
* **bir nechta do'kon / avtolavka** — modul buni to'sib qo'ymaydi (POS
  konfiguratsiyasi har do'kon uchun alohida), lekin sinovdan
  o'tkazilmagan.
