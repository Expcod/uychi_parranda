<!-- AUTO:BEGIN — bu blok koddan avtomatik yangilanadi (claude_tarix/tools/readme_yoz.py), qo'lda tahrirlamang -->
# AgroNova — So'yish (`agronova_soyish`)

> Qabul va tortish, so'yish, chiqim foizi, tashqi mijoz xizmati

- **Loyiha:** AgroNova — parrandachilik holdingi (boquv, ona tovuq, inkubatoriya, so'yish, yem zavodi, qishloq xo'jaligi, savdo)
- **Versiya:** 19.0.1.0.0  ·  **Litsenziya:** LGPL-3
- **Bog'liqliklar:** `base`, `mail`, `stock`, `stock_account`, `account`, `analytic`, `hr`, `sale_management`, `agronova_base`, `agronova_savdo_moliya`

## Tavsif

AgroNova — So'yish bo'limi moduli.

So'yish TZ sining katta qismi standart Odoo bilan qoplanadi: sortirovka va
kesish MRP yon mahsulotlari orqali, tayyor mahsulot ombori va yaroqlilik
muddati `product_expiry` bilan, sotuv `sale_stock` bilan, kuzatuv esa
lot/seriya orqali. Bu modul faqat standartda yo'q narsalarni qo'shadi:

* **Qabul va tortish** — brutto, tara, netto va 1 dona o'rtacha vazni.
  Tovuq donada sanaladi, kilogrammda tortiladi;
* **Chiqim foizi** — tirik vazndan necha foiz tayyor mahsulot chiqdi.
  Odooda bunday ko'rsatkich yo'q;
* **Ikki manba** — ichki boquv va tashqi mijoz. Tashqi mijozning tovug'i
  ham, mahsuloti ham uning mulki: bizga faqat xizmat haqi tegadi
  (so'yilgan dona × narx), ombor harakati yaratilmaydi;
* **Sortirovka tannarxi** — chiqqan mahsulotlar orasida tannarx vazn
  yoki qiymat ulushi bo'yicha bo'linadi;
* **Xarajat taqsimoti** — bosh soni yoki tirik vazn bo'yicha.

Vaqtinchalik saqlash (mijoz mulki omborda turishi) uchun Odooning
konsignatsiya mexanizmi ishlatiladi — custom ombor mantiqi yozilmagan.

## Modellar

| Model | Tavsif | Maydonlar |
|---|---|---|
| `agronova.soyish.natija` | So'yish — sortirovka natijasi | `jarayon_id`, `product_id`, `miqdor_kg`, `ulush_foiz`, `qiymat`, `lot_id`, `move_id`, `currency_id` |
| `agronova.soyish.jarayon` | So'yish jarayoni | `name`, `sana`, `partiya_id`, `manba`, `company_id`, `currency_id`, `holat`, `soyilgan_son`, `nobud_son`, `natija_ids` … |
| `agronova.soyish.partiya` | So'yish partiyasi | `name`, `sana`, `qabul_id`, `manba`, `partner_id`, `product_id`, `company_id`, `currency_id`, `holat`, `tirik_son` … |
| `agronova.soyish.pl` _(wizard)_ | So'yish — bo'lim foyda-zarari | `qator_ids`, `tirik_vazn_kg`, `tayyor_kg`, `chiqim_foiz`, `tannarx_1_kg`, `xizmat_summa` |
| `agronova.soyish.pl.qator` _(wizard)_ | So'yish — foyda-zarar hisoboti qatori | `pl_id`, `currency_id` |
| `agronova.soyish.qabul` | So'yish — qabul qilish va tortish | `name`, `sana`, `manba`, `partner_id`, `product_id`, `transport`, `haydovchi`, `tovuq_soni`, `brutto_kg`, `tara_kg` … |
| `agronova.soyish.xarajat` | So'yish — xarajat hujjati | `partiya_id`, `partiya_ids`, `taqsimlash_bazasi` |
| `agronova.soyish.xizmat` | So'yish — tashqi mijoz xizmati | `name`, `sana`, `partiya_id`, `partner_id`, `company_id`, `currency_id`, `kelgan_son`, `kelgan_vazn`, `soyilgan_son`, `tayyor_kg` … |

## Interfeys va huquqlar

- **Menyular:** So'yish · Kunlik ish · Qabul va tortish · So'yish jarayoni · Partiyalar · So'yish partiyalari · Moliya · Tashqi mijoz xizmati · Xarajatlar · Sozlamalar · Xarajat kategoriyalari · Depozitlar · Hisobotlar · Foyda-zarar · So'yish hisoboti · Tashqi mijozlar hisoboti · Ichki ishlab chiqarish · Tannarx hisoboti
- **Huquq guruhlari:** Operator; Bo'lim boshlig'i; Hisobchi

## O'rnatish, yangilash, test

Lokal (Windows, `Desktop\odoo` ichidan, Git Bash):

```bash
./venv/Scripts/python.exe run_odoo.py -c odoo-agronova.conf -d agronova -u agronova_soyish --stop-after-init --no-http
```

Server: GitHub `novaodooteam/agronova-custom` ga push → serverda `git pull` + `-u <modul>`.
<!-- AUTO:END -->

## Eslatmalar va tuzoqlar

_Hozircha yo'q._
