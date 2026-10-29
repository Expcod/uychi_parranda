"""Stiker printeri: sozlamalari, jonli preview va sinov chop etish.

Bitta printer yozuvi = bitta fizik printer. Sozlamalar shu yerda
saqlanadi, chunki har printerning stiker o'lchami va tili boshqacha
bo'lishi mumkin.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from . import label_renderer as lr

FONT_SELECTION = [
    ("1", "Juda kichik"),
    ("2", "Kichik"),
    ("3", "O'rtacha"),
    ("4", "Katta"),
    ("5", "Juda katta"),
]


class StockLabelPrinter(models.Model):
    _name = "agronova.label.printer"
    _description = "Stiker printeri"
    _order = "sequence, id"

    name = fields.Char("Nomi", required=True, help="Masalan: 3-sex Xprinter")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    system_name = fields.Char(
        "Tizimdagi nomi", required=True,
        help="Windows'dagi printer nomi — aynan shundayligiga ishonch hosil qiling.\n"
             "Masalan: Xprinter XP-365B",
    )
    language = fields.Selection(
        [("tspl", "TSPL (Xprinter, TSC)"), ("zpl", "ZPL (Zebra)")],
        string="Printer tili", default="tspl", required=True,
        help="Printer qaysi buyruq tilini tushunadi. Xprinter uchun odatda TSPL.",
    )
    delivery = fields.Selection(
        [("queue", "Navbat orqali (agent)"), ("local", "To'g'ridan-to'g'ri (faqat lokal)")],
        string="Yetkazish usuli", default="queue", required=True,
        help="Navbat: sexdagi agent dasturi chop etadi — server uzoqda bo'lsa ham ishlaydi.\n"
             "To'g'ridan-to'g'ri: Odoo o'zi chop etadi — faqat printer server bilan "
             "bitta kompyuterda bo'lsa.",
    )
    agent_token = fields.Char(
        "Agent kaliti", copy=False,
        help="Agent dasturi shu kalit bilan o'z navbatini oladi.",
    )
    charset = fields.Selection(
        [
            ("cyrillic", "Kirill (о'zbek, rus)"),
            ("latin", "Lotin (g'arbiy Yevropa)"),
            ("turkish", "Turk"),
            ("utf8", "UTF-8 (zamonaviy printerlar)"),
        ],
        string="Harflar to'plami", default="cyrillic", required=True,
        help="Mahsulot nomida kirill harflari bo'lsa 'Kirill' ni tanlang.\n"
             "Stikerda tushunarsiz belgilar chiqsa — boshqasini sinab ko'ring.",
    )

    # --- stiker o'lchami ---
    label_width = fields.Float("Kenglik (mm)", default=40.0, required=True)
    label_height = fields.Float("Balandlik (mm)", default=30.0, required=True)
    gap_mm = fields.Float("Stikerlar orasi (mm)", default=2.0)

    # --- mazmuni ---
    show_name = fields.Boolean("Mahsulot nomi", default=True)
    show_lot = fields.Boolean("Lot raqami", default=True)
    show_date = fields.Boolean("Sana", default=True)
    show_weight = fields.Boolean(
        "Og'irligi", default=False,
        help="Stikerda mahsulot og'irligi chiqadi (masalan \"1.250 kg\").\n"
             "Og'irlik lotning \"Og'irligi\" maydonidan, u bo'sh bo'lsa "
             "mahsulot kartochkasidagi og'irlikdan olinadi.",
    )
    show_expiry = fields.Boolean(
        "Yaroqlilik muddati", default=False,
        help="Stikerda \"Muddat: 12.09.2026\" qatori chiqadi. Lotda yaroqlilik "
             "muddati kiritilgan bo'lishi kerak (mahsulotda muddat hisobi yoqilsa "
             "Odoo uni avtomatik hisoblaydi).",
    )

    name_font = fields.Selection(FONT_SELECTION, "Nom shrifti", default="1", required=True)
    lot_font = fields.Selection(FONT_SELECTION, "Lot shrifti", default="2", required=True)
    date_font = fields.Selection(FONT_SELECTION, "Sana shrifti", default="1", required=True)
    weight_font = fields.Selection(
        FONT_SELECTION, "Og'irlik shrifti", default="2", required=True)
    expiry_font = fields.Selection(
        FONT_SELECTION, "Muddat shrifti", default="1", required=True)

    # --- kod turi: QR va/yoki chiziqli barcode ---
    code_mode = fields.Selection(
        [
            ("qr", "Faqat QR"),
            ("barcode", "Faqat chiziqli kod"),
            ("both", "QR va chiziqli kod"),
        ],
        string="Kod turi", default="qr", required=True,
        help="QR — telefon va 2D skaner o'qiydi, ko'p ma'lumot sig'adi.\n"
             "Chiziqli kod — oddiy (lazerli) skanerlar uchun; kassa va "
             "ta'minotchi tizimlari shuni talab qiladi.",
    )
    barcode_type = fields.Selection(
        [("128", "Code 128 (har qanday matn)"), ("EAN13", "EAN-13 (13 xonali raqam)")],
        string="Chiziqli kod turi", default="128", required=True,
        help="Code 128 — lot nomi kabi harf-raqamli kodlar uchun.\n"
             "EAN-13 — faqat 12/13 xonali raqam. Kod mos kelmasa avtomatik "
             "Code 128 ga o'tadi (stiker bo'sh chiqib qolmasligi uchun).",
    )
    barcode_source = fields.Selection(
        [
            ("lot", "Lot/seriya raqami"),
            ("product", "Mahsulot barcode'i"),
        ],
        string="Chiziqli kod manbasi", default="lot", required=True,
        help="Lot — har bir partiya/seriya alohida kod oladi (kuzatuv uchun).\n"
             "Mahsulot barcode'i — bir xil mahsulotda kod bir xil bo'ladi "
             "(kassa va sotuv uchun). Mahsulotda barcode bo'lmasa lot nomi olinadi.",
    )
    barcode_height_mm = fields.Float(
        "Chiziqli kod balandligi (mm)", default=8.0,
        help="Chiziqlar balandligi. Kamida 6-8 mm bo'lgani skaner uchun qulay.",
    )
    barcode_human = fields.Boolean(
        "Kod ostida raqamlar", default=True,
        help="Chiziqli kod ostida uning matni chiqadi — skaner o'qimasa xodim "
             "qo'lda kiritishi mumkin.",
    )

    # --- quti (box) stikeri mazmuni ---
    box_show_count = fields.Boolean(
        "Quti: ichidagi soni", default=True,
        help="Quti stikerida \"30 dona\" kabi ichidagi mahsulot soni chiqadi.",
    )
    box_show_date = fields.Boolean(
        "Quti: sana", default=True,
        help="Quti stikerida quti yaratilgan sana chiqadi.",
    )
    box_date_font = fields.Selection(
        FONT_SELECTION, "Quti sana shrifti", default="1", required=True,
    )
    box_date_format = fields.Selection(
        [
            ("date", "Faqat sana (21.08.2026)"),
            ("datetime", "Sana va soat (21.08.2026 14:30)"),
        ],
        string="Quti sana ko'rinishi", default="date", required=True,
    )

    qr_auto = fields.Boolean(
        "QR avtomatik", default=True,
        help="Yoqilgan bo'lsa QR stikerga sig'adigan eng katta o'lchamda chiqadi.",
    )
    qr_cell = fields.Integer(
        "QR o'lchami", default=6,
        help="QR nuqtasining kattaligi (2-12). 'QR avtomatik' o'chirilganda ishlatiladi.",
    )

    # --- chop etish sifati ---
    density = fields.Integer("Qoraligi", default=8, help="0-15. Yuqori qiymat qoraroq bosadi.")
    speed = fields.Integer("Tezligi", default=4, help="1-6 dyuym/sek.")

    # --- sinov ---
    test_product_id = fields.Many2one(
        "product.product", string="Sinov mahsuloti",
        help="Sinab chop etishda shu mahsulot nomi chiqadi.\n"
             "Bo'sh qoldirilsa — bazadagi birinchi lot olinadi.",
    )

    # --- preview ---
    preview_image = fields.Binary("Ko'rinishi", compute="_compute_preview", store=False)
    preview_info = fields.Char("Holat", compute="_compute_preview", store=False)
    fits = fields.Boolean(compute="_compute_preview", store=False)
    qr_size_mm = fields.Float(
        "QR o'lchami (mm)", compute="_compute_preview", store=False, digits=(4, 1),
        help="QR kodning stikerdagi haqiqiy o'lchami.",
    )
    box_preview_image = fields.Binary(
        "Quti stikeri", compute="_compute_box_preview", store=False)
    box_preview_info = fields.Char(
        "Quti holati", compute="_compute_box_preview", store=False)

    # Odoo 19: `_sql_constraints` jimgina e'tiborsiz qoldiriladi — models.Constraint.
    _agent_token_uniq = models.Constraint(
        "unique(agent_token)", "Agent kaliti takrorlanmasligi kerak.")

    # Harflar to'plami -> (TSPL kod sahifasi, Python kodlashi)
    CHARSETS = {
        "cyrillic": ("1251", "cp1251"),
        "latin": ("1252", "cp1252"),
        "turkish": ("1254", "cp1254"),
        "utf8": ("UTF-8", "utf-8"),
    }

    @property
    def codepage(self):
        return self.CHARSETS.get(self.charset, self.CHARSETS["cyrillic"])[0]

    @property
    def encoding(self):
        return self.CHARSETS.get(self.charset, self.CHARSETS["cyrillic"])[1]

    # ------------------------------------------------------------------
    # Sozlama -> renderer
    # ------------------------------------------------------------------
    def _render_config(self):
        self.ensure_one()
        return {
            "label_width": self.label_width,
            "label_height": self.label_height,
            "gap_mm": self.gap_mm,
            "qr_cell": self.qr_cell,
            "qr_auto": self.qr_auto,
            "show_name": self.show_name,
            "show_lot": self.show_lot,
            "show_date": self.show_date,
            "show_weight": self.show_weight,
            "show_expiry": self.show_expiry,
            "name_font": self.name_font,
            "lot_font": self.lot_font,
            "date_font": self.date_font,
            "weight_font": self.weight_font,
            "expiry_font": self.expiry_font,
            "code_mode": self.code_mode,
            "barcode_type": self.barcode_type,
            "barcode_height_mm": self.barcode_height_mm,
            "barcode_human": self.barcode_human,
            "box_show_count": self.box_show_count,
            "box_show_date": self.box_show_date,
            "box_date_font": self.box_date_font,
            "box_date_format": self.box_date_format,
            "density": self.density,
            "speed": self.speed,
            "codepage": self.codepage,
        }

    def _sample_data(self):
        """Preview va sinov uchun namuna.

        Mahsulot tanlangan bo'lsa uning nomi olinadi — shunda haqiqiy nom
        (kirill harflar bilan) chop etishdan oldin previewda ko'rinadi.
        Tanlanmagan bo'lsa bazadagi birinchi lot, u ham bo'lmasa namuna.
        """
        if self.test_product_id:
            lot = self.env["stock.lot"].search(
                [("product_id", "=", self.test_product_id.id)], limit=1)
            if lot:
                return self._lot_data(lot)
            return dict(
                self._sample_extras(),
                product_name=self.test_product_id.display_name or "",
                lot_name="SINOV-000001",
                barcode=(self.test_product_id.barcode or "SINOV-000001"
                         if self.barcode_source == "product" else "SINOV-000001"),
                date=fields.Date.to_string(fields.Date.context_today(self)),
            )
        lot = self.env["stock.lot"].search([], limit=1)
        if lot:
            return self._lot_data(lot)
        return dict(
            self._sample_extras(),
            product_name=_("NAMUNA MAHSULOT"),
            lot_name="LOT-00000-000001",
            barcode="LOT-00000-000001",
            date=fields.Date.to_string(fields.Date.context_today(self)),
        )

    def _sample_extras(self):
        """Previewda og'irlik/muddat qatorlari qanday ko'rinishini ko'rsatadi."""
        self.ensure_one()
        today = fields.Date.context_today(self)
        return {
            "weight": "1.25 kg" if self.show_weight else "",
            "expiry": (_("Muddat: %s") % today.strftime("%d.%m.%Y")
                       if self.show_expiry else ""),
        }

    def _lot_data(self, lot):
        return {
            "product_name": lot.product_id.display_name or "",
            "lot_name": lot.name or "",
            "date": fields.Date.to_string(
                fields.Date.context_today(self, lot.create_date) if lot.create_date
                else fields.Date.context_today(self)
            ),
            "barcode": self._lot_barcode(lot),
            "weight": self._weight_text(lot),
            "expiry": self._expiry_text(lot),
        }

    def _lot_barcode(self, lot):
        """Chiziqli kodga yoziladigan qiymat.

        Sozlamaga qarab lot nomi (har partiya alohida kod) yoki mahsulot
        barcode'i (kassada bir xil mahsulot bir xil kod). Mahsulotda barcode
        bo'lmasa lot nomiga qaytamiz — stiker kodsiz chiqib qolmasligi kerak.
        """
        self.ensure_one()
        if self.barcode_source == "product" and lot.product_id.barcode:
            return lot.product_id.barcode
        return lot.name or ""

    def _weight_text(self, lot):
        """Stikerdagi og'irlik matni ("1.25 kg").

        Avval lotning o'z og'irligi olinadi (qadoqlashda tarozidan kiritiladi),
        u bo'sh bo'lsa mahsulot kartochkasidagi og'irlik ishlatiladi.
        """
        self.ensure_one()
        if not self.show_weight:
            return ""
        weight = lot.label_weight or lot.product_id.weight or 0.0
        if not weight:
            return ""
        text = ("%.3f" % weight).rstrip("0").rstrip(".")
        return "%s %s" % (text, lot.product_id.weight_uom_name or "kg")

    def _expiry_text(self, lot):
        """Yaroqlilik muddati. Lotda muddat yo'q bo'lsa qator umuman chiqmaydi."""
        self.ensure_one()
        if not self.show_expiry or not lot.expiration_date:
            return ""
        local = fields.Datetime.context_timestamp(self, lot.expiration_date)
        return _("Muddat: %s") % local.strftime("%d.%m.%Y")

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------
    @api.depends("label_width", "label_height", "qr_cell", "qr_auto",
                 "show_name", "show_lot", "show_date", "show_weight", "show_expiry",
                 "name_font", "lot_font", "date_font", "weight_font", "expiry_font",
                 "code_mode", "barcode_type", "barcode_source", "barcode_height_mm",
                 "barcode_human", "test_product_id")
    def _compute_preview(self):
        for printer in self:
            if printer.label_width <= 0 or printer.label_height <= 0:
                printer.preview_image = False
                printer.preview_info = _("O'lcham 0 dan katta bo'lishi kerak")
                printer.fits = False
                printer.qr_size_mm = 0
                continue

            layout = lr.build_layout(printer._render_config(), printer._sample_data())
            printer.preview_image = lr.to_preview_png(layout, scale=2)
            printer.fits = layout.fits

            qr = [i for i in layout.items if i["kind"] == "qr"]
            qr_mm = (qr[0]["size"] / lr.DOTS_PER_MM) if qr else 0
            printer.qr_size_mm = qr_mm
            if layout.fits:
                free_mm = (layout.height - layout.bottom) / lr.DOTS_PER_MM
                printer.preview_info = _(
                    "QR: %(qr).1f mm  |  bo'sh joy: %(free).1f mm"
                ) % {"qr": qr_mm, "free": free_mm}
            else:
                printer.preview_info = _(
                    "SIG'MAYDI — %(over).1f mm oshib ketdi. QR yoki shriftni kichraytiring."
                ) % {"over": layout.overflow / lr.DOTS_PER_MM}

    @api.depends("label_width", "label_height", "qr_cell", "qr_auto",
                 "show_name", "show_lot", "name_font", "lot_font",
                 "box_show_count", "box_show_date", "box_date_font",
                 "box_date_format", "code_mode", "barcode_type",
                 "barcode_height_mm", "barcode_human", "test_product_id")
    def _compute_box_preview(self):
        """Quti stikeri previewi — lot previewidan alohida.

        Quti stikerida qatorlar ko'proq (kod + soni + sana), shuning uchun
        sig'ishini alohida ko'rsatish kerak.
        """
        for printer in self:
            if printer.label_width <= 0 or printer.label_height <= 0:
                printer.box_preview_image = False
                printer.box_preview_info = _("O'lcham 0 dan katta bo'lishi kerak")
                continue

            sample = printer._sample_data()
            now = fields.Datetime.now()
            if printer.box_date_format == "datetime":
                date_txt = fields.Datetime.context_timestamp(
                    printer, now).strftime("%d.%m.%Y %H:%M")
            else:
                date_txt = fields.Date.context_today(printer).strftime("%d.%m.%Y")

            config = dict(
                printer._render_config(),
                show_date=printer.box_show_date,
                date_font=printer.box_date_font,
                show_weight=False,
                show_expiry=False,
            )
            data = {
                "product_name": sample["product_name"],
                "lot_name": "BOX-00012-000045",
                "barcode": "BOX-00012-000045",
                "date": date_txt if printer.box_show_date else "",
                "extra": _("%d dona") % 30 if printer.box_show_count else "",
                "extra_font": printer.lot_font,
            }
            layout = lr.build_layout(config, data)
            printer.box_preview_image = lr.to_preview_png(layout, scale=2)
            if layout.fits:
                free_mm = (layout.height - layout.bottom) / lr.DOTS_PER_MM
                printer.box_preview_info = _(
                    "Quti stikeri: bo'sh joy %(free).1f mm"
                ) % {"free": free_mm}
            else:
                printer.box_preview_info = _(
                    "QUTI STIKERI SIG'MAYDI — %(over).1f mm oshdi. "
                    "Sana yoki sonini o'chiring, yoki shriftni kichraytiring."
                ) % {"over": layout.overflow / lr.DOTS_PER_MM}

    # ------------------------------------------------------------------
    # Chop etish
    # ------------------------------------------------------------------
    def build_payload(self, lot, copies=1):
        """Lot uchun printer tiliga mos buyruqlar matni."""
        self.ensure_one()
        config = self._render_config()
        layout = lr.build_layout(config, self._lot_data(lot))
        if self.language == "zpl":
            return lr.to_zpl(layout, config, copies=copies)
        return lr.to_tspl(layout, config, copies=copies)

    def _box_date_text(self, box):
        """Quti stikeridagi sana matni (printer sozlamasiga ko'ra)."""
        self.ensure_one()
        if box.date:
            return box.date.strftime("%d.%m.%Y")
        src = box.create_date or fields.Datetime.now()
        if self.box_date_format == "datetime":
            local = fields.Datetime.context_timestamp(self, src)
            return local.strftime("%d.%m.%Y %H:%M")
        return fields.Date.context_today(self, src).strftime("%d.%m.%Y")

    def _build_box_payload(self, box, copies=1):
        """Quti stikeri uchun buyruqlar matni.

        Lot stikeri bilan bir xil renderer — quti kodi `lot_name` o'rniga
        beriladi (QR shuni kodlaydi). Past blokda ichidagi soni ("30 dona")
        va quti yaratilgan sana chiqadi; ikkalasi ham printer sozlamasida
        alohida yoqib/o'chiriladi.
        """
        self.ensure_one()
        config = self._render_config()
        # Quti stikerida lot sanasi emas, quti sanasi kerak — shuning uchun
        # lot uchun mo'ljallangan `show_date` o'rniga box sozlamalari ishlaydi.
        config = dict(
            config,
            show_date=self.box_show_date,
            date_font=self.box_date_font,
            # Og'irlik va muddat bitta seriyaga tegishli — qutida ma'nosi yo'q.
            show_weight=False,
            show_expiry=False,
        )
        data = {
            "product_name": box.product_id.display_name or "",
            "lot_name": box.name or "",
            # Chiziqli kod ham quti kodini beradi — QR bilan bir xil natija,
            # ya'ni oddiy lazerli skaner ham qutini topa oladi.
            "barcode": box.name or "",
            "date": self._box_date_text(box) if self.box_show_date else "",
            "extra": _("%d dona") % box.lot_count if self.box_show_count else "",
            "extra_font": self.lot_font,
        }
        layout = lr.build_layout(config, data)
        if self.language == "zpl":
            return lr.to_zpl(layout, config, copies=copies)
        return lr.to_tspl(layout, config, copies=copies)

    def print_lots(self, lots, copies=1):
        """Lotlarni chop etishga yuboradi. Har lot uchun bitta job."""
        self.ensure_one()
        if not lots:
            raise UserError(_("Chop etish uchun lot tanlanmagan."))

        Job = self.env["agronova.label.print.job"]
        jobs = Job.browse()
        for lot in lots:
            jobs |= Job.create({
                "printer_id": self.id,
                "lot_id": lot.id,
                "copies": copies,
                "payload": self.build_payload(lot, copies=copies),
            })

        if self.delivery == "local":
            jobs._run_local()
        return jobs

    def action_test_print(self):
        """Namuna stikerni chop etadi — sozlamani tekshirish uchun."""
        self.ensure_one()
        config = self._render_config()
        layout = lr.build_layout(config, self._sample_data())
        if not layout.fits:
            raise UserError(_(
                "Stiker sig'maydi (%.1f mm oshib ketdi). Avval sozlamani tuzating."
            ) % (layout.overflow / lr.DOTS_PER_MM))

        payload = (lr.to_zpl if self.language == "zpl" else lr.to_tspl)(layout, config)
        note = _("Sinov chop etish")
        if self.test_product_id:
            note = _("Sinov: %s") % self.test_product_id.display_name
        job = self.env["agronova.label.print.job"].create({
            "printer_id": self.id,
            "copies": 1,
            "payload": payload,
            "note": note,
        })
        if self.delivery == "local":
            job._run_local()
            message = _("Sinov stikeri chop etildi.")
        else:
            message = _("Sinov stikeri navbatga qo'yildi — agent uni chop etadi.")
        if self.test_product_id:
            message = "%s (%s)" % (message, self.test_product_id.display_name)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"message": message, "type": "success", "sticky": False},
        }

    def action_reset_token(self):
        """Agent kalitini qayta yaratadi (eskisi ishlamay qoladi)."""
        import secrets
        for printer in self:
            printer.agent_token = secrets.token_urlsafe(24)
        return True

    @api.constrains("qr_cell")
    def _check_qr_cell(self):
        for printer in self:
            if not printer.qr_auto and not (2 <= printer.qr_cell <= 12):
                raise ValidationError(_(
                    "QR o'lchami 2 dan 12 gacha bo'lishi kerak (hozir: %s)."
                ) % printer.qr_cell)

    @api.constrains("label_width", "label_height")
    def _check_label_size(self):
        for printer in self:
            if printer.label_width <= 0 or printer.label_height <= 0:
                raise ValidationError(_("Stiker o'lchami 0 dan katta bo'lishi kerak."))

    @api.model_create_multi
    def create(self, vals_list):
        import secrets
        for vals in vals_list:
            if not vals.get("agent_token"):
                vals["agent_token"] = secrets.token_urlsafe(24)
        return super().create(vals_list)
