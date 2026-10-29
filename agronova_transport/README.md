# AgroNova — Transport reyslari (`agronova_transport`)

Odooning `fleet` moduli mashina, haydovchi, texnik xizmat va shartnomani yuritadi,
lekin **«reys» tushunchasi yo'q**. Bu modul shuni qo'shadi.

## O'rnatish

```bash
# 1. addons_path ga qo'shing
addons_path = ...,/opt/odoo/custom_addons/agronova-custom

# 2. modullar ro'yxatini yangilang va o'rnating
./odoo-bin -c odoo.conf -d agronova_demo -u base --stop-after-init
./odoo-bin -c odoo.conf -d agronova_demo -i agronova_transport --stop-after-init
```

Bog'liqliklar: `fleet`, `hr_expense`, `analytic` — uchalasi ham `agronova_demo` da
allaqachon o'rnatilgan.

**Diqqat:** o'rnatishdan oldin `scripts/12_cleanup_manual_trip.py` ni ishga tushiring —
u demo bazadagi Studio uslubidagi `x_agronova_trip` modelini tozalaydi. Aks holda
ikkita bir xil «Reyslar» menyusi paydo bo'ladi.

## Nima beradi

| Model | Izoh |
|---|---|
| `agronova.trip` | Reys — ichki yoki tashqi, 7 bosqichli holat zanjiri |
| `hr.expense.trip_id` | Haydovchi xarajatini reysga bog'laydi |
| `fleet.vehicle.log.services.trip_id` | Yo'ldagi ta'mirni reysga bog'laydi |

### Lot mexanizmi

Reys yaratilganda tizim `REYS-2026-0001` raqamini beradi va shu nom bilan
**analitik hisob** ochadi (`Reys (transport)` rejasida). TZ dagi «har bir reysga
lot/partiya ochiladi» talabi shu — `stock.lot` emas, chunki u mahsulot loti va
unga xarajat yozib bo'lmaydi.

`hr.expense` da reys tanlansa, analitik taqsimot avtomat o'sha lotga yo'naltiriladi.

### Hisob-kitob

```
Jami xarajat = qo'lda kiritilgan + hr.expense (rad etilmaganlari) + fleet xizmat jurnali
Foyda        = daromad − jami xarajat
Haydovchi    = foyda × ulush%          (zarar bo'lsa 0)
Qoldiq qarz  = olgan − topshirgan − xarajat − haydovchi ulushi
```

Haydovchi ulushi **sof foydadan** hisoblanadi, tushumdan emas — TZ ning transport
bo'limida shunday belgilangan (umumiy TT da «30% daromad» deyilgani aniqlashtirilgan).

### Nazorat

- Yo'lga chiqarishdan oldin haydovchi tanlangan bo'lishi shart
- Daromadsiz reysni yakunlab bo'lmaydi — ichki reysda ham tarif summasi kerak,
  busiz foyda va haydovchi ulushi hisoblanmaydi
- Ulush foizi 0–100 oralig'ida (baza darajasida cheklov)

## Hali yo'q (keyingi bosqich)

- Ichki reys tarifi jadvali va daromadning avtomat to'lishi — tarif ma'lumoti
  buyurtmachidan kutilmoqda (`AgroNova TRANSPORT SHABLON.xlsx`, 3-varaq)
- Yoqilg'i normasi (l/100 km) va undan og'ish nazorati
- Telegram bot orqali xarajat kiritish — M11 bot infratuzilmasi bilan birga
- Haydovchi ulushini ish haqi moduliga uzatish
