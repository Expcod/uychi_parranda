<!-- AUTO:BEGIN — bu blok koddan avtomatik yangilanadi (claude_tarix/tools/readme_yoz.py), qo'lda tahrirlamang -->
# AgroNova — Ona Tovuq (`agronova_ona_tovuq`)

> Ona tovuq partiyalari, sexlar, kunlik jurnal, tuxum tannarxi va sotuvi

- **Loyiha:** AgroNova — parrandachilik holdingi (boquv, ona tovuq, inkubatoriya, so'yish, yem zavodi, qishloq xo'jaligi, savdo)
- **Versiya:** 19.0.1.0.0  ·  **Litsenziya:** LGPL-3
- **Bog'liqliklar:** `base`, `mail`, `stock`, `stock_account`, `account`, `analytic`, `hr`, `sale_management`, `agronova_base`, `agronova_savdo_moliya`, `agronova_soyish`, `agronova_ish_haqi`, `agronova_telegram`

## Tavsif

AgroNova — Ona Tovuq bo'limi moduli.

Ona tovuq yo'nalishining to'liq sikli:

**Jo'ja o'stirish partiyasi** (jo'ja kirimi → kunlik jurnal → yopilish, 1 bosh
tannarxi qotadi) → **Ona tovuq partiyasi** (tannarx meros bo'lib o'tadi, bozor
narxida qayta baholash yo'q) → kunlik tuxum jurnali → **tuxum omboriga
kirim** (lot bilan) → **ichki sotuv** (Inkubatsiyaga) yoki **tashqi sotuv**
(standart Sales) → tuxum berish % normadan tushganda poda **so'yishga ichki
sotuv** sifatida o'tkaziladi.

Asosiy mexanizmlar:

* barcha xarajat va daromad `account.analytic.line` ga yig'iladi — tannarx,
  foyda-zarar va rentabellik faqat shundan hisoblanadi;
* xarajat hujjati `agronova.xarajat.mixin` dan meros (naqd/qarz, foto majburiy,
  tahrirlash muddati 12/24/36 soat, storno);
* xarajat taqsimlash: m² / bosh soni / teng / to'g'ridan-to'g'ri;
* ish haqi — sexga biriktirilgan operator to'g'ridan-to'g'ri, biriktirilmagan
  xodim m² bo'yicha, oy o'rtasida ko'chsa kunlar bo'yicha bo'linadi;
* tannarx maydoni **barcha rollar uchun readonly** — qo'lda kiritilmaydi;
* ichki narx: sotuv bo'limi taklif qiladi, bosh buxgalter tasdiqlaydi,
  tarix o'zgartirilmaydi.

## Modellar

| Model | Tavsif | Maydonlar |
|---|---|---|
| `agronova.ona_tovuq.xodim.sex.tarix` | Ona tovuq — xodim sex tarixi | `employee_id`, `sex_id`, `boshlanish_sana`, `tugash_sana` |
| `agronova.ona_tovuq.bot` | Ona tovuq — kunlik jurnal bot provayderi |  |
| `agronova.ona_tovuq.elminatsiya` | Ona tovuq — ichki marja elminatsiyasi | `qator_ids` |
| `agronova.ona_tovuq.elminatsiya.qator` | Ona tovuq — elminatsiya qatori | `elminatsiya_id`, `company_id`, `currency_id`, `ichki_sotuv_id`, `tur`, `date`, `partiya_id`, `miqdor`, `summa`, `tannarx_summa` … |
| `agronova.ona_tovuq.ichki_sotuv` | Ona tovuq — ichki sotuv | `name`, `tur`, `date`, `partiya_id`, `sex_id`, `company_id`, `currency_id`, `dona`, `tirik_vazn`, `product_id` … |
| `agronova.ona_tovuq.ish_haqi` | Ona tovuq — ish haqi taqsimoti | `name`, `davr_boshi`, `davr_oxiri`, `company_id`, `currency_id`, `department_ids`, `qator_ids`, `jami_summa`, `xodim_soni`, `holat` … |
| `agronova.ona_tovuq.ish_haqi.qator` | Ona tovuq — ish haqi taqsimoti qatori | `ish_haqi_id`, `company_id`, `currency_id`, `employee_id`, `sex_id`, `partiya_id`, `usul`, `kunlar`, `jami_kun`, `oylik_summa` … |
| `agronova.ona_tovuq.jurnal.sarf` | Ona tovuq — kunlik sarf qatori | `jurnal_ostirish_id`, `jurnal_tuxum_id`, `product_id`, `miqdor`, `uom_id`, `move_id`, `qiymat`, `currency_id` |
| `agronova.ona_tovuq.jurnal.mixin` | Ona tovuq — kunlik jurnal skeleti | `date`, `company_id`, `currency_id`, `holat`, `kun_boshi_son`, `nobud_son`, `brak_son`, `kun_oxiri_son`, `nobud_sabab`, `suv_litr` … |
| `agronova.ona_tovuq.jurnal.ostirish` | Ona tovuq — kunlik jurnal (jo'ja o'stirish) | `partiya_id`, `sex_id`, `ortacha_vazn` |
| `agronova.ona_tovuq.jurnal.tuxum` | Ona tovuq — kunlik jurnal (ona tovuq) | `partiya_id`, `sex_id`, `sarf_ids`, `nobud_xoroz`, `xoroz_son`, `tovuq_son`, `tovuq_oxiri`, `jami_tuxum`, `sifatli_tuxum`, `brak_tuxum` … |
| `agronova.ona_tovuq.narx` | Ona tovuq — ichki narx | `tur`, `narx`, `amal_sana`, `tugash_sana`, `asos`, `company_id`, `currency_id`, `holat`, `taklif_qildi_id`, `tasdiqladi_id` … |
| `agronova.ona_tovuq.normativ` | Ona tovuq normativi | `name`, `zot_id`, `davr`, `hafta_dan`, `hafta_gacha`, `tuxum_berish_foiz`, `uruglanish_foiz`, `nobud_foiz_haftalik`, `brak_foiz_haftalik`, `xoroz_tovuq_nisbati` … |
| `agronova.ona_tovuq.partiya.mixin` | Ona tovuq partiyasi — umumiy skelet | `name`, `sex_id`, `zot_id`, `company_id`, `currency_id`, `boshlangich_son`, `nobud_son`, `brak_son`, `chiqim_son`, `joriy_son` … |
| `agronova.ona_tovuq.partiya.ostirish` | Ona tovuq — jo'ja o'stirish partiyasi | `kirim_sana`, `yopilish_sana`, `yosh_kun`, `yosh_hafta`, `holat`, `jurnal_ids`, `jurnal_count`, `tannarx_1_bosh`, `tuxum_partiya_id` |
| `agronova.ona_tovuq.partiya.tuxum` | Ona tovuq partiyasi | `ostirish_partiya_id`, `ochilish_sana`, `yopilish_sana`, `yosh_hafta`, `boshlangich_tannarx`, `holat`, `yopilish_sababi`, `soyishga_otkazish_id`, `jurnal_ids`, `kirim_ids` … |
| `agronova.ona_tovuq.pl` _(wizard)_ | Ona tovuq — bo'lim foyda-zarari | `qator_ids`, `jami_tuxum`, `tannarx_1_dona` |
| `agronova.ona_tovuq.pl.qator` _(wizard)_ | Ona tovuq — foyda-zarar hisoboti qatori | `pl_id`, `currency_id` |
| `agronova.ona_tovuq.sex` | Ona tovuq sexi | `name`, `code`, `maydoni`, `sigimi`, `mas_ul_xodim_id`, `company_id`, `currency_id`, `warehouse_id`, `location_id`, `active` … |
| `agronova.ona_tovuq.tuxum.kirim` | Ona tovuq — tuxum omboriga kirim | `name`, `date`, `partiya_id`, `sex_id`, `jurnal_id`, `company_id`, `currency_id`, `qator_ids`, `jami_dona`, `jami_qiymat` … |
| `agronova.ona_tovuq.tuxum.kirim.qator` | Ona tovuq — tuxum kirimi qatori | `kirim_id`, `sifat`, `dona`, `lot_id`, `move_id`, `qiymat`, `currency_id` |
| `agronova.ona_tovuq.xarajat` | Ona tovuq — xarajat hujjati | `sex_id`, `sex_ids` |
| `agronova.ona_tovuq.zot` | Ona tovuq zoti | `name`, `code`, `active`, `ostirish_kun`, `tuxum_davri_hafta`, `normativ_ids`, `note` |

Kengaytirilgan standart/boshqa modellar:

- `hr.employee`: `agronova_ot_sex_id`, `agronova_ot_sex_tarix_ids`
- `res.config.settings`: `agronova_ot_eskirish_chegara`, `agronova_ot_tannarxdan_past_taqiq`, `agronova_ot_product_inkubatsion`, `agronova_ot_product_tovar`, `agronova_ot_product_brak`, `agronova_ot_product_poda`, `agronova_ot_company_inkubatsiya`, `agronova_ot_company_soyish`
- `sale.order.line`: `agronova_tannarx`, `agronova_marja`, `agronova_marja_foiz`, `agronova_ot_partiya_id`
- `sale.order`
- `stock.move`

## Interfeys va huquqlar

- **Menyular:** Ona Tovuq · Kunlik ish · Kunlik jurnal (ona tovuq) · Kunlik jurnal (jo'ja o'stirish) · Tuxum kirimi · Partiyalar · Ona tovuq partiyalari · Jo'ja o'stirish partiyalari · Moliya · Xarajatlar · Ichki narxlar · Ish haqi taqsimoti · Ichki marja elminatsiyasi · Hisobotlar · Foyda-zarar · Kunlik hisobot · Sexlar hisoboti · Partiyalar hisoboti · Tuxum ombori hisoboti · Ichki sotuv (arxiv) · Tannarx hisoboti · Sozlamalar · Sexlar · Zotlar · Normativlar
- **Rejali amallar (cron):** Ona tovuq: to'ldirilmagan kunlik jurnal eslatmasi
- **Huquq guruhlari:** Operator (faqat o'z sexi); Veterinar; Bo'lim boshlig'i; Hisobchi

## O'rnatish, yangilash, test

Lokal (Windows, `Desktop\odoo` ichidan, Git Bash):

```bash
./venv/Scripts/python.exe run_odoo.py -c odoo-agronova.conf -d agronova -u agronova_ona_tovuq --stop-after-init --no-http
```

Server: GitHub `novaodooteam/agronova-custom` ga push → serverda `git pull` + `-u <modul>`.
<!-- AUTO:END -->

## Eslatmalar va tuzoqlar

_Hozircha yo'q._
