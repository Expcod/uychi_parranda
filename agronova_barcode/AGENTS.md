# AGENTS.md — `agronova_barcode` moduli uchun AI agent qo'llanmasi

> **Bu fayl haqida:** `agronova_barcode` Odoo modulining texnik hujjati.
> Modulga har qanday o'zgarish kiritilganda ushbu faylni yangilash SHART.
>
> **Yaratilgan:** 2026-08-31
> **Manba:** `filtruz-custom/stock_lot_qr_label` (19.0.1.2.1) moduli baza qilib
> olindi, model nomlari `agronova.` prefiksiga o'tkazildi va TZ talablari qo'shildi.

---

## 1. Modulning maqsadi

Ombor TZ (`docs/tz_2026-08-11/01_ombor.txt`, 8-band «Barcode va QR Code») va
So'yish TZ (8.2 «Qadoqlash», 9 «Tayyor mahsulot ombori») talablarini bajaradi:

* mahsulot/partiyani **QR** va **chiziqli barcode** bilan identifikatsiya qilish;
* **etiketka printeri** (Xprinter/TSC — TSPL, Zebra — ZPL) bilan ishlash;
* **skaner** orqali qabul qilish va jo'natishni nazorat qilish;
* etiketkada: mahsulot nomi, og'irligi, ishlab chiqarilgan sana, yaroqlilik
  muddati, partiya, barcode.

---

## 2. Modellar

### `agronova.label.printer` — stiker printeri
Bitta yozuv = bitta fizik printer. Har printerning o'z stiker o'lchami, tili va
harflar to'plami bo'ladi.

