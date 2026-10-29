<!-- AUTO:BEGIN — bu blok koddan avtomatik yangilanadi (claude_tarix/tools/readme_yoz.py), qo'lda tahrirlamang -->
# AgroNova — Ish haqi (`agronova_ish_haqi`)

> Tarif, oylik hisoblash, xodim balansi va provodka

- **Loyiha:** AgroNova — parrandachilik holdingi (boquv, ona tovuq, inkubatoriya, so'yish, yem zavodi, qishloq xo'jaligi, savdo)
- **Versiya:** 19.0.1.0.0  ·  **Litsenziya:** LGPL-3
- **Bog'liqliklar:** `base`, `mail`, `hr`, `hr_attendance`, `account`, `analytic`, `agronova_base`, `agronova_kassa`

## Tavsif

AgroNova — ish haqi moduli (TZ M09).

Odooning `hr_payroll` moduli o'rniga yozilgan. Sababi: O'zbekiston uchun
payroll lokalizatsiyasi mavjud emas, ya'ni barcha hisoblash qoidasini
baribir qo'lda yozish kerak bo'lardi — Odooning qoida dvigateli esa
Python parchalari bilan ishlaydi va uni brigadir ham, ishchi ham o'qiy
olmaydi. TZ talab qiladigan hisob esa sodda va aniq.

Nima bor:

* **uch xil tarif** — 26 kunlik oklad, 30 kunlik oklad, soatbay;
  tarif tarixi bilan yuritiladi, tasdiqlangani o'zgartirilmaydi;
* **oylik hisoblash hujjati** — xodimlar yig'iladi, ishlagan kun/soat
  davomatdan olinadi (bo'lmasa norma bo'yicha to'ldiriladi), avans,
  jarima va bonus qo'lda kiritiladi;
* **xodim balansi** — hisoblandi / berildi / qoldiq, brigadir depoziti
  bilan bir xil uslubda;
* **buxgalteriya provodkasi** — Dt ish haqi xarajati / Kt xodimga qarz;
* **storno** — provodka teskarilanadi, balans qatorlari o'chiriladi.

Ish haqini sex va partiyalarga taqsimlash bu modulning ishi emas — uni
bo'lim modullari qiladi (`agronova.ona_tovuq.ish_haqi` va h.k.), summani esa
shu yerdan oladi. Aks holda xarajat ikki marta sanalgan bo'lardi.

## Modellar

| Model | Tavsif | Maydonlar |
|---|---|---|
| `agronova.ish_haqi.davr` | Ish haqi — oylik hisoblash | `name`, `davr_boshi`, `davr_oxiri`, `company_id`, `currency_id`, `department_ids`, `qator_ids`, `xodim_soni`, `jami_hisoblangan`, `jami_bonus` … |
| `agronova.ish_haqi.davr.qator` | Ish haqi — hisoblash qatori | `davr_id`, `company_id`, `currency_id`, `employee_id`, `department_id`, `tarif_id`, `tur`, `stavka`, `manba`, `norma_kun` … |
| `agronova.ish_haqi.harakat` | Ish haqi — xodim bilan hisob-kitob harakati | `employee_id`, `sana`, `tur`, `summa`, `balans_summa`, `davr_id`, `company_id`, `currency_id`, `kassa_harakat_id`, `izoh` |
| `agronova.ish_haqi.tarif` | Ish haqi tarifi | `employee_id`, `tur`, `stavka`, `norma_kun`, `amal_sana`, `tugash_sana`, `company_id`, `currency_id`, `holat`, `izoh` |

Kengaytirilgan standart/boshqa modellar:

- `hr.employee`: `agronova_tarif_ids`, `agronova_tarif_id`, `agronova_tarif_turi`, `agronova_stavka`, `agronova_currency_id`, `agronova_harakat_ids`, `agronova_hisoblandi`, `agronova_berildi` …
- `res.config.settings`: `agronova_ish_haqi_account_xarajat`, `agronova_ish_haqi_account_qarz`, `agronova_ish_haqi_journal`
- `agronova.kassa.harakat`: `agronova_ish_haqi_harakat_id`

## Interfeys va huquqlar

- **Menyular:** Ish haqi · Hisoblash · Xodimlar · Oylik ish haqi · Xodimlar bilan hisob-kitob · Sozlamalar · Tariflar
- **Huquq guruhlari:** Ko'rish; Hisobchi

## O'rnatish, yangilash, test

Lokal (Windows, `Desktop\odoo` ichidan, Git Bash):

```bash
./venv/Scripts/python.exe run_odoo.py -c odoo-agronova.conf -d agronova -u agronova_ish_haqi --stop-after-init --no-http
```

Server: GitHub `novaodooteam/agronova-custom` ga push → serverda `git pull` + `-u <modul>`.
<!-- AUTO:END -->

## Eslatmalar va tuzoqlar

_Hozircha yo'q._
