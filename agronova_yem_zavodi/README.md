<!-- AUTO:BEGIN — bu blok koddan avtomatik yangilanadi (claude_tarix/tools/readme_yoz.py), qo'lda tahrirlamang -->
# AgroNova — Yem zavodi (`agronova_yem_zavodi`)

> Yem tannarxi: 1 kg va 1 tonna, reja-fakt, tannarx tahlili

- **Loyiha:** AgroNova — parrandachilik holdingi (boquv, ona tovuq, inkubatoriya, so'yish, yem zavodi, qishloq xo'jaligi, savdo)
- **Versiya:** 19.0.1.0.0  ·  **Litsenziya:** LGPL-3
- **Bog'liqliklar:** `mrp`, `mrp_account`, `stock_account`

## Tavsif

AgroNova — Yem zavodi moduli.

Yem zavodi TZ sining asosiy qismi standart Odoo MRP bilan qoplanadi
(retsept, ishlab chiqarish, ombor, sotuv). Bu modul faqat standartda
yo'q narsalarni qo'shadi:

* **1 kg va 1 tonna tannarxi** — Odoo 19 da `mrp.production` da tannarx
  yig'indisi maydonlari yo'q, qiymat `stock.move.value` da yashiringan;
* **xomashyo ulushi** — tannarxning necha foizi xomashyoga to'g'ri keladi;
* **ishlab chiqarish xarajati** — ish markazi orqali kirgan qism
  (elektr, gaz, ish haqi, amortizatsiya) alohida ko'rinadi;
* **reja-fakt taqqoslash** — retsept bo'yicha nazariy tannarx va haqiqiy
  tannarx, chetlanish foizi bilan;
* **tannarx tahlili** — pivot va grafik ko'rinishlar (mahsulot, oy, hafta
  kesimida).

Tonnaga o'girish o'lchov birligi orqali bajariladi, shuning uchun mahsulot
kilogrammda ham, tonnada ham yuritilishi mumkin.

## Modellar

Kengaytirilgan standart/boshqa modellar:

- `mrp.production`: `currency_id`, `product_id`, `agronova_miqdor_kg`, `agronova_xomashyo_qiymat`, `agronova_ustama_qiymat`, `agronova_jami_tannarx`, `agronova_tannarx_1_kg`, `agronova_tannarx_1_tonna` …

## Interfeys va huquqlar

- **Menyular:** Yem tannarxi

## O'rnatish, yangilash, test

Lokal (Windows, `Desktop\odoo` ichidan, Git Bash):

```bash
./venv/Scripts/python.exe run_odoo.py -c odoo-agronova.conf -d agronova -u agronova_yem_zavodi --stop-after-init --no-http
```

Server: GitHub `novaodooteam/agronova-custom` ga push → serverda `git pull` + `-u <modul>`.
<!-- AUTO:END -->

## Batafsil

Yem ishlab chiqarish zavodi uchun to'liq modul: rejadan moliyaviy natijagacha bitta
zanjir. Ma'lumot bir marta kiritiladi, keyingi bosqich oldingisidan oladi.

```
xarid → tarozi (brutto/tara) → xomashyo kirimi (netto)
reja → xomashyo tekshiruvi → ishlab chiqarish buyurtmasi (tasdiqlangan retseptura versiyasi)
     → haqiqiy sarf (komponent bo'yicha og'ish) → yo'qotish (me'yoriy / haqiqiy)
     → qadoqlash (qop og'irligi ayriladi) → tayyor mahsulot ombori
jo'natma (sotuv yoki ichki xo'jalik) → tarozi → faktura / ichki ko'chirish
smena hisoboti · energiya · to'xtashlar · xarajat taqsimoti → 1 kg / 1 t tannarx
```

### TZ bo'yicha qamrov

| TZ | Qayerda |
|---|---|
| 3.1 Rejalashtirish | `agronova.yem.reja` — kunlik/haftalik/oylik, liniya yuklamasi, xomashyo ehtiyoji, xarid talabi, reja-fakt, kechikish |
| 3.2 Retseptura | `mrp.bom` — versiya, holat (loyiha → tasdiqlangan → arxiv), standart yo'qotish %, komponent og'ishi; tasdiqlangani o'zgarmaydi |
| 3.3 Xomashyo berish | `stock.move` — reja (retsepturadan) va haqiqiy sarf; ruxsatdan oshsa buyurtma boshliq tasdig'isiz yopilmaydi |
| 3.4–3.6 Smena va yakun | `agronova.yem.smena`, `agronova.yem.toxtash`; buyurtmada kirim, chiqim, yo'qotish, tannarx |
| 4.1 Avtomobil tarozisi | `agronova_tarozi` moduli |
| 4.2 Qop og'irligi | `agronova.yem.qadoqlash` — standart yoki haqiqiy usul, kam/ortiqcha to'ldirish, qop sarfi ombordan |
| 4.3 Jo'natma tafovuti | `agronova.yem.jonatma` + tarozi; nominal yuk = yem + qoplar |
| 5 Yo'qotishlar | `agronova.yem.yoqotish` — reyestr; «Me'yoriy» va «Haqiqiy yo'qotish» hisobotlari |
| 6.3 Min/max zaxira | `agronova.yem.zaxira` — qayta buyurtma qoidalari + o'rtacha sarf, necha kunga yetadi; soatlik cron |
| 8.2 Ichki iste'mol | ona tovuq, boquv, boshqa ichki — sotuv emas, ichki ko'chirish |
| 9 Tannarx | xomashyo (FIFO) + ish markazi + qadoq + taqsimlangan davr xarajati (`agronova.yem.xarajat`) |
| 10 Energiya | `agronova.yem.energiya` — kVt·soat / t, me'yordan farq |
| 13.1 Telegram | `agronova.yem.bot` — to'xtash, brak, izoh botdan; rahbar uchun `tg_yem_hisobot` |
| 14 Dashboard | `agronova_dashboard` → «Yem zavodi» bo'limi va 3D jarayon xaritasi |
| 15 Rollar | ishchi · smena boshlig'i · omborchi · texnolog · ishlab chiqarish boshlig'i · zavod direktori |

### Demo ma'lumot

`scripts/demo_yem_zavodi.py` bo'sh bazada 30 kunlik zanjir yaratadi (xarid, tortish,
ishlab chiqarish, qadoqlash, sotuv, faktura, to'lov). Hamma raqam Odoo hujjatlari orqali o'tadi.

### Tuzoqlar

- Buyurtma yopilganda Odoo kam sarflangan harakatni bo'lib, talabni haqiqiy miqdorga
  tenglashtiradi — reja `product_uom_qty` dan emas, retseptura qatoridan olinadi.
- Retsepturada `consumption = flexible`: Odoo'ning sarf ogohlantirishi o'rniga bizning tasdiq mexanizmi.
- Tasdiqlangan smenaga bog'liq hujjatda faqat `_smena_qulf_erkin` maydonlari o'zgaradi.
- Qoidalar faqat `agronova_yem_turi = 'yem'` mahsulotli buyurtmalarga qo'llanadi.
