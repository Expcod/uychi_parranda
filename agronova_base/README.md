<!-- AUTO:BEGIN — bu blok koddan avtomatik yangilanadi (claude_tarix/tools/readme_yoz.py), qo'lda tahrirlamang -->
# AgroNova — umumiy asos (base) (`agronova_base`)

> Bo'limlar uchun umumiy mixin'lar: xarajat hujjati, taqsimlash bazasi, analitik yordamchilar

- **Loyiha:** AgroNova — parrandachilik holdingi (boquv, ona tovuq, inkubatoriya, so'yish, yem zavodi, qishloq xo'jaligi, savdo)
- **Versiya:** 19.0.1.0.0  ·  **Litsenziya:** LGPL-3
- **Bog'liqliklar:** `base`, `mail`, `account`, `analytic`, `hr`

## Tavsif

«AgroNova» ERP loyihasining umumiy qatlami.

Boquv, Ona Tovuq, So'yish, Inkubatoriya kabi bo'lim modullarida bir xil
takrorlanadigan mexanizmlar shu yerda bir marta yozilgan:

* `agronova.xarajat.mixin` — xarajat hujjatining umumiy skeleti: naqd/qarz
  to'lov turi, naqdda foto majburiyati, tahrirlash muddati pog'onasi
  (12/24/36 soat), maqsad turi va taqsimlash bazasi (bosh soni / m² / teng).
* `agronova.xarajat.kategoriya` — xarajat kategoriyalari, har biriga standart
  taqsimlash bazasi bog'lanadi (faqat administrator yaratadi).
* `agronova.analitik.mixin` — obyektga (bino, partiya) avtomat analitik hisob
  ochish va unga xarajat/daromad qatorlarini yozish yordamchilari.
* Bo'limlararo umumiy rollar: bosh buxgalter, direktor.

**Muhim:** bu modul hech qanday bo'limga tegishli biznes mantiq saqlamaydi —
faqat qayta ishlatiladigan pattern. Yangi bo'lim moduli yozilganda xarajat
hujjati qaytadan yozilmaydi, shu mixin'dan meros olinadi.

## Modellar

| Model | Tavsif | Maydonlar |
|---|---|---|
| `agronova.analitik.mixin` | AgroNova — analitik hisob mixin | `analytic_account_id` |
| `agronova.elminatsiya.mixin` | AgroNova — ichki marja elminatsiyasi | `name`, `davr_boshi`, `davr_oxiri`, `company_id`, `currency_id`, `jami_ichki_sotuv`, `jami_marja`, `jami_elminatsiya`, `realizatsiya_marja`, `holat` … |
| `agronova.elminatsiya.qator.mixin` | AgroNova — elminatsiya qatori | `currency_id`, `qolgan_miqdor`, `sotilgan_miqdor`, `realizatsiya_foiz`, `elminatsiya_summa`, `izoh` |
| `agronova.jurnal.provider.mixin` | AgroNova — kunlik jurnal bot provayderi |  |
| `agronova.jurnal.bot` | AgroNova — kunlik jurnal bot API |  |
| `agronova.mahsulot.guruh` | AgroNova — mahsulot guruhi | `name`, `kod`, `izoh`, `categ_ids`, `product_ids`, `product_soni`, `active` |
| `agronova.mahsulot.filtr.mixin` | AgroNova — mahsulot filtri |  |
| `agronova.otkazma.mixin` | AgroNova — bo'limlararo o'tkazma mixin |  |
| `agronova.pl.qator.mixin` | AgroNova — foyda-zarar hisoboti qatori | `currency_id`, `nom`, `summa`, `ulush` |
| `agronova.pl.mixin` | AgroNova — bo'lim foyda-zarari | `davr_boshi`, `davr_oxiri`, `company_id`, `currency_id`, `ichki_sotuv`, `tashqi_sotuv`, `boshqa_daromad`, `jami_daromad`, `sotilgan_tannarx`, `jami_xarajat` … |
| `agronova.tannarx.qulf.mixin` | AgroNova — tannarx maydonini qulflash |  |
| `agronova.xarajat.kategoriya` | Xarajat kategoriyasi | `name`, `code`, `sequence`, `taqsimlash_bazasi`, `account_id`, `is_ish_haqi`, `active`, `company_id`, `note` |
| `agronova.xarajat.mixin` | AgroNova — xarajat hujjati mixin | `name`, `sana`, `kategoriya_id`, `nom`, `miqdor`, `narx`, `summa`, `company_id`, `currency_id`, `tolov_turi` … |

Kengaytirilgan standart/boshqa modellar:

- `account.analytic.line`: `agronova_kategoriya_id`, `agronova_tannarx_bazasi`, `agronova_obyekt`
- `stock.lot`
- `stock.move`

## Interfeys va huquqlar

- **Menyular:** AgroNova sozlamalari · Xarajat kategoriyalari · Mahsulot guruhlari
- **Huquq guruhlari:** Bo'lim boshlig'i; Bo'lim hisobchisi; Bosh buxgalter; Direktor (faqat ko'radi)

## O'rnatish, yangilash, test

Lokal (Windows, `Desktop\odoo` ichidan, Git Bash):

```bash
./venv/Scripts/python.exe run_odoo.py -c odoo-agronova.conf -d agronova -u agronova_base --stop-after-init --no-http
```

Server: GitHub `novaodooteam/agronova-custom` ga push → serverda `git pull` + `-u <modul>`.
<!-- AUTO:END -->

## Eslatmalar va tuzoqlar

- Bo'lim modullari (boquv, ona tovuq, so'yish, inkubatoriya, qishloq xo'jaligi) shu mixin'larni
  ishlatadi — bu yerdagi o'zgarish hammasiga ta'sir qiladi; ularni birga `-u` qiling.
