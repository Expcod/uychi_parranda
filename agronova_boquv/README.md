# AgroNova — Boquv: brigadir paneli

`Boquv → Operatsiyalar → Brigadir paneli` (`agronova_boquv.brigadir_panel`).

## Nima uchun panel kerak

TZ ning 9 va 10-bandlari brigadirning kunlik vazifalarini sanaydi: sehni
va ishchilarni nazorat qilish, jo'jalar holatini tekshirish, o'lganini
aniqlash, haroratni o'lchash, yem va suv holatini ko'rish, **kuniga kamida
3 marta obxod** qilish va **kunlik ma'lumotlarni tizimga kiritish**.

Bularning har biri uchun modulda alohida hujjat bor (`agronova.boquv.obxod`,
`agronova.boquv.jurnal`, `agronova.boquv.vazn`, `agronova.boquv.xarajat`), lekin
brigadir ularni sehda, telefonda to'ldiradi — to'rt xil formani ochib
yurish real ish sharoitiga to'g'ri kelmaydi. Panel shu to'rttasini bitta
ekranga yig'adi va eng muhim savolga javob beradi: **bugun nima
qilinmagan**.

## Ekranda nima bor

| Bo'lim | Mazmuni |
|---|---|
| Kunlik xulosa | Faol partiya, tirik jo'ja, jurnalsiz partiya, obxodi yetmagan partiya |
| Ogohlantirishlar | Jurnal to'ldirilmagan · obxod 3 tadan kam · harorat me'yordan chetda · FCR/nobud normadan og'gan. Bosilsa o'sha partiyaga o'tadi |
| Partiya kartochkalari | Yosh/reja kun, tirik bosh soni, nobud %, FCR, obxod n/3, jurnal ✓/✗ |
| Tanlangan partiya | Boshlang'ich, nobud, yashovchanlik, EPEF + shu yoshdagi me'yor qatori |
| Bugungi obxodlar | Vaqt, harorat (me'yordan chetlashsa qizil), holatlar, muammo/chora |
| Oxirgi kunlar | 7 kunlik jurnal: nobud, qoldiq, yem, suv, harorat, holat |

To'rt amal tugmasi: **Obxod**, **Kunlik jurnal**, **Vazn**, **Xarajat**.

## Qaror izohlari

**Hisob-kitob faqat serverda.** Panel `agronova.boquv.partiya` dagi `ui_*`
metodlaridan ma'lumot oladi va formani o'sha yerga yuboradi. Shu sababli
paneldagi raqam hujjat ochilganda ko'rinadigan raqamdan hech qachon farq
qilmaydi.

**Huquq qoidasi takrorlanmagan.** Panel oddiy `search` ishlatadi —
brigadir kimning partiyasini ko'rishini `security/agronova_boquv_rules.xml`
hal qiladi. Qoida bitta joyda turgani uchun panel va ro'yxat ko'rinishi
bir-biridan ajralib qolmaydi.

**Kunlik jurnal — kuniga bitta.** Modelda `UNIQUE(partiya_id, sana)` bor.
Panel o'sha kunning **qoralamasi** bo'lsa ustiga yozadi (eski sarf
qatorlarini o'chirib — aks holda yem ikki marta qo'shilardi),
**tasdiqlangani** bo'lsa rad etadi: sarf ombordan chiqib bo'lgan.

**Obxoddagi «o'lik jo'ja» hisobga kirmaydi.** Rasmiy nobud soni kunlik
jurnalda yoziladi; obxoddagi raqam faqat ma'lumot uchun. Panel buni
formada ham yozib qo'yadi, chunki ikki joyda son ko'rgan brigadir
ikkalasini ham to'ldirib, nobudni ikki barobar qilib yuborardi.

**Naqd xarajat.** `agronova.xarajat.mixin` naqd to'lovda foto va depozitni
majburiy qiladi. Panel telefon kamerasini ochadi (`capture="environment"`)
va depozit qoldig'ini ko'rsatib turadi, lekin tekshiruv mixin'da qoladi —
qoida bitta joyda.

## Yo'l-yo'lakay tuzatilgan nuqson

`agronova.boquv.partiya._compute_obxod_bugun` da `@api.depends` yo'q edi.
Odoo bunday compute'ni bir marta hisoblab keshlaydi va tranzaksiya
davomida qayta hisoblamaydi — panel obxodni yozib, o'sha so'rov ichida
sonni qaytargani uchun brigadir «3/3» o'rniga «0/3» ni ko'rardi. Endi
`@api.depends('obxod_ids.vaqt')` qo'yildi. Shu bilan birga sana
foydalanuvchi vaqt mintaqasida olinadigan bo'ldi: UTC bo'yicha
hisoblanganda Toshkentda soat 19:00 dan keyingi obxod ertangi kunga
tushib ketardi va norma buzilgandek ko'rinardi.

## O'rnatish tuzog'i

Eski bazaga o'rnatishda **`agronova_base` ni ham yangilash shart**:

```bash
python run_odoo.py -c odoo-agronova.conf -d <db> \
    -u agronova_base -i agronova_boquv --stop-after-init
```

Usiz `ir_model_inherit` da `null value in column "parent_id"` xatosi
chiqadi: `agronova_base` ga keyin qo'shilgan mixin'lar (`agronova.pl.mixin`,
`agronova.jurnal.provider.mixin`, `agronova.tannarx.qulf.mixin`) bazadagi
`ir_model` da bo'lmaydi, chunki Odoo faqat yangilanayotgan modullarning
modellarini ro'yxatga oladi.

## Sinov

```bash
echo "exec(open(r'agronova_custom/scripts/31_boquv_panel_test.py', encoding='utf-8').read())" \
  | python run_odoo.py shell -c odoo-agronova.conf -d agronova_boquv_test --no-http

node donxolm_custom/tools/owl_smoke.mjs \
    agronova_custom/agronova_boquv/static/src/boquv_panel.js BoquvBrigadirPanel
```

53 ta tekshiruv: panel ochilishi, ogohlantirishlar, obxod normasi, jurnal
qoralama/tasdiq oqimi, sarf ikkilanmasligi, vazn, depozitli xarajat,
record rule va faol bo'lmagan partiya cheklovi.

## Keyingi bosqich

* So'yimga jo'natma paneldan emas, standart formadan kiritiladi — u
  mashina, yuk xati va manzil talab qiladigan kamdan-kam hujjat;
* Telegram bot (`agronova_telegram`) orqali xuddi shu kunlik jurnalni
  to'ldirish — `agronova.jurnal.provider.mixin` allaqachon tayyor;
* haroratni sensordan avtomat olish (TZ 11-band, kelajak uchun).