| Guruh | Maydonlar |
|---|---|
| Ulanish | `system_name` (Windows'dagi nom), `language` (tspl/zpl), `charset` (kirill/lotin/turk/utf8), `delivery` (queue/local), `agent_token` |
| O'lcham | `label_width`, `label_height`, `gap_mm` |
| Mazmuni | `show_name`, `show_lot`, `show_date`, `show_weight`, `show_expiry` va ularning shriftlari |
| Kod | `code_mode` (qr / barcode / both), `qr_auto`, `qr_cell`, `barcode_type` (128/EAN13), `barcode_source` (lot/product), `barcode_height_mm`, `barcode_human` |
| Quti | `box_show_count`, `box_show_date`, `box_date_font`, `box_date_format` |
| Sifat | `density`, `speed` |
| Preview | `preview_image`, `box_preview_image`, `fits`, `qr_size_mm` (compute, store=False) |

Asosiy metodlar: `build_payload(lot)`, `_build_box_payload(box)`,
`print_lots(lots)`, `action_test_print()`, `action_reset_token()`,
`_lot_data(lot)` (stikerga chiqadigan ma'lumot), `_lot_barcode`, `_weight_text`,
`_expiry_text`.

### `agronova.label.print.job` — chop etish navbati
Odoo job yaratadi → sexdagi agent dasturi `agent_fetch(token)` bilan oladi →
printerga yuboradi → `agent_report(token, results)` bilan natijani qaytaradi.
Shu sxema tufayli server VPS'da bo'lsa ham chop etish ishlaydi.
`delivery="local"` bo'lsa Odoo `win32print` orqali o'zi bosadi.
Job `done` bo'lganda lotning `label_printed` belgisi qo'yiladi.
`@api.autovacuum` 30 kundan oshgan joblarni tozalaydi.

### `stock.lot` (inherit)
* `qr_code_image` — lot nomini kodlovchi QR (compute).
* `label_printed`, `label_printed_at` — stiker chop etilganlik holati.
* `qr_scan_required` (default `True`) — transferda majburiy skanerlash. Eski,
  stikersiz tovarlar uchun `False` qilinadi.
* `label_weight` — **YANGI**: shu partiyaning haqiqiy og'irligi (kg). Qadoqlashda
  tarozidan kiritiladi; bo'sh bo'lsa stikerga mahsulot og'irligi chiqadi.
* `expiration_date` — `product_expiry` dan keladi, stikerdagi «Muddat:» qatori.
* `generate_complex_serials(count)` — 8 xonali murakkab serial kod
  (`K7#mQ2@x` kabi). **AgroNova'da default O'CHIQ** (`agronova_barcode.complex_serials`
  = `False`) — mavjud lot nomlash tartibi o'zgarmasligi uchun. Sozlamalardan
  yoqiladi.

### `agronova.lot.box` — qutilash
Sig'im bo'yicha seriallarni bitta quti kodiga birlashtiradi (`BOX-` prefiksi).
Transferda bitta quti kodini skanerlash ichidagi barcha seriyalarni o'tkazadi.

### `stock.picking` (inherit) — majburiy skanerlash
* `qr_scan_required` / `qr_scan_done` (compute) — transferda serial mahsulot
  bormi va hammasi skanerlanganmi.
* `_qr_scan_progress()` → `(skanerlangan, talab)`. `lot_id.qr_scan_required = False`
  bo'lgan qatorlar skanerlangan deb hisoblanadi.
* `_drop_unscanned_reservations()` — skanerlanmagan rezervlarni tozalaydi.
* `button_validate()` — skanerlash to'liq bo'lmasa transferni to'xtatadi.

### `stock.picking.type` (inherit)
* `qr_scan_exempt` — bu operatsiya turida skanerlash talab qilinmaydi
  (masalan sotuv agentining mijozga yetkazishi).

### `product.template` (inherit) — **YANGI**
* `action_generate_ean13()` — belgilangan mahsulotlarga ichki EAN-13 kod beradi
  (`200` + mahsulot id + tekshiruv raqami). Barcode'i bor mahsulot chetlab
  o'tiladi. Mahsulot ro'yxatidagi **Amallar → EAN-13 barcode yaratish** orqali
  (`data/product_barcode_action.xml`, `ir.actions.server`).

### Wizardlar
`agronova.label.print.wizard` (printer tanlash), `agronova.lot.box.wizard` (qutilash),
`agronova.picking.qr.scan` + `.product` (transferda skanerlash oynasi),
`agronova.picking.qr.bypass` (menejer uchun istisno), `agronova.quant.serial.wizard`
(inventarizatsiyada seriyalar).

---

## 3. `models/label_renderer.py` — stiker chizish yadrosi

Odoo'ga bog'liq emas (toza Python), shuning uchun alohida sinash oson.
203 DPI, 1 mm = 8 nuqta.

* `build_layout(config, data)` → `LabelLayout`. Uch blok: **tepa** — mahsulot
  nomi, **o'rta** — QR va/yoki chiziqli kod, **past** — lot, quti soni,
  og'irlik, sana, muddat. Bo'sh joy bloklar orasiga teng taqsimlanadi.
* `to_tspl(layout, config)` / `to_zpl(...)` — printer buyruqlari.
* `to_preview_png(layout)` — Odoo formasidagi jonli ko'rinish (Pillow + qrcode;
  chiziqli kod uchun reportlab).
* **Chiziqli kod yordamchilari (YANGI):** `barcode_modules()`,
  `normalize_barcode()` (EAN-13 ga mos kelmasa jimgina Code128 ga o'tadi),
  `best_narrow()` (stiker kengligiga sig'adigan eng katta modul kengligi),
  `LabelLayout.add_barcode()`.
* `encode_payload()` — kirill matn CP1251 da yuboriladi, aks holda printerning
  ichki shrifti buzib chiqaradi.

**Muhim:** lot nomida `^`, `~`, `"`, `\` belgilari BO'LMASLIGI kerak — ular ZPL
va TSPL boshqaruv belgilari (`stock_lot.SERIAL_SYMBOLS` shuni hisobga olgan).

---

## 4. Agent dasturi (`agent/`)

Sexdagi Windows kompyuterda ishlaydigan tray dasturi (PyInstaller bilan
yig'iladi). `agent.ini` da server URL, baza, login va printer `agent_token`
ko'rsatiladi. RPC orqali `agronova.label.print.job` modeliga murojaat qiladi:
`agent_fetch` → chop etadi → `agent_report`.

Yig'ish: `agent/build.ps1`.

---

## 5. Bog'liqliklar

`stock`, `product_expiry` (yaroqlilik muddati), `agronova_base`.
Python: `qrcode`, `Pillow` (preview uchun; chop etishga shart emas),
`reportlab` (Odoo bilan keladi), Windows lokal chop etish uchun `pywin32`.

---

## 6. O'zgarish kiritilganda

* Model/maydon qo'shilsa — shu faylni va `security/ir.model.access.csv` ni
  yangilang.
* `label_renderer.py` o'zgarsa — `build_layout` → `to_tspl`/`to_zpl` → preview
  uchligi mos qolishini tekshiring (preview printerdan chiqadigan bilan bir xil
  bo'lishi kerak).
* **`-u agronova_barcode` SHART** (view va maydonlar yangilanishi uchun).
