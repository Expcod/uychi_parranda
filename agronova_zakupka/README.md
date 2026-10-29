<!-- AUTO:BEGIN — bu blok koddan avtomatik yangilanadi (claude_tarix/tools/readme_yoz.py), qo'lda tahrirlamang -->
# AgroNova — Xarid (Zakupka) (`agronova_zakupka`)

> Zayavka → ruxsat → xarid → tranzit → ombor → Didox: to'liq xarid sikli

- **Loyiha:** AgroNova — parrandachilik holdingi (boquv, ona tovuq, inkubatoriya, so'yish, yem zavodi, qishloq xo'jaligi, savdo)
- **Versiya:** 19.0.1.0.0  ·  **Litsenziya:** LGPL-3
- **Bog'liqliklar:** `base`, `mail`, `resource`, `hr`, `stock`, `stock_account`, `purchase`, `purchase_stock`, `account`, `stock_landed_costs`, `product_expiry`, `account_asset`, `agronova_base`, `agronova_savdo_moliya`

## Tavsif

AgroNova — Xarid (Zakupka) bo'limi moduli.

**Arxitektura qarori (texzadaniya 0.5-bandiga javob).**
OCA `purchase_request` va `base_tier_validation` bu o'rnatmaning
addons_path ida yo'q (faqat Odoo core + Enterprise, 1397 modul) va OCA da
19.0 uchun barqaror port ham hali chiqmagan. Shuning uchun `agronova.zayavka`
va `agronova.ruxsat` shu modulda yoziladi — lekin **ataylab yupqa**:
ular faqat so'rov va tasdiqlash qatlamini olib yuradi, tovar harakati va
moliyaviy yozuv esa to'liq Odoo standartiga (`stock.picking`,
`account.move`, `stock.landed.cost`, `account.asset`) topshiriladi.
Ya'ni 15-bo'limdagi «tayyor modulni ishlat» talabi buzilmaydi — faqat
tasdiqlash zanjiri va zayavka qobig'i o'z qo'limizda.

Asosiy mexanizmlar:

* **Tovar va faktura — ikki alohida hujjat.** `stock.picking` omborchida,
  `account.move` buxgalterda. Didox fakturasi 1-2 kun kech kelsa ham oqim
  to'xtamaydi (MSFO: qarz tovar nazorati o'tgan zahoti tan olinadi).
* **Zakupchik tranziti** — har bir zakupchikka shaxsiy ombor joyi; sotib
  olingan, lekin omborchi qabul qilmagan tovar shu yerda, zakupchik
  zimmasida turadi.
* **Uch qatlamli narx normasi** — xarid tarixi → kategoriya limiti →
  «birinchi xarid» (kamida 3 taklif). Og'ish foizi tovar → kategoriya →
  umumiy tartibida aniqlanadi; chegaradan oshsa kirim hujjati saqlanmaydi.
* **Ketma-ket uch bosqichli tasdiqlash**, o'z-o'zini tasdiqlash taqiqi va
  avtomat bir pog'ona yuqoriga ko'tarish.
* **Muddat nazorati** — barcha muddatlar bitta markazlashgan ish vaqti
  kalendaridan (`resource.calendar`) hisoblanadi, `ir.cron` eskalatsiya
  qiladi.
* **KPI** — uch o'lchovli omborchi bahosi, narx tejami, e'tiroz (nizo)
  mexanizmi, oy yopilgach qulf. Faqat bonusga ta'sir qiladi.
