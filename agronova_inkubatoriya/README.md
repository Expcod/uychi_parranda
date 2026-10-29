<!-- AUTO:BEGIN — bu blok koddan avtomatik yangilanadi (claude_tarix/tools/readme_yoz.py), qo'lda tahrirlamang -->
# AgroNova — Inkubatoriya (`agronova_inkubatoriya`)

> Tuxum qabuli, inkubatsiya partiyasi, jo'ja ochilishi va tannarxi

- **Loyiha:** AgroNova — parrandachilik holdingi (boquv, ona tovuq, inkubatoriya, so'yish, yem zavodi, qishloq xo'jaligi, savdo)
- **Versiya:** 19.0.1.0.0  ·  **Litsenziya:** LGPL-3
- **Bog'liqliklar:** `base`, `mail`, `stock`, `stock_account`, `account`, `analytic`, `hr`, `sale_management`, `agronova_base`, `agronova_savdo_moliya`, `agronova_ona_tovuq`

## Tavsif

AgroNova — Inkubatoriya bo'limi moduli.

Asosiy talab (TZ 13-band): **tuxumdan jo'jagacha zanjir uzilmasligi**.

    Ona tovuq filiali → Tuxum ombori → Tuxum partiyasi →
    Inkubatsiya partiyasi → Jo'ja partiyasi → Jo'ja tannarxi →
    Ichki sotuv (Boquv) / Tashqi sotuv

Standart Odoo bilan qoplanmaydigan qismlar shu modulda:

* **Tuxum qabuli** — Ona tovuqning ichki sotuv hujjatidan avtomat
  qoralama ochiladi. Tuxum jismonan allaqachon ko'chgan bo'ladi, bu
  hujjat uning **kelib chiqishi va qiymatini** inkubatsiya partiyasiga
  bog'laydi;
* **Inkubatsiya partiyasi** — inkubator raqami, mas'ul, qo'yilgan sana,
  kutilayotgan va haqiqiy ochilish sanasi;
* **Ochilish hujjati** — ochilgan jo'ja, ochilmagan tuxum, nobud va brak.
  Ochilish foizi, nobudgarchilik va brak foizi, 1 tuxumdan jo'ja
  koeffitsienti avtomat hisoblanadi. Tuxum ombordan hisobdan chiqadi,
  jo'ja omborga kiradi;
* **Jo'ja tannarxi** — tuxum qiymati + elektr + gaz + suv + ish haqi +
  veterinariya + dori. Analitik qatlam yagona manba, tannarx maydonlari
  qo'lda yozilmaydi;
* **Jo'jani Boquvga berish** — TZ 8-band bo'yicha bo'lim daromadi
  shakllanadigan ichki sotuv, oddiy ko'chirish emas;
* **Elminatsiya** — realizatsiya qilinmagan ichki marja konsolidatsiyada
  chiqarib tashlanadi;
* **Foyda-zarar sahifasi** — boshqa bo'limlardagi bilan bir xil.

Tashqi mijozga jo'ja sotuvi standart Sales bilan ketadi; tannarxdan past
sotuv nazorati `agronova_ona_tovuq` da butun loyiha uchun qo'yilgan.

## Modellar

| Model | Tavsif | Maydonlar |
|---|---|---|
| `agronova.ink.elminatsiya` | Inkubatoriya — ichki marja elminatsiyasi | `qator_ids` |
| `agronova.ink.elminatsiya.qator` | Inkubatoriya — elminatsiya qatori | `elminatsiya_id`, `company_id`, `currency_id`, `ichki_sotuv_id`, `date`, `partiya_id`, `qabul_company_id`, `miqdor`, `summa`, `tannarx_summa` … |
| `agronova.ink.ichki_sotuv` | Inkubatoriya — jo'jani ichki berish | `name`, `date`, `partiya_id`, `company_id`, `currency_id`, `qabul_company_id`, `qabul_warehouse_id`, `qabul_ombor_soni`, `product_id`, `product_domain` … |
| `agronova.ink.inkubator` | Inkubator | `name`, `kod`, `company_id`, `sigim`, `turi`, `active`, `izoh`, `partiya_ids`, `holat`, `joriy_partiya_id` … |
| `agronova.ink.ochilish` | Inkubatoriya — jo'ja ochilishi | `name`, `partiya_id`, `sana`, `company_id`, `currency_id`, `product_id`, `product_domain`, `ochilgan_joja`, `ochilmagan_tuxum`, `nobud_son` … |
| `agronova.ink.partiya` | Inkubatsiya partiyasi | `name`, `company_id`, `currency_id`, `inkubator_id`, `masul_id`, `sana_qoyilgan`, `inkubatsiya_kun`, `sana_kutilayotgan`, `sana_ochilgan`, `kechikish_kun` … |
| `agronova.ink.pl` _(wizard)_ | Inkubatoriya — bo'lim foyda-zarari | `qator_ids`, `tuxum_dona`, `ochilgan_joja`, `sof_joja`, `ochilish_foiz`, `tannarx_1_joja` |
| `agronova.ink.pl.qator` _(wizard)_ | Inkubatoriya — foyda-zarar hisoboti qatori | `pl_id`, `currency_id` |
| `agronova.ink.qabul` | Inkubatoriya — tuxum qabuli | `name`, `date`, `manba`, `company_id`, `currency_id`, `ot_ichki_sotuv_id`, `picking_id`, `purchase_id`, `ot_partiya_id`, `ot_company_id` … |
| `agronova.ink.xarajat` | Inkubatoriya — xarajat hujjati | `partiya_id`, `partiya_ids`, `taqsimlash_bazasi` |

Kengaytirilgan standart/boshqa modellar:

- `sale.order.line`: `agronova_ink_partiya_id`
- `stock.move`
- `stock.picking`

## Interfeys va huquqlar

- **Menyular:** Inkubatoriya · Inkubatsiya · Tuxum qabuli · Inkubatsiya partiyalari · Jo'ja ochilishi · Moliya · Xarajatlar · Ichki marja elminatsiyasi · Hisobotlar · Foyda-zarar · Tuxum hisoboti · Inkubatsiya hisoboti · Jo'ja hisoboti · Tannarx hisoboti · Sotuv hisoboti · Sozlamalar · Inkubatorlar · Xarajat kategoriyalari · Depozitlar
- **Huquq guruhlari:** Omborchi; Operator; Bo'lim boshlig'i; Hisobchi

## O'rnatish, yangilash, test

Lokal (Windows, `Desktop\odoo` ichidan, Git Bash):

```bash
./venv/Scripts/python.exe run_odoo.py -c odoo-agronova.conf -d agronova -u agronova_inkubatoriya --stop-after-init --no-http
```

Server: GitHub `novaodooteam/agronova-custom` ga push → serverda `git pull` + `-u <modul>`.
<!-- AUTO:END -->

## Eslatmalar va tuzoqlar

_Hozircha yo'q._
