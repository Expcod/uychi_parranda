<!-- AUTO:BEGIN — bu blok koddan avtomatik yangilanadi (claude_tarix/tools/readme_yoz.py), qo'lda tahrirlamang -->
# AgroNova — Barcode, QR, printer va skaner (`agronova_barcode`)

> Lot/seriya uchun QR va chiziqli barcode stikerlari, stiker printerlari (TSPL/ZPL), chop etish navbati va agenti, qutilash, transferda majburiy skanerlash.

- **Loyiha:** AgroNova — parrandachilik holdingi (boquv, ona tovuq, inkubatoriya, so'yish, yem zavodi, qishloq xo'jaligi, savdo)
- **Versiya:** 19.0.1.0.0  ·  **Litsenziya:** LGPL-3
- **Bog'liqliklar:** `stock`, `product_expiry`, `agronova_base`

## Tavsif

AgroNova — Barcode / QR integratsiyasi
Ombor TZ (8-band: «Barcode va QR Code») va So'yish TZ (8.2: qadoqlash etiketkasi)
talablarini bajaradi.

Nima qiladi
* **QR kod** — har bir lot/seriya nomini kodlaydi, Odoo Barcode ilovasi va oddiy
  skaner uni o'qiy oladi.
* **Chiziqli barcode** — Code128 yoki EAN-13. Mahsulotning `barcode` maydonidan
  yoki lot nomidan olinadi. Stikerda QR bilan birga ham chiqishi mumkin.
* **Etiketka mazmuni** — mahsulot nomi, QR/barcode, partiya raqami, og'irligi (kg),
  ishlab chiqarilgan sana va yaroqlilik muddati. Har bir element printer
  sozlamasida alohida yoqiladi/o'chiriladi.
* **Stiker printerlari** — har printer uchun alohida yozuv: o'lchami, tili
  (TSPL/ZPL), harflar to'plami (kirill), qoraligi va tezligi. Formada jonli
  ko'rinish (preview) — chop etishdan oldin sig'ishi ko'rinadi.
* **Chop etish navbati + agent** — server uzoqda (VPS) bo'lsa ham sexdagi agent
  dasturi navbatni olib printerga yuboradi.
* **Qutilash** — bir nechta seriyani bitta quti kodiga birlashtirish, quti QR ini
  bir marta skanerlab hammasini o'tkazish.
* **Transferda majburiy skanerlash** — qabul/jo'natishda seriyalar skanerlanmasa
  transfer tasdiqlanmaydi (operatsiya turi bo'yicha istisno berish mumkin).

## Modellar

| Model | Tavsif | Maydonlar |
|---|---|---|
| `agronova.label.printer` | Stiker printeri | `name`, `sequence`, `active`, `system_name`, `language`, `delivery`, `agent_token`, `charset`, `label_width`, `label_height` … |
| `agronova.label.print.job` | Stiker chop etish ishi | `printer_id`, `lot_id`, `copies`, `payload`, `note`, `state`, `error`, `sent_at`, `done_at` |
| `agronova.lot.box` | Mahsulot qutisi (jamlangan QR) | `name`, `product_id`, `lot_ids`, `lot_count`, `capacity`, `date`, `company_id`, `printed`, `note` |
| `agronova.label.print.wizard` _(wizard)_ | Stiker chop etish | `printer_id`, `lot_ids`, `box_ids`, `copies`, `total_labels` |
| `agronova.lot.box.wizard` _(wizard)_ | Qutiga solish va chop etish | `lot_ids`, `lot_count`, `in_box_count`, `box_count`, `printer_id`, `date`, `mode`, `capacity` |
| `agronova.picking.qr.scan` _(wizard)_ | Transferda QR skanerlash | `picking_id`, `scan_code`, `last_status`, `last_message`, `scan_seq`, `progress_info`, `scanned_qty`, `demand_qty`, `is_done`, `line_ids` … |
| `agronova.picking.qr.scan.product` _(wizard)_ | Skanerlash oynasi — mahsulot holati | `wizard_id`, `product_id`, `demand_qty`, `scanned_qty`, `remaining_qty`, `is_complete` |
| `agronova.picking.qr.bypass` _(wizard)_ | QR skanerlashni chetlab o'tish | `picking_id`, `reason` |
| `agronova.quant.serial.wizard` _(wizard)_ | Serial miqdorini o'zgartirish | `product_id`, `product_locked`, `location_id`, `company_id`, `current_qty`, `count`, `diff`, `diff_mode`, `removal_mode`, `removal_lot_ids` … |

Kengaytirilgan standart/boshqa modellar:

- `ir.actions.report`
- `product.product`
- `product.template`
- `res.config.settings`: `lot_qr_label_width`, `lot_qr_label_height`, `lot_complex_serials`
- `stock.lot`: `qr_code_image`, `qr_scan_required`, `label_printed`, `label_printed_at`, `label_weight`
- `stock.move.line`: `qr_scanned`, `qr_box_id`
- `stock.picking`: `qr_scan_required`, `qr_scan_done`, `qr_scan_info`, `qr_scan_bypassed`
- `stock.move`
- `stock.picking.type`: `qr_scan_exempt`
- `stock.quant`: `qr_scan_required`, `label_state`, `label_printed_at`

## Interfeys va huquqlar

- **Menyular:** QR Stiker va Qutilar · Qutilar · Qutilar ro'yxati · Serial raqamlar · Barcha serial raqamlar · Ombor qoldiqlari (Seriyalar) · Printerlar va Navbat · Stiker printerlari · Chop etish navbati · Sozlamalar · Umumiy sozlamalar

## O'rnatish, yangilash, test

Lokal (Windows, `Desktop\odoo` ichidan, Git Bash):

```bash
./venv/Scripts/python.exe run_odoo.py -c odoo-agronova.conf -d agronova -u agronova_barcode --stop-after-init --no-http
```

Server: GitHub `novaodooteam/agronova-custom` ga push → serverda `git pull` + `-u <modul>`.
<!-- AUTO:END -->

## Eslatmalar va tuzoqlar

- Transferda majburiy QR skanerlash (`qr_scan_required`), menejer uchun "chetlab o'tish" (bypass) sabab bilan.
- Filtruzdagi `stock_lot_qr_label` bilan bir xil g'oya — Filtruz tahlilida ichki transferlarning ~30% i
  bypass bilan o'tgani aniqlangan; bypass'ni cheklash rejalashtirilsin.
