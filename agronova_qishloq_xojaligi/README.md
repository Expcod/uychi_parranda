<!-- AUTO:BEGIN — bu blok koddan avtomatik yangilanadi (claude_tarix/tools/readme_yoz.py), qo'lda tahrirlamang -->
# AgroNova — Qishloq xo'jaligi (`agronova_qishloq_xojaligi`)

> Yer maydonlari, ekin partiyalari, hosil tannarxi va sotuvi

- **Loyiha:** AgroNova — parrandachilik holdingi (boquv, ona tovuq, inkubatoriya, so'yish, yem zavodi, qishloq xo'jaligi, savdo)
- **Versiya:** 19.0.1.0.0  ·  **Litsenziya:** LGPL-3
- **Bog'liqliklar:** `base`, `mail`, `stock`, `stock_account`, `account`, `analytic`, `hr`, `sale_management`, `agronova_base`, `agronova_savdo_moliya`

## Tavsif

AgroNova — Qishloq xo'jaligi bo'limi moduli.

Zanjir: **yer → ekin → partiya → xarajat → hosil → tannarx → sotuv → foyda**.

* **Yer maydoni** — doimiy obyekt, gektari, o'z analitik hisobi va ombor
  lokatsiyasi bilan. Ustida partiyalar ketma-ket almashadi, tarixi saqlanadi.
* **Ekin partiyasi** — bitta yetishtirish sikli. Urug', o'g'it, yoqilg'i,
  ish haqi va boshqa xarajatlar shunga yig'iladi.
* **Dalada bajarilgan ish** — ekish, o'g'itlash, sug'orish, dorilash, o'rim.
  Tasdiqlanganda resurs ombordan hisobdan chiqadi, FIFO qiymati partiya
  tannarxiga tushadi. Kunlik jurnal yo'q — ekinda har kun yozadigan narsa
  bo'lmaydi.
* **Hosil kirimi** — omborga lot bilan kiradi, qiymati partiya tannarxidan.
* **Tannarx** = partiyaning jami xarajati / olingan hosil (kg). Qo'lda
  kiritilmaydi.
* **Xarajat taqsimoti** — sug'orish, elektr, texnika **gektar bo'yicha**
  yerlar orasida bo'linadi.
* **Ichki berish** (Yem zavodiga) — QQS fakturasi yo'q, lekin partiyaga
  daromad va tannarx chiqimi yoziladi, shunda rentabellik to'g'ri chiqadi.

Xarajat hujjati va analitik hisob mexanizmi `agronova_base` dan meros olinadi —
Ona Tovuq bilan bir xil uslub.

## Modellar

| Model | Tavsif | Maydonlar |
|---|---|---|
| `agronova.qx.ekin` | Qishloq xo'jaligi — ekin turi | `name`, `code`, `product_id`, `urug_product_id`, `yetishtirish_kun`, `norma_hosildorlik`, `active`, `note` |
| `agronova.qx.hosil` | Qishloq xo'jaligi — hosil kirimi | `name`, `date`, `partiya_id`, `yer_id`, `ekin_id`, `product_id`, `miqdor_kg`, `uom_id`, `lot_id`, `move_id` … |
| `agronova.qx.ichki_berish` | Qishloq xo'jaligi — ichki berish | `name`, `date`, `partiya_id`, `yer_id`, `qabul_qiluvchi`, `product_id`, `miqdor_kg`, `birlik_narx`, `partiya_tannarx_1_kg`, `partiya_hosil_kg` … |
| `agronova.qx.ish.sarf` | Qishloq xo'jaligi — sarf qatori | `ish_id`, `product_id`, `miqdor`, `uom_id`, `move_id`, `qiymat`, `currency_id` |
| `agronova.qx.ish` | Qishloq xo'jaligi — dalada bajarilgan ish | `name`, `date`, `tur`, `partiya_id`, `yer_id`, `company_id`, `currency_id`, `holat`, `maydoni_ga`, `texnika_soat` … |
| `agronova.qx.partiya` | Qishloq xo'jaligi — ekin partiyasi | `name`, `yer_id`, `ekin_id`, `maydoni_ga`, `ekish_sana`, `yopilish_sana`, `reja_hosil_kg`, `company_id`, `currency_id`, `holat` … |
| `agronova.qx.pl` _(wizard)_ | Qishloq xo'jaligi — bo'lim foyda-zarari | `qator_ids`, `olingan_hosil_kg`, `maydon_ga`, `hosildorlik`, `tannarx_1_kg` |
| `agronova.qx.pl.qator` _(wizard)_ | Qishloq xo'jaligi — foyda-zarar hisoboti qatori | `pl_id`, `currency_id` |
| `agronova.qx.xarajat` | Qishloq xo'jaligi — xarajat hujjati | `yer_id`, `yer_ids`, `taqsimlash_bazasi` |
| `agronova.qx.yer` | Qishloq xo'jaligi — yer maydoni | `name`, `code`, `maydoni_ga`, `joylashuvi`, `mas_ul_xodim_id`, `company_id`, `currency_id`, `warehouse_id`, `location_id`, `active` … |

Kengaytirilgan standart/boshqa modellar:

- `sale.order.line`: `agronova_qx_partiya_id`
- `stock.move`

## Interfeys va huquqlar

- **Menyular:** Qishloq xo'jaligi · Dalada · Bajarilgan ishlar · Olingan hosil · Yer va ekin · Yer maydonlari · Ekin partiyalari · Moliya · Xarajatlar · Sozlamalar · Ekin turlari · Xarajat kategoriyalari · Depozitlar · Hisobotlar · Foyda-zarar · Yer maydonlari hisoboti · Partiyalar hisoboti · Olingan hosil hisoboti · Sarflangan materiallar · Ichki berish hisoboti · Tannarx hisoboti
- **Huquq guruhlari:** Agronom; Bo'lim boshlig'i; Hisobchi

## O'rnatish, yangilash, test

Lokal (Windows, `Desktop\odoo` ichidan, Git Bash):

```bash
./venv/Scripts/python.exe run_odoo.py -c odoo-agronova.conf -d agronova -u agronova_qishloq_xojaligi --stop-after-init --no-http
```

Server: GitHub `novaodooteam/agronova-custom` ga push → serverda `git pull` + `-u <modul>`.
<!-- AUTO:END -->

## Eslatmalar va tuzoqlar

_Hozircha yo'q._
