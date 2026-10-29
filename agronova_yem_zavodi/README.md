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

## Eslatmalar va tuzoqlar

- Odoo 19 da `stock.valuation.layer` yo'q — qiymat `stock.move.value` da; tannarx yig'indisi shu yerdan olinadi.
