"""Stiker layoutini hisoblash, TSPL/ZPL generatsiya va preview rasm chizish.

Bitta manbadan ikki natija chiqadi — printerga ketadigan buyruqlar va
ekranda ko'rinadigan rasm. Ikkisi bir xil `_layout()` dan foydalanadi,
shuning uchun preview printerdan chiqadigan bilan mos keladi.

Koordinatalar nuqtada (dot). 203 DPI da 1 mm = 8 nuqta.
"""
import base64
import io
import logging

_logger = logging.getLogger(__name__)

DPI = 203
DOTS_PER_MM = DPI / 25.4

# TSPL bitmap shriftlari: raqam -> (belgi kengligi, balandligi) nuqtada.
# Printer hujjatidagi qiymatlar; preview shu nisbatlarni takrorlaydi.
TSPL_FONTS = {
    "1": (8, 12),
    "2": (12, 20),
    "3": (16, 24),
    "4": (24, 32),
    "5": (32, 48),
}


class LabelLayout:
    """Bitta stikerning joylashuvi — elementlar ro'yxati va sig'ish holati."""

    def __init__(self, width_mm, height_mm):
        self.width = int(round(width_mm * DOTS_PER_MM))
        self.height = int(round(height_mm * DOTS_PER_MM))
        self.width_mm = width_mm
        self.height_mm = height_mm
        self.items = []          # [{kind, x, y, ...}]
        self.bottom = 0          # eng pastki ishlatilgan nuqta

    # --- qo'shish ---
    def add_text(self, text, y, font="2", align="center", x=None):
        if not text:
            return
        fw, fh = TSPL_FONTS.get(font, TSPL_FONTS["2"])
        width = text_width(text, font)
        if x is None:
            x = self._align_x(width, align)
        self.items.append({
            "kind": "text", "text": text, "x": x, "y": y,
            "font": font, "font_w": fw, "font_h": fh, "width": width,
        })
        self.bottom = max(self.bottom, y + fh)

    def add_qr(self, data, y, cell, align="center", x=None):
        if not data:
            return
        size = self._qr_size(data, cell)
        if x is None:
            x = self._align_x(size, align)
        self.items.append({
            "kind": "qr", "data": data, "x": x, "y": y,
            "cell": cell, "size": size,
        })
        self.bottom = max(self.bottom, y + size)

    def add_barcode(self, data, y, symbology, height, narrow,
                    human=True, align="center", x=None):
        """Chiziqli kod (Code128 / EAN-13) qo'shadi.

        Kengligi ma'lumot uzunligiga bog'liq: modul soni x eng ingichka
        chiziq kengligi. `human` yoqilgan bo'lsa kod ostida raqamlar
        chiziladi — shuning uchun balandlikka qo'shimcha qator qo'shiladi.
        """
        if not data:
            return
        width = barcode_modules(data, symbology) * narrow
        if x is None:
            x = self._align_x(width, align)
        total_h = height + (HUMAN_TEXT_H if human else 0)
        self.items.append({
            "kind": "barcode", "data": data, "x": x, "y": y,
            "symbology": symbology, "height": height, "narrow": narrow,
            "human": human, "width": width, "size": total_h,
        })
        self.bottom = max(self.bottom, y + total_h)

    # --- yordamchi ---
    def _align_x(self, item_width, align):
        if align == "left":
            return 4
        if align == "right":
            return max(0, self.width - item_width - 4)
        return max(0, (self.width - item_width) // 2)

    @staticmethod
    def _qr_size(data, cell):
        """QR ning nuqtadagi o'lchami = modul soni x cell.

        Modul sonini `qrcode` kutubxonasidan aniq olamiz — shunda preview
        printerdan chiqadigan bilan mos keladi. Kutubxona bo'lmasa
        ma'lumot uzunligi bo'yicha taxmin qilinadi (TSPL bir xil qoida
        bilan versiya tanlaydi).
        """
        try:
            import qrcode
            qr = qrcode.QRCode(
                error_correction=qrcode.constants.ERROR_CORRECT_L, border=0)
            qr.add_data(data or "")
            qr.make(fit=True)
            modules = qr.modules_count
        except Exception:
            n = len(data or "")
            if n <= 25:
                modules = 21      # versiya 1
            elif n <= 47:
                modules = 25      # versiya 2
            elif n <= 77:
                modules = 29      # versiya 3
            elif n <= 114:
                modules = 33      # versiya 4
            else:
                modules = 37      # versiya 5
        return modules * cell

    @property
    def fits(self):
        return self.bottom <= self.height

    @property
    def overflow(self):
        """Nechta nuqta stikerdan chiqib ketgan (0 bo'lsa sig'adi)."""
        return max(0, self.bottom - self.height)


# Bloklar orasidagi eng kam bo'shliq (nuqta). QR matnga yopishmasligi uchun.
MIN_BLOCK_GAP = 8

# Chiziqli kod ostidagi inson o'qiy oladigan raqamlar balandligi (nuqta).
HUMAN_TEXT_H = 14


def barcode_modules(data, symbology):
    """Chiziqli kodning modul soni — kengligini hisoblash uchun.

    Modul — eng ingichka chiziq. Kod kengligi = modul soni x `narrow`.
    EAN-13 doim 95 modul (+ chetlardagi tinch zona), Code128 esa har
    belgiga 11 modul: start + ma'lumot + tekshiruv + stop(13).
    """
    if symbology == "EAN13":
        return 95 + 18
    return 11 * (len(data or "") + 2) + 13 + 20


def normalize_barcode(data, symbology):
    """Ma'lumot EAN-13 ga mos kelmasa jimgina Code128 ga o'tadi.

    EAN-13 faqat 12 yoki 13 xonali raqamni qabul qiladi. Lot nomi yoki
    mahsulot kodi bunga mos kelmasa printer stikerni umuman chop etmasdi —
    xato o'rniga Code128 chiqargan foydaliroq (u har qanday matnni oladi).
    """
    data = (data or "").strip()
    if not data:
        return "", symbology
    if symbology == "EAN13" and not (data.isdigit() and len(data) in (12, 13)):
        return data, "128"
    return data, symbology


def best_narrow(width_dots, data, symbology, lo=1, hi=4):
    """Stiker kengligiga sig'adigan eng katta modul kengligi."""
    modules = barcode_modules(data, symbology)
    for narrow in range(hi, lo - 1, -1):
        if modules * narrow <= width_dots:
            return narrow
    return lo


# Kirill harflar printerda lotinnikidan kengroq chiziladi. Qatorga nechta
# belgi sig'ishini hisoblashda shu koeffitsientni qo'llaymiz.
CYRILLIC_WIDTH_FACTOR = 1.25


def text_width(text, font):
    """Matnning nuqtadagi kengligi.

    Kirill harflar kengroq chiziladi — har belgini alohida hisoblaymiz,
    aks holda aralash matn (kirill + lotin) noto'g'ri markazlanadi.
    """
    fw = TSPL_FONTS.get(font, TSPL_FONTS["2"])[0]
    total = 0.0
    for ch in (text or ""):
        total += fw * (CYRILLIC_WIDTH_FACTOR if _is_cyrillic(ch) else 1.0)
    return int(round(total))


def _is_cyrillic(ch):
    return "Ѐ" <= ch <= "ӿ"


def build_layout(config, data):
    """Sozlama va ma'lumotdan layout quradi.

    Stiker uch blokka bo'linadi — tepada mahsulot nomi, markazda QR,
    pastda lot va sana. QR vertikal markazda turadi va bloklar orasida
    doim bo'shliq qoladi, stiker o'lchami qanday bo'lishidan qat'i nazar.

    `qr_cell` 0 (yoki `qr_auto` yoqilgan) bo'lsa — QR stikerga sig'adigan
    eng katta o'lchamda avtomatik tanlanadi.

    :param config: dict — label_width, label_height, qr_cell, show_name,
                   show_lot, show_date, name_font, lot_font, date_font
    :param data: dict — product_name, lot_name, date
    """
    if config.get("qr_auto") or not config.get("qr_cell"):
        config = dict(config, qr_cell=_best_qr_cell(config, data))

    lay = LabelLayout(config["label_width"], config["label_height"])

    # --- bloklarni oldindan hisoblaymiz (hali chizmaymiz) ---
    top = _name_lines(config, data, lay.width)          # [(matn, font, balandlik)]
    bottom = _footer_lines(config, data)                 # [(matn, font, balandlik)]
    qr_cell = config.get("qr_cell", 6)
    code_mode = config.get("code_mode", "qr")
    qr_data = (data.get("lot_name") or "") if code_mode in ("qr", "both") else ""
    qr_size = LabelLayout._qr_size(qr_data, qr_cell) if qr_data else 0

    # --- chiziqli kod (QR bilan birga yoki uning o'rniga) ---
    bc_data, bc_type, bc_h, bc_narrow, bc_total = "", "128", 0, 1, 0
    bc_human = bool(config.get("barcode_human", True))
    if code_mode in ("barcode", "both"):
        bc_data, bc_type = normalize_barcode(
            data.get("barcode") or data.get("lot_name") or "",
            config.get("barcode_type", "128"),
        )
    if bc_data:
        bc_h = int(round(float(config.get("barcode_height_mm") or 8) * DOTS_PER_MM))
        bc_narrow = best_narrow(lay.width - 8, bc_data, bc_type)
        bc_total = bc_h + (HUMAN_TEXT_H if bc_human else 0)

    # O'rta blok: QR + chiziqli kod (ikkalasi ham bo'lsa orasida bo'shliq)
    mid_h = qr_size + bc_total + (MIN_BLOCK_GAP if (qr_size and bc_total) else 0)

    top_h = sum(h for _, _, h in top) + max(0, len(top) - 1)
    bottom_h = sum(h for _, _, h in bottom) + max(0, len(bottom) - 1)

    # --- bo'sh joyni bloklar orasiga taqsimlaymiz ---
    gaps = (1 if top_h else 0) + (1 if bottom_h else 0)
    free = lay.height - (top_h + mid_h + bottom_h)
    if gaps:
        gap = max(MIN_BLOCK_GAP, free // (gaps + 1)) if free > 0 else MIN_BLOCK_GAP
    else:
        gap = 0

    # QR markazda tursin: qolgan joyni tepa/past orasida teng bo'lamiz
    used = top_h + bottom_h + mid_h + gap * gaps
    y = max(0, (lay.height - used) // 2)

    # --- chizamiz ---
    for text, font, height in top:
        lay.add_text(text, y, font=font)
        y += height + 1
    if top_h:
        y += gap - 1

    if qr_data:
        lay.add_qr(qr_data, y, qr_cell)
        y = lay.bottom
        if bc_data:
            y += MIN_BLOCK_GAP

    if bc_data:
        lay.add_barcode(bc_data, y, bc_type, bc_h, bc_narrow, human=bc_human)
        y = lay.bottom

    if (qr_data or bc_data) and bottom_h:
        y += gap

    for text, font, height in bottom:
        lay.add_text(text, y, font=font)
        y += height + 1

    return lay


def _name_lines(config, data, width):
    """Tepa blok — mahsulot nomi qatorlari."""
    if not (config.get("show_name") and data.get("product_name")):
        return []
    font = config.get("name_font", "1")
    fh = TSPL_FONTS.get(font, TSPL_FONTS["1"])[1]
    max_chars = _max_chars(data["product_name"], font, width)
    max_lines = max(1, int(config.get("name_lines", 2)))
    return [(line, font, fh)
            for line in _wrap(data["product_name"], max_chars, max_lines)]


def _max_chars(text, font, width):
    """Qatorga sig'adigan belgi soni.

    Matnda kirill bo'lsa harflar kengroq — sig'adigan belgi soni kamayadi,
    aks holda nom stiker chetidan chiqib ketadi.
    """
    fw = TSPL_FONTS.get(font, TSPL_FONTS["1"])[0]
    if _has_cyrillic(text):
        fw = fw * CYRILLIC_WIDTH_FACTOR
    return max(1, int(width // fw))


def _has_cyrillic(text):
    return any(_is_cyrillic(ch) for ch in (text or ""))


def _footer_lines(config, data):
    """Past blok — lot raqami, quti soni, og'irlik, sana va yaroqlilik muddati.

    `extra` — quti stikeri uchun ("30 dona"). Lot stikerida bo'lmaydi,
    shuning uchun mavjud bo'lgandagina qo'shiladi.
    """
    lines = []
    if config.get("show_lot") and data.get("lot_name"):
        font = config.get("lot_font", "2")
        lines.append((data["lot_name"], font, TSPL_FONTS.get(font, TSPL_FONTS["2"])[1]))
    if data.get("extra"):
        font = data.get("extra_font") or config.get("lot_font", "2")
        lines.append((data["extra"], font, TSPL_FONTS.get(font, TSPL_FONTS["2"])[1]))
    if config.get("show_weight") and data.get("weight"):
        font = config.get("weight_font", "2")
        lines.append((data["weight"], font, TSPL_FONTS.get(font, TSPL_FONTS["2"])[1]))
    if config.get("show_date") and data.get("date"):
        font = config.get("date_font", "1")
        lines.append((data["date"], font, TSPL_FONTS.get(font, TSPL_FONTS["1"])[1]))
    if config.get("show_expiry") and data.get("expiry"):
        font = config.get("expiry_font", "1")
        lines.append((data["expiry"], font, TSPL_FONTS.get(font, TSPL_FONTS["1"])[1]))
    return lines


def _wrap(text, max_chars, max_lines):
    """Matnni so'zlar bo'yicha qatorlarga bo'ladi.

    Oxirgi qator sig'masa "..." bilan qisqartiriladi — nom yarim
    kesilganidan ko'ra qisqarganini ko'rsatgan tushunarliroq.
    """
    text = (text or "").strip()
    if not text:
        return []

    lines, current = [], ""
    for word in text.split():
        candidate = (current + " " + word).strip()
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            lines.append(current)
        # Bitta so'z qatorga sig'masa - bo'lib tashlaymiz
        while len(word) > max_chars:
            lines.append(word[:max_chars])
            word = word[max_chars:]
        current = word
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)

    lines = lines[:max_lines]
    # Sig'magan matn qolgan bo'lsa oxirgi qatorni ".." bilan tugatamiz.
    # Uch nuqta o'rniga ikkita ASCII nuqta — "…" belgisi CP1251 da yo'q.
    if len("".join(lines).replace(" ", "")) < len(text.replace(" ", "")) and lines:
        last = lines[-1]
        if len(last) > max_chars - 2:
            last = last[:max_chars - 2]
        lines[-1] = last + ".."
    return lines


def _best_qr_cell(config, data, lo=2, hi=12):
    """Stikerga sig'adigan eng katta QR cell qiymatini topadi.

    Kattadan kichikka qarab sinaydi — birinchi sig'gani eng kattasi.
    """
    probe = dict(config)
    probe["qr_auto"] = False
    for cell in range(hi, lo - 1, -1):
        probe["qr_cell"] = cell
        if build_layout(probe, data).fits:
            return cell
    return lo


def encode_payload(text, encoding):
    """Printerga yuboriladigan baytlar.

    Kirill matn uchun CP1251 kerak — printerning ichki shrifti UTF-8 ni
    tushunmaydi va `Ç ï ê` kabi belgilar chiqadi. Kodlanmagan belgilar
    stikerni buzmasligi uchun '?' bilan almashtiriladi.
    """
    if isinstance(text, bytes):
        return text
    try:
        return text.encode(encoding, errors="replace")
    except LookupError:
        _logger.warning("Noma'lum kodlash '%s' — UTF-8 ishlatildi", encoding)
        return text.encode("utf-8", errors="replace")


def to_tspl(layout, config, copies=1):
    """Layoutdan TSPL buyruqlari (Xprinter/TSC printerlar tili)."""
    gap = config.get("gap_mm", 2)
    lines = [
        "SIZE %s mm,%s mm" % (_fmt(layout.width_mm), _fmt(layout.height_mm)),
        "GAP %s mm,0" % _fmt(gap),
        "DIRECTION %d" % (1 if config.get("direction", True) else 0),
        "DENSITY %d" % config.get("density", 8),
        "SPEED %d" % config.get("speed", 4),
        # Kirill/lotin harflari to'g'ri chiqishi uchun kod sahifasi.
        # 1251 - kirill, 1252 - g'arbiy Yevropa, 1254 - turk.
        "CODEPAGE %s" % config.get("codepage", "1251"),
        "CLS",
    ]
    for it in layout.items:
        if it["kind"] == "text":
            # TEXT — printer kirill harflarni shu buyruq bilan to'g'ri chizadi.
            # BLOCK markazlashni o'zi qilardi, lekin kirill gliflarni ustma-ust
            # bosib yuboradi, shuning uchun x ni o'zimiz hisoblaymiz.
            lines.append('TEXT %d,%d,"%s",0,1,1,"%s"'
                         % (it["x"], it["y"], it["font"], _escape_tspl(it["text"])))
        elif it["kind"] == "qr":
            lines.append('QRCODE %d,%d,L,%d,A,0,"%s"'
                         % (it["x"], it["y"], it["cell"], _escape_tspl(it["data"])))
        elif it["kind"] == "barcode":
            # BARCODE X,Y,"turi",balandlik,matn(0/2),burilish,ingichka,keng,"kod"
            lines.append('BARCODE %d,%d,"%s",%d,%d,0,%d,%d,"%s"'
                         % (it["x"], it["y"], it["symbology"], it["height"],
                            2 if it["human"] else 0, it["narrow"],
                            max(2, it["narrow"] * 2), _escape_tspl(it["data"])))
    lines.append("PRINT %d,1" % max(1, copies))
    return "\n".join(lines) + "\n"


def to_zpl(layout, config, copies=1):
    """Layoutdan ZPL buyruqlari (Zebra printerlar uchun zaxira variant)."""
    lines = ["^XA", "^CI28",
             "^PW%d" % layout.width, "^LL%d" % layout.height]
    for it in layout.items:
        if it["kind"] == "text":
            lines.append("^FO%d,%d^A0N,%d,%d^FD%s^FS"
                         % (it["x"], it["y"], it["font_h"], it["font_w"],
                            _escape_zpl(it["text"])))
        elif it["kind"] == "qr":
            magnification = max(1, min(10, it["cell"]))
            lines.append("^FO%d,%d^BQN,2,%d^FDQA,%s^FS"
                         % (it["x"], it["y"], magnification, _escape_zpl(it["data"])))
        elif it["kind"] == "barcode":
            human = "Y" if it["human"] else "N"
            code = ("^BEN,%d,%s,N" if it["symbology"] == "EAN13"
                    else "^BCN,%d,%s,N,N") % (it["height"], human)
            lines.append("^FO%d,%d^BY%d,2,%d%s^FD%s^FS"
                         % (it["x"], it["y"], it["narrow"], it["height"],
                            code, _escape_zpl(it["data"])))
    lines.append("^PQ%d" % max(1, copies))
    lines.append("^XZ")
    return "\n".join(lines) + "\n"


def to_preview_png(layout, scale=3):
    """Layoutni PNG rasmga chizadi (Odoo formasida ko'rsatish uchun).

    Pillow yo'q bo'lsa None qaytaradi — preview ixtiyoriy, chop etishga ta'sir qilmaydi.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        _logger.warning("Pillow o'rnatilmagan — stiker preview ko'rsatilmaydi")
        return None

    try:
        import qrcode
    except ImportError:
        _logger.warning("qrcode o'rnatilmagan — stiker preview ko'rsatilmaydi")
        return None

    W, H = layout.width * scale, layout.height * scale
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)
    # Stiker chegarasi — faqat previewda, chop etilmaydi
    draw.rectangle([0, 0, W - 1, H - 1], outline="#d0d0d0")

    for it in layout.items:
        if it["kind"] == "text":
            font = _pil_font(it["font_h"] * scale)
            # Printer BLOCK bilan o'zi markazlaydi — preview ham shunday
            # qilsin, aks holda ikkisi mos kelmaydi.
            text_w = draw.textlength(it["text"], font=font)
            x = max(0, (W - text_w) / 2)
            draw.text((x, it["y"] * scale), it["text"], font=font, fill="black")
        elif it["kind"] == "qr":
            qr = qrcode.QRCode(
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=it["cell"] * scale,
                border=0,
            )
            qr.add_data(it["data"])
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
            img.paste(qr_img, (it["x"] * scale, it["y"] * scale))
        elif it["kind"] == "barcode":
            bc_img = _barcode_png(it["data"], it["symbology"],
                                  it["width"] * scale, it["height"] * scale,
                                  it["human"])
            if bc_img:
                img.paste(bc_img, (it["x"] * scale, it["y"] * scale))

    # Sig'magan qismni qizil chiziq bilan belgilash
    if not layout.fits:
        y = layout.height * scale - 1
        draw.line([(0, y), (W, y)], fill="#d9534f", width=2 * scale)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue())


# --- ichki yordamchilar ---
def _barcode_png(data, symbology, width, height, human):
    """Chiziqli kod rasmini reportlab orqali chizadi (Odoo bilan birga keladi).

    Faqat previewga kerak — printerga buyruq matni ketadi, rasm emas.
    """
    try:
        from reportlab.graphics.barcode import createBarcodeDrawing
        from PIL import Image
    except ImportError:
        return None
    kind = "EAN13" if symbology == "EAN13" else "Code128"
    try:
        drawing = createBarcodeDrawing(
            kind, value=str(data), format="png",
            width=max(1, int(width)), height=max(1, int(height)),
            humanReadable=bool(human))
        return Image.open(io.BytesIO(drawing.asString("png"))).convert("RGB")
    except Exception:
        _logger.warning("Chiziqli kod previewi chizilmadi: %s", data)
        return None


def _pil_font(px):
    from PIL import ImageFont
    for path in ("C:/Windows/Fonts/consola.ttf", "C:/Windows/Fonts/cour.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"):
        try:
            return ImageFont.truetype(path, int(px))
        except OSError:
            continue
    return ImageFont.load_default()


def _fmt(value):
    """40.0 -> '40', 40.5 -> '40.5' (TSPL kasrsiz sonlarni afzal ko'radi)."""
    f = float(value)
    return str(int(f)) if f == int(f) else ("%.1f" % f)


def _escape_tspl(text):
    return (text or "").replace("\\", "\\\\").replace('"', '\\"')


def _escape_zpl(text):
    return (text or "").replace("^", " ").replace("~", " ")
