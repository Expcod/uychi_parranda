# agronova_custom — AgroNova uchun Odoo 19 Enterprise modullari

**AgroNova** — parrandachilik holdingi. Biznes zanjiri:

```
Yem zavodi → Ona tovuq (tuxum) → Inkubatoriya (jo'ja) → Boquv (filiallar, binolar, partiyalar)
          → So'yish sexi → Go'sht ombori → Sotuv / POS do'kon → Kassa → Analitika
                               + Qishloq xo'jaligi, Transport, Xarid (zakupka), Ish haqi
```

- Ijrochi: «NOVA CODE» MCHJ. Demo: `demo.novaodoo.uz` / baza `agronova_demo` (1 bosh + 7 filial).
- Repo: `github.com/novaodooteam/agronova-custom` (`main`)
- TZ konspekti: [`docs/TZ_XULOSA.md`](docs/TZ_XULOSA.md), yangi TZ: [`docs/TZ_YANGI_2026-08-11.md`](docs/TZ_YANGI_2026-08-11.md)

## Brend va universallik (AgroNova)

Foydalanuvchi ko'radigan nom — **AgroNova** (modul nomlari, guruhlar, rahbar paneli). Texnik
nomlar (`agronova_*`, `agronova_*`) ataylab o'zgartirilmagan: ishlab turgan bazalardagi XML ID va
jadvallar buzilmasin. Panel nomi va texnologik normativlar **Sozlamalar → Rahbar paneli**
dan beriladi, shuning uchun bitta kod boshqa parrandachilik / agro korxonalariga ham
o'rnatiladi; o'rnatilmagan bo'limlar panelda avtomatik yashiriladi. Batafsil:
[`agronova_dashboard/README.md`](agronova_dashboard/README.md).

## Asosiy texnik qarorlar (TZ dan)

- Tannarx: **FIFO + avtomatik (perpetual)** baholash, Anglo-Saxon. Tannarx maydoni hamma uchun readonly.
- **Ikki qatlamli hisob**: moliyaviy (FIFO) va boshqaruv (tasdiqlangan ichki narx); oy oxirida ichki marja
  **elminatsiyasi** (`agronova.elminatsiya.mixin`).
- Har bo'lim — foyda markazi (analitik reja); filial = ombor + analitik; bino/sex = lokatsiya + analitik (m² majburiy);
  partiya = analitik hisob.
- Moliyaviy yozuv tahrirlanmaydi — faqat **storno**. Kontragent o'chirilmaydi — bloklanadi.
- Naqd xarajatda foto majburiy; xarajat analitik kesimsiz saqlanmaydi.
- Naqd xarajat **depozit**dan (mas'ul xodim naqdi, `agronova_savdo_moliya`) chiqadi.
- Standart Odoo imkoniyatlaridan maksimal foydalanish; OCA modullari bu o'rnatmada yo'q.

## Modullar

| Modul | Vazifasi | Ichki bog'liqlik |
|---|---|---|
| [`agronova_base`](agronova_base/README.md) | Umumiy mixin'lar: xarajat hujjati, taqsimlash bazasi, analitika, P&L, elminatsiya | — |
| [`agronova_savdo_moliya`](agronova_savdo_moliya/README.md) | Depozit egalari va balansi (minimal yadro) | agronova_base |
| [`agronova_kassa`](agronova_kassa/README.md) | Kassa kitobi, orderlar, kunlik yopish, transfer, inkassatsiya, 80mm chek | agronova_savdo_moliya |
| [`agronova_boquv`](agronova_boquv/README.md) | Boquv: filial, bino, partiya, kunlik jurnal, tannarx, so'yishga topshirish | agronova_base, agronova_telegram, agronova_savdo_moliya |
| [`agronova_ona_tovuq`](agronova_ona_tovuq/README.md) | Ona tovuq partiyalari, sexlar, tuxum tannarxi va sotuvi | agronova_base, agronova_savdo_moliya, agronova_soyish, agronova_ish_haqi, agronova_telegram |
| [`agronova_inkubatoriya`](agronova_inkubatoriya/README.md) | Tuxum qabuli → inkubatsiya → jo'ja ochilishi → tannarx | agronova_base, agronova_savdo_moliya, agronova_ona_tovuq |
| [`agronova_soyish`](agronova_soyish/README.md) | Qabul va tortish, so'yish, chiqim foizi, tashqi mijoz xizmati | agronova_base, agronova_savdo_moliya |
| [`agronova_yem_zavodi`](agronova_yem_zavodi/README.md) | Yem tannarxi (1 kg / 1 t), reja-fakt | — |
| [`agronova_qishloq_xojaligi`](agronova_qishloq_xojaligi/README.md) | Yer maydonlari, ekin partiyalari, hosil tannarxi | agronova_base, agronova_savdo_moliya |
| [`agronova_zakupka`](agronova_zakupka/README.md) | Xarid: zayavka → ruxsat → kirim → tranzit → ombor → Didox | agronova_base, agronova_savdo_moliya |
| [`agronova_ish_haqi`](agronova_ish_haqi/README.md) | Tariflar, oylik hisoblash, xodim balansi, provodka | agronova_base, agronova_kassa |
| [`agronova_pos`](agronova_pos/README.md) | Go'sht do'koni POS: tarozi, FEFO lot, kassa kitobi, kredit limiti | agronova_kassa |
| [`agronova_barcode`](agronova_barcode/README.md) | QR/barcode stikerlar, printerlar, qutilash, majburiy skanerlash | agronova_base |
| [`agronova_dashboard`](agronova_dashboard/README.md) | AgroNova rahbar paneli: 15 bo'lim, drill-down, 3D biznes xaritasi, oq yorliq, hisobotlar | (barcha bo'limlar) |
| [`agronova_transport`](agronova_transport/README.md) | Reys, reys loti, xarajatlar, foyda va haydovchi ulushi | — |
| [`agronova_telegram`](agronova_telegram/README.md) | Haydovchi reys xarajatini chek rasmi bilan Telegram orqali yuboradi | agronova_transport |
| [`hr_hikvision_attendance`](hr_hikvision_attendance/README.md) | Hikvision Face ID davomat | — |
| [`user_app_launcher`](user_app_launcher/README.md) | User formasida ilovalarga kirish grid'i | — |