* **Didox** — avtomat tortish va STIR+summa+sana bo'yicha solishtirish,
  ikki tomonlama hisobot (tovar bor/faktura yo'q va aksincha).
* **Import (C1/C2)** — GTD, bojxona, Landed Cost; C2 uskuna omborga
  tushmaydi, `account.asset` orqali amortizatsiya qilinadi.

Depozit, storno, foto majburiyati va tahrirlash muddati pog'onasi
qaytadan yozilmagan — `agronova_base` va `agronova_savdo_moliya` dan meros.

## Modellar

| Model | Tavsif | Maydonlar |
|---|---|---|
| `agronova.didox.log` | Didox faktura yozuvi | `name`, `sana`, `hujjat_turi`, `stir`, `kontragent_id`, `summa`, `qqs_summasi`, `currency_id`, `company_id`, `moslashtirilgan_kirim_id` … |
| `agronova.import` | Import partiyasi | `name`, `import_turi`, `kontragent_id`, `zakupchik_id`, `company_id`, `currency_id`, `shartnoma_raqami`, `shartnoma_sanasi`, `yetkazib_berish_sharti`, `valyuta_id` … |
| `agronova.kirim` | Xarid kirim hujjati | `name`, `sotib_olingan_sana`, `kiritilgan_sana`, `kechikib_kiritilgan`, `xarid_turi`, `tasdiqlangan_ruxsat_id`, `zayavka_id`, `zakupchik_id`, `kontragent_id`, `oz_nomidan` … |
| `agronova.kirim.qatori` | Xarid kirim qatori | `kirim_id`, `product_id`, `zayavka_qatori_id`, `miqdor`, `olchov_birligi_id`, `narx`, `summa`, `currency_id`, `qabul_miqdor`, `lot_nomi` … |
| `agronova.kpi.davr` | KPI davri | `name`, `boshlanish`, `tugash`, `holat`, `ball_narxi`, `currency_id`, `kpi_ids` |
| `agronova.kpi` | KPI ball yozuvi | `name`, `xodim_id`, `davr_id`, `sana`, `mezon_turi`, `qiymat`, `norma`, `ball`, `formula_izohi`, `nizoli` … |
| `agronova.kpi.etiroz` | KPI balliga e'tiroz | `kpi_id`, `xodim_id`, `eski_ball`, `yangi_ball`, `sabab`, `korib_chiquvchi_id`, `qaror_izohi`, `holat` |
| `agronova.muddat.mixin` | AgroNova — ish vaqti bo'yicha muddat hisobi | `kechikdimi`, `kechikish_soati`, `eskalatsiya_darajasi` |
| `agronova.narx.normasi` | Xarid — norma narx | `product_id`, `company_id`, `currency_id`, `norma_narx`, `sana`, `manba`, `manba_izoh`, `eski` |
| `agronova.nomenklatura.sorovi` | Yangi nomenklatura so'rovi | `name`, `nom`, `olchov_birligi_id`, `kategoriya_id`, `xarajat_turi`, `izoh`, `surat`, `surat_filename`, `sorovchi_id`, `tekshiruvchi_id` … |
| `agronova.qaytarish` | Xarid tovarini qaytarish | `name`, `kirim_id`, `kontragent_id`, `company_id`, `currency_id`, `sana`, `sabab`, `izoh`, `qator_ids`, `summa` … |
| `agronova.qaytarish.qatori` | Qaytarish qatori | `qaytarish_id`, `kirim_qatori_id`, `product_id`, `miqdor`, `narx`, `summa`, `currency_id` |
| `agronova.ruxsat` | Sotib olishga ruxsat | `name`, `zayavka_id`, `zayavka_qatori_id`, `zakupchik_id`, `company_id`, `currency_id`, `product_id`, `tovar_nomi`, `miqdor`, `olchov_birligi_id` … |
| `agronova.taklif` | Xarid taklifi (birinchi xarid solishtiruvi) | `ruxsat_id`, `taklif_beruvchi`, `kontragent_id`, `narx`, `currency_id`, `yetkazish_muddati`, `dalil`, `dalil_filename`, `izoh` |
| `agronova.zayavka` | Xarid zayavkasi | `name`, `warehouse_id`, `omborchi_id`, `zakupchik_id`, `company_id`, `qator_ids`, `sana`, `kiritilgan_sana`, `maksimal_muddat`, `muhimlik_darajasi` … |
| `agronova.zayavka.qatori` | Zayavka qatori | `zayavka_id`, `product_id`, `miqdor`, `olchov_birligi_id`, `bajarilgan_miqdor`, `qoldiq_miqdor`, `izoh`, `kirim_qatori_ids` |
| `agronova.qabul.wizard` _(wizard)_ | Tovarni qabul qilish va baholash | `kirim_id`, `zakupchik_id`, `maqsad_ombor_id`, `qator_ids`, `ball_toliqlik`, `ball_muddat`, `ball_sifat`, `ball_sababi`, `ball_izohi` |
| `agronova.qabul.wizard.qatori` _(wizard)_ | Qabul qilish qatori | `wizard_id`, `kirim_qatori_id`, `product_id`, `soralgan_miqdor`, `qabul_miqdor`, `lot_nomi`, `yaroqlilik_sanasi`, `kuzatuv_shart` |

Kengaytirilgan standart/boshqa modellar:

- `product.category`: `narx_ogish_foizi`, `kategoriya_limit_narx`, `kuzatuv_majburiy`
- `product.template`: `xarajat_turi`, `narx_ogish_foizi`, `norma_narx`, `norma_narx_manba`, `norma_narx_sana`, `norma_narx_eski`, `seriya_kuzatuv_shart`
- `product.product`
- `res.config.settings`: `agronova_zk_kalendar_id`, `agronova_zk_bitta_tasdiq_chegara`, `agronova_zk_muddat_juda_muhim`, `agronova_zk_muddat_orta`, `agronova_zk_muddat_zaxira`, `agronova_zk_eskalatsiya_oraliq`, `agronova_zk_narx_tarixi_soni`, `agronova_zk_narx_eskirish_oy` …
- `res.partner`: `shaxs_turi`, `stir`, `qqs_tolovchi`, `qqs_royxat_raqami`, `xarajat_turi`, `bank_hisob_raqami`, `bank_mfo`, `telegram_username` …
- `res.users`: `zakupka_roli`, `zakupka_tranzit_id`, `zakupka_depozit_id`, `zakupka_orinbosar_id`, `zakupka_rahbar_id`
- `agronova.kirim`: `faktura_kutish_kuni`
- `stock.location`: `zakupchik_tranzit`, `zakupchik_user_id`

## Interfeys va huquqlar

- **Menyular:** Xarid · Operatsiyalar · Zayavkalar · Ruxsat so'rovlari · Xarid kirimlari · Qaytarishlar · Import partiyalari · Nomenklatura so'rovlari · Moliya · Didox fakturalari · Depozit qoldiqlari · KPI · Mening KPI'im · KPI hisoboti · E'tirozlar · KPI davrlari · Hisobotlar · Ochiq zayavkalar · Tasdiq kutayotgan ruxsatlar · Tranzitda turgan tovarlar · Faktura kutilayotgan tovarlar · Fakturasi bor, tovari yo'q · Narx og'ishi · Kechikib kiritilgan yozuvlar · Kontragent bo'yicha xaridlar
- **Rejali amallar (cron):** Xarid: zayavka javob muddati nazorati; Xarid: ruxsat tasdiq muddati nazorati; Xarid: tranzitda qolgan tovar nazorati; Xarid: Didox fakturalarini tortib olish; Xarid: Didox solishtirish va faktura ogohlantirishi; Xarid: eskirgan norma narxlar
- **Huquq guruhlari:** Omborchi; Zakupchik; Sifat va narx nazorati boshlig'i; Xarid buxgalteri; Zakupka bo'lim boshlig'i; Xarid administratori

## O'rnatish, yangilash, test

Lokal (Windows, `Desktop\odoo` ichidan, Git Bash):

```bash
./venv/Scripts/python.exe run_odoo.py -c odoo-agronova.conf -d agronova -u agronova_zakupka --stop-after-init --no-http
MSYS_NO_PATHCONV=1 ./venv/Scripts/python.exe run_odoo.py -c odoo-agronova.conf -d <test_nusxa> -u agronova_zakupka --test-enable --test-tags=agronova_zakupka --stop-after-init --no-http
```

Testlar: **56** ta (`tests/`). Testni prod nusxasida emas, alohida nusxa bazada yurgizing.

Server: GitHub `novaodooteam/agronova-custom` ga push → serverda `git pull` + `-u <modul>`.
<!-- AUTO:END -->

## Eslatmalar va tuzoqlar

- OCA `purchase_request`/`base_tier_validation` bu o'rnatmada yo'q va 19.0 porti chiqmagan — shuning uchun
  zayavka/ruxsat custom, tovar va pul harakati esa to'liq Odoo standartida (stock/account/landed cost/assets).
- Lokal sinov: `agronova_back_1208` nusxasidan `agronova_zk_test` →
  `run_odoo.py -c odoo-agronova.conf -d agronova_zk_test -i agronova_zakupka --test-enable
  --test-tags=agronova_zakupka` (56 test).
- TZ 20-bo'limdagi 7 ta qiymat hali buyurtmachidan olinmagan — `ir.config_parameter` da, data faylida `# TODO`.
