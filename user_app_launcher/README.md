<!-- AUTO:BEGIN — bu blok koddan avtomatik yangilanadi (claude_tarix/tools/readme_yoz.py), qo'lda tahrirlamang -->
# User App Launcher (`user_app_launcher`)

> Foydalanuvchi formasida ilovalarga kirish huquqini vizual grid orqali boshqarish

- **Loyiha:** AgroNova — parrandachilik holdingi (boquv, ona tovuq, inkubatoriya, so'yish, yem zavodi, qishloq xo'jaligi, savdo)
- **Versiya:** 1.0  ·  **Litsenziya:** LGPL-3
- **Bog'liqliklar:** `base`

## Tavsif

Foydalanuvchi (res.users) formasiga yangi 'Ilovalar' bo'limi qo'shadi —
barcha o'rnatilgan ilovalar ikonka shaklida ko'rsatiladi, har biri
yonida shu foydalanuvchi kira oladigan/olmaydiganini bildiruvchi
yoqish/o'chirish tugmasi bor. Tugma bosilganda foydalanuvchi shu
ilovaning asosiy guruhiga qo'shiladi yoki undan chiqariladi.

## Modellar

Kengaytirilgan standart/boshqa modellar:

- `ir.ui.menu`: `app_restricted_user_ids`
- `res.users`: `app_access_grid_placeholder`

## O'rnatish, yangilash, test

Lokal (Windows, `Desktop\odoo` ichidan, Git Bash):

```bash
./venv/Scripts/python.exe run_odoo.py -c odoo-agronova.conf -d agronova -u user_app_launcher --stop-after-init --no-http
```

Server: GitHub `novaodooteam/agronova-custom` ga push → serverda `git pull` + `-u <modul>`.

Tarjimalar: `uz_UZ.po`, `uz_UZ@Cyrl.po`. JS dagi `_t()` satrlari .po da `#. odoo-javascript` + `.js` havolasi bilan bo'lishi shart.
<!-- AUTO:END -->

## Eslatmalar va tuzoqlar

_Hozircha yo'q._