Yordamchi papkalar: `scripts/` (demo bazani sozlash skriptlari `01_…17_`, [`scripts/README.md`](scripts/README.md)),
`docs/` (TZ konspekti, Excel shablonlar).

## Lokal ishga tushirish

Port **8071**, conf `odoo-agronova.conf` (`dbfilter = ^agronova.*$` — busiz cron boshqa loyiha bazasini ochadi).

```bash
cd "/c/Users/Surface PC/Desktop/odoo"
./venv/Scripts/python.exe run_odoo.py -c odoo-agronova.conf -d agronova -u <modul> --stop-after-init --no-http
# testlar (alohida nusxada, masalan agronova_zk_test)
./venv/Scripts/python.exe run_odoo.py -c odoo-agronova.conf -d agronova_zk_test -u <modul> \
    --test-enable --test-tags=<modul> --stop-after-init --no-http
```

- Prod backup `agronova_back_1208` lokal build'dan yangiroq Odoo'dan olingan — sxema xatolari chiqsa `-u` bilan tuzating.
- Backup'ni **filestore bilan** (Odoo zip) tiklang; faqat SQL tiklansa ilova ikonlari yo'qoladi
  (`ir.ui.menu.web_icon` ni qayta yozish bilan tiklanadi).
- `--test-tags=/modul` shakli Git Bash'da yo'lga aylanadi — tag nomini o'zini yozing yoki `MSYS_NO_PATHCONV=1`.

## Odoo 19 eslatmalari (shu loyihada uchragan)

- `stock.move.name` yo'q → `description_picking`; `stock.valuation.layer` yo'q → qiymat `stock.move.value` da.
- `res.users.group_ids` (`groups_id` emas); search view'da `<group>` ga `expand`/`string` berilmaydi.
- To'lov provodkasi faqat to'lov usulida "Outstanding" hisobi bo'lsa yaratiladi — naqd jurnallarda jurnalning
  o'z hisobini qo'ying.
- POS da lot tanlanmasa Odoo jimgina lotsiz chiqim qiladi — `agronova_pos` FEFO bilan o'zi tanlaydi.

> **Modul README'lari avtomatik yangilanadi:** har moduldagi `<!-- AUTO:BEGIN -->…<!-- AUTO:END -->` bloki koddan yig'iladi (Claude hook'i va git pre-commit, generator `Desktop/odoo/claude_tarix/tools/readme_yoz.py`). Blokni qo'lda tahrirlamang; "Eslatmalar va tuzoqlar" qismini esa qo'lda yangilab boring.
