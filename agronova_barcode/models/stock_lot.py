import base64
import secrets

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Murakkab serial raqam alifbosi.
# Chalkashadigan belgilar (O/0, I/l/1) ATAYLAB olib tashlangan — xodim stikerdagi
# kodni ko'z bilan solishtirganda adashmasligi uchun.
SERIAL_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"      # I va O yo'q
SERIAL_LOWER = "abcdefghijkmnpqrstuvwxyz"         # l va o yo'q
SERIAL_DIGITS = "23456789"                        # 0 va 1 yo'q
# Maxsus belgilar. `^` va `~` ATAYLAB yo'q — ular ZPL (Zebra) printer tilining
# boshqaruv belgilari; `label_renderer._escape_zpl` ularni bo'sh joyga almashtiradi
# va QR ichidagi kod lot nomiga mos kelmay qolardi (skanerlash ishlamasdi).
# `"` va `\` ham yo'q — ular TSPL da escape talab qiladi.
SERIAL_SYMBOLS = "!@#$%&*+="                      # skaner/printerda xavfsiz belgilar
SERIAL_ALPHABET = SERIAL_LETTERS + SERIAL_LOWER + SERIAL_DIGITS + SERIAL_SYMBOLS
SERIAL_LENGTH = 8


class StockLot(models.Model):
    _inherit = "stock.lot"

    qr_code_image = fields.Binary(
        string="QR kod",
        compute="_compute_qr_code_image",
        help="Lot nomini kodlaydigan QR kod rasmi. Lot nomi o'zgarsa qayta hisoblanadi.",
    )

    qr_scan_required = fields.Boolean(
        "QR skanerlash shart",
        default=True,
        index=True,
        help="Transfer vaqtida bu seriya uchun majburiy QR skanerlash talab qilinadimi. "
             "Omborda avvaldan mavjud, stikeri yo'q tovarlar uchun buni o'chirib (False) "
             "qo'yish mumkin.",
    )

    # Stiker chop etilganini `agronova.label.print.job` dan hisoblab BO'LMAYDI —
    # `_gc_old_jobs` 30 kundan oshgan joblarni o'chiradi va yashil belgi qizilga
    # aylanib qolardi. Shuning uchun alohida saqlanadi.
    label_printed = fields.Boolean(
        "Stiker chop etilgan", default=False, copy=False, index=True,
        help="Bu lotning QR stikeri printerga muvaffaqiyatli yuborilganmi.",
    )
    label_printed_at = fields.Datetime("Stiker chop etilgan vaqt", copy=False, readonly=True)

    # Qadoqlashda har bir partiya og'irligi har xil bo'ladi (tovuq go'shti,
    # kolbasa) — mahsulot kartochkasidagi bitta og'irlik yetmaydi. Shuning
    # uchun og'irlik lotning o'zida saqlanadi va stikerga shundan chiqadi.
    label_weight = fields.Float(
        "Og'irligi (kg)", digits="Stock Weight", copy=False,
        help="Shu partiya/seriyaning haqiqiy og'irligi — qadoqlashda tarozidan "
             "kiritiladi. Bo'sh qoldirilsa stikerga mahsulot kartochkasidagi "
             "og'irlik chiqadi.",
    )

    @api.depends("name")
    def _compute_qr_code_image(self):
        for lot in self:
            if not lot.name:
                lot.qr_code_image = False
                continue
            try:
                # Odoo ichki barcode generatori (reportlab). QR lot nomini kodlaydi.
                png = self.env["ir.actions.report"].barcode(
                    "QR",
                    lot.name,
                    width=300,
                    height=300,
                    humanreadable=0,
                )
                lot.qr_code_image = base64.b64encode(png)
            except Exception:
                # Generatsiya muvaffaqiyatsiz bo'lsa (masalan nom bo'sh/xato),
                # forma buzilmasligi uchun bo'sh qoldiramiz.
                lot.qr_code_image = False

    # ------------------------------------------------------------------
    # Murakkab (random) serial raqam generatsiyasi
    # ------------------------------------------------------------------
    @api.model
    def _build_complex_serial(self):
        """Bitta 8 xonali murakkab kod yasaydi.

        Har kodda kamida bitta katta harf, kichik harf, raqam va maxsus belgi
        bo'lishi kafolatlanadi — shunda kod "oddiy raqam" ga o'xshab qolmaydi.
        `secrets` ishlatiladi (`random` emas), chunki kod taxmin qilinmasligi kerak.
        """
        required = [
            secrets.choice(SERIAL_LETTERS),
            secrets.choice(SERIAL_LOWER),
            secrets.choice(SERIAL_DIGITS),
            secrets.choice(SERIAL_SYMBOLS),
        ]
        rest = [secrets.choice(SERIAL_ALPHABET) for _i in range(SERIAL_LENGTH - len(required))]
        chars = required + rest
        # Majburiy belgilar doim boshida turmasligi uchun aralashtiramiz
        secrets.SystemRandom().shuffle(chars)
        return "".join(chars)

    @api.model
    def generate_complex_serials(self, count, product=None):
        """`count` ta TAKRORLANMAS murakkab serial nomi qaytaradi.

        Takrorlanmaslik ikki bosqichda ta'minlanadi:
          1) shu chaqiruv ichida — `taken` to'plami;
          2) bazadagi mavjud lotlarga qarshi — `stock.lot.name` bo'yicha qidiruv.

        Baza tekshiruvi mahsulotga bog'liq EMAS (butun `stock.lot` bo'ylab), chunki
        talab: bir marta generatsiya bo'lgan seriya boshqa qayta chiqmasin.
        """
        count = int(count or 0)
        if count <= 0:
            return []

        Lot = self.env["stock.lot"].sudo()
        names = []
        taken = set()
        # Har kod uchun cheklangan urinish — to'qnashuv deyarli bo'lmaydi
        # (alifbo 64 belgi, 8 xona), lekin cheksiz sikl bo'lmasligi kerak.
        max_attempts = count * 20 + 50
        attempts = 0
        while len(names) < count:
            attempts += 1
            if attempts > max_attempts:
                raise UserError(_(
                    "Takrorlanmas serial raqam yaratib bo'lmadi. "
                    "Administratorga murojaat qiling."
                ))
            candidate = self._build_complex_serial()
            if candidate in taken:
                continue
            if Lot.search_count([("name", "=", candidate)], limit=1):
                continue
            taken.add(candidate)
            names.append(candidate)
        return names

    @api.depends("product_id")
    def _compute_name(self):
        """Ombor/inventarizatsiya oynasida ham murakkab kod chiqishi uchun.

        Odoo standarti bo'sh nomni mahsulotning `lot_sequence_id` ketma-ketligidan
        to'ldiradi (`0000043` → `0000044`). Bu yo'l `generate_lot_names` dan
        MUSTAQIL — shuning uchun inventarizatsiya (`stock.quant`), qabul qilish va
        lot formasida "yangi" bosilganda oddiy raqam chiqib qolardi.

        Sozlama o'chirilgan bo'lsa Odoo standart xulqi qaytadi.
        """
        if not self._complex_serials_enabled():
            return super()._compute_name()

        blanks = self.filtered(lambda lot: not lot.name)
        if blanks:
            names = self.generate_complex_serials(len(blanks))
            for lot, name in zip(blanks, names):
                lot.name = name
        for lot in self - blanks:
            lot.name = lot.name

    @api.model
    def generate_lot_names(self, first_lot, count):
        """Odoo standart ketma-ket generatorini murakkab kod bilan almashtiradi.

        Standart xulq (`0000353` → `0000354` → ...) taxmin qilinadigan raqam beradi.
        Sozlama (`agronova_barcode.complex_serials`) yoqilgan bo'lsa — MO dagi
        "Serial raqamlarni yaratish" oynasi ham 8 xonali murakkab kod beradi.

        Sozlama o'chirilgan bo'lsa Odoo standart xulqi qaytadi.
        """
        if not self._complex_serials_enabled():
            return super().generate_lot_names(first_lot, count)
        return [{"lot_name": name} for name in self.generate_complex_serials(count)]

    @api.model
    def _complex_serials_enabled(self):
        """Murakkab serial rejimi yoqilganmi (Sozlamalar → Ombor)."""
        return self.env["ir.config_parameter"].sudo().get_param(
            "agronova_barcode.complex_serials", "False"
        ) in ("True", "true", "1", True)

    # ------------------------------------------------------------------
    # Stiker chop etish
    # ------------------------------------------------------------------
    def _default_label_printer(self):
        """Birinchi faol printer. Bittasi bo'lsa tanlash so'ralmaydi."""
        return self.env["agronova.label.printer"].search([], limit=1)

    def action_print_qr_label(self):
        """Stikerni printerga yuboradi — PDF ochilmaydi.

        Printer sozlanmagan bo'lsa foydalanuvchini sozlash sahifasiga yo'naltiradi.
        Bir nechta printer bo'lsa tanlash oynasi ochiladi.
        """
        lots = self.filtered("name")
        if not lots:
            raise UserError(_("Lot raqami yo'q — stiker chop etib bo'lmaydi."))

        printers = self.env["agronova.label.printer"].search([])
        if not printers:
            raise UserError(_(
                "Stiker printeri sozlanmagan.\n\n"
                "Ombor > Sozlamalar > Stiker printerlari bo'limida printer qo'shing."
            ))

        if len(printers) > 1:
            return {
                "type": "ir.actions.act_window",
                "name": _("Stiker chop etish"),
                "res_model": "agronova.label.print.wizard",
                "view_mode": "form",
                "target": "new",
                "context": {"default_lot_ids": lots.ids},
            }

        jobs = printers.print_lots(lots)
        return self._label_print_notification(jobs, printers)

    @api.model
    def _label_print_notification(self, jobs, printer):
        failed = jobs.filtered(lambda j: j.state == "failed")
        if failed:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Chop etishda xato"),
                    "message": failed[0].error or _("Noma'lum xato"),
                    "type": "danger",
                    "sticky": True,
                },
            }

        if printer.delivery == "local":
            message = _("%d ta stiker chop etildi.") % len(jobs)
        else:
            message = _("%d ta stiker navbatga qo'yildi.") % len(jobs)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"message": message, "type": "success", "sticky": False},
        }
