<!-- AUTO:BEGIN — bu blok koddan avtomatik yangilanadi (claude_tarix/tools/readme_yoz.py), qo'lda tahrirlamang -->
# AgroNova — savdo va moliya (depozit yadrosi) (`agronova_savdo_moliya`)

> Depozit egalari, depozit balansi va naqd xarajatning depozitdan chiqimi

- **Loyiha:** AgroNova — parrandachilik holdingi (boquv, ona tovuq, inkubatoriya, so'yish, yem zavodi, qishloq xo'jaligi, savdo)
- **Versiya:** 19.0.1.0.0  ·  **Litsenziya:** LGPL-3
- **Bog'liqliklar:** `agronova_base`

## Tavsif

**Diqqat — bu modulning hozirgi hajmi ataylab minimal.**

TZ bo'yicha `agronova_savdo_moliya` katta modul: kassa, storno, chek, mijoz
qarzi, inkassatsiya. Ona Tovuq modulini yozish paytida bu modul hali
mavjud emas edi, lekin xarajat hujjatining «naqd» to'lov turi **depozitga**
bog'lanishi shart. Model egaligi (xmlid) keyin ko'chirilganda muammo
bo'lmasligi uchun `agronova.depozit` darhol o'z joyida — shu modulda —
yaratildi.

Hozircha shu narsa bor:

* `agronova.depozit` — depozit egasi (brigadir, ta'minotchi, bo'lim boshlig'i)
  va uning qoldig'i;
* `agronova.depozit.harakat` — depozitga kirim / depozitdan chiqim, har biri
  manba hujjatga bog'langan, o'chirilmaydi — faqat storno;
* `agronova.xarajat.mixin` kengaytmasi — naqd xarajatda depozit majburiy,
  tasdiqlanganda depozitdan avtomat chiqim yoziladi.

Kassa, chek va mijoz qarzi shu modulga keyingi bosqichda qo'shiladi.

## Modellar

| Model | Tavsif | Maydonlar |
|---|---|---|
| `agronova.depozit` | Depozit (mas'ul xodim naqdi) | `name`, `egasi_id`, `user_id`, `company_id`, `currency_id`, `harakat_ids`, `kirim`, `chiqim`, `balans`, `limit` … |
| `agronova.depozit.harakat` | Depozit harakati | `depozit_id`, `sana`, `turi`, `summa`, `currency_id`, `izoh`, `holat`, `manba_model`, `manba_id` |

Kengaytirilgan standart/boshqa modellar:

- `agronova.xarajat.mixin`: `depozit_id`, `depozit_harakat_id`

## Interfeys va huquqlar

- **Menyular:** Depozitlar

## O'rnatish, yangilash, test

Lokal (Windows, `Desktop\odoo` ichidan, Git Bash):

```bash
./venv/Scripts/python.exe run_odoo.py -c odoo-agronova.conf -d agronova -u agronova_savdo_moliya --stop-after-init --no-http
```

Server: GitHub `novaodooteam/agronova-custom` ga push → serverda `git pull` + `-u <modul>`.
<!-- AUTO:END -->

## Eslatmalar va tuzoqlar

- Hozircha ataylab minimal (depozit yadrosi). `agronova.depozit` model xmlid'i shu modulda — keyin model
  boshqa modulga ko'chirilsa, ikkala modul BIRGA `-u` qilinsin (aks holda jadval drop bo'ladi).
