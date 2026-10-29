"""Transfer skanerlash oynasi.

Oddiy forma: bitta input maydoni. Skaner klaviatura emulyatsiyasi qiladi va
oxirida Enter yuboradi — Odoo `onchange` shu paytda ishga tushadi va kod
qayta ishlanadi. Oyna ochiq turadi, omborchi ketma-ket skanerlayveradi.

Uch tab:
  * Mahsulotlar — har mahsulot bo'yicha "3 / 10" holati (asosiy ish ko'rinishi)
  * Seriyalar — qaysi seriyalar tushgani
  * Qutilar — quti QR skanerlangan bo'lsa, qaysi qutilar va nechtadan
"""
from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError


class StockPickingQrScan(models.TransientModel):
    _name = "agronova.picking.qr.scan"
    _description = "Transferda QR skanerlash"

    picking_id = fields.Many2one(
        "stock.picking", "Transfer", required=True, ondelete="cascade",
    )
    scan_code = fields.Char(
        "Skanerlash",
        help="Skaner bilan QR kodni o'qing. Quti QR kodi ichidagi barcha "
             "mahsulotlarni bir vaqtda qo'shadi.",
    )
    last_status = fields.Selection(
        [
            ("ok", "Qo'shildi"),
            ("duplicate", "Takror"),
            ("unknown", "Topilmadi"),
            ("wrong", "Mos emas"),
            ("excess", "Ortiqcha"),
            ("fifo_block", "FIFO buzilish"),
        ],
        string="Oxirgi natija", readonly=True,
    )
    last_message = fields.Char("Xabar", readonly=True)
    # Har skanda ortadi. Compute maydonlar shunga bog'langan: `last_message`
    # ning o'ziga tayanib bo'lmaydi — ketma-ket bir xil xabar kelsa (masalan
    # ikki marta "Topilmadi") qiymat o'zgarmaydi va tablar yangilanmay qolardi.
    scan_seq = fields.Integer("Skan raqami", readonly=True, default=0)
    progress_info = fields.Char(
        "Holat", compute="_compute_progress",
    )
    scanned_qty = fields.Integer(compute="_compute_progress")
    demand_qty = fields.Integer(compute="_compute_progress")
    is_done = fields.Boolean(compute="_compute_progress")

    # Many2many (One2many emas) — bu modellarda wizardga teskari havola yo'q,
    # ular faqat ko'rsatish uchun to'ldiriladi.
    line_ids = fields.Many2many(
        "stock.move.line", compute="_compute_lines", string="Skanerlangan seriyalar",
    )
    # `store=True` + `readonly=False` — Odoo'ning o'z namunasi
    # (stock/wizard/stock_picking_return.py:103). `store=False` bo'lsa
    # compute ichidagi `(0, 0, ...)` buyruqlari saqlanmay yo'qoladi.
    product_line_ids = fields.One2many(
        "agronova.picking.qr.scan.product", "wizard_id",
        compute="_compute_product_lines", string="Mahsulotlar",
        store=True, readonly=False, precompute=True,
    )
    box_ids = fields.Many2many(
        "agronova.lot.box", compute="_compute_boxes", string="Skanerlangan qutilar",
    )
    box_count = fields.Integer(compute="_compute_boxes")

    @api.depends("picking_id", "scan_seq")
    def _compute_progress(self):
        for wiz in self:
            if not wiz.picking_id:
                wiz.scanned_qty = wiz.demand_qty = 0
                wiz.is_done = False
                wiz.progress_info = ""
                continue
            scanned, demand = wiz.picking_id._qr_scan_progress()
            wiz.scanned_qty = int(scanned)
            wiz.demand_qty = int(demand)
            wiz.is_done = scanned >= demand
            wiz.progress_info = _("%(done)s / %(total)s skanerlangan") % {
                "done": int(scanned), "total": int(demand),
            }

    @api.depends("picking_id", "scan_seq")
    def _compute_lines(self):
        Line = self.env["stock.move.line"]
        for wiz in self:
            if not wiz.picking_id:
                wiz.line_ids = Line
                continue
            moves = wiz.picking_id._serial_moves()
            # Skanerlangan yoki skanerlash talab qilinmaydigan (qr_scan_required=False) qatorlar
            wiz.line_ids = moves.mapped("move_line_ids").filtered(
                lambda ml: ml.lot_id and (ml.qr_scanned or not ml.lot_id.qr_scan_required)) or Line

    @api.depends("picking_id", "scan_seq")
    def _compute_product_lines(self):
        """Har mahsulot bo'yicha "skanerlangan / so'ralgan" holati.

        Asosiy ish ko'rinishi: omborchi qaysi mahsulotdan yana nechta
        kerakligini bir qarashda ko'radi.
        """
        for wiz in self:
            commands = [Command.clear()]
            if wiz.picking_id:
                for move in wiz.picking_id._serial_moves():
                    scanned = sum(
                        ml.quantity for ml in move.move_line_ids
                        if ml.lot_id and (ml.qr_scanned or not ml.lot_id.qr_scan_required)
                    )
                    commands.append(Command.create({
                        "product_id": move.product_id.id,
                        "demand_qty": move.product_uom_qty,
                        "scanned_qty": scanned,
                    }))
            wiz.product_line_ids = commands

    @api.depends("picking_id", "scan_seq")
    def _compute_boxes(self):
        Box = self.env["agronova.lot.box"]
        for wiz in self:
            boxes = Box
            if wiz.picking_id:
                boxes = wiz.picking_id._serial_moves().move_line_ids.filtered(
                    lambda ml: ml.qr_scanned and ml.qr_box_id
                ).mapped("qr_box_id")
            wiz.box_ids = boxes
            wiz.box_count = len(boxes)

    @api.onchange("scan_code")
    def _onchange_scan_code(self):
        """Skaner Enter yuborganda kod qayta ishlanadi va maydon bo'shatiladi."""
        if not self.scan_code or not self.picking_id:
            return
        code = self.scan_code
        # Maydonni darhol bo'shatamiz — keyingi skan uchun tayyor
        self.scan_code = False

        res = self.picking_id.register_scanned_code(code)
        self.last_status = res["status"]
        self.last_message = res["message"]
        # Tablarni yangilashga majbur qiladi — barcha compute shunga bog'langan.
        self.scan_seq += 1

        # Modal FAQAT haqiqiy to'siq uchun. `duplicate` / `excess` — omborchi
        # bir kodni ikki marta o'qigan yoki miqdor to'lgan holat: xabar
        # yuqoridagi alert blokida (`last_message`) allaqachon ko'rinadi.
        # Modal chiqarish skanerlash ritmini buzadi — omborchi har takror
        # skanda oynani qo'lda yopishga majbur bo'lardi.
        if res["status"] in ("fifo_block", "unknown", "wrong"):
            titles = {
                "fifo_block": _("FIFO: avval eski seriallarni chiqaring!"),
                "unknown": _("Kod topilmadi"),
                "wrong": _("Mos kelmadi"),
            }
            return {
                "warning": {
                    "title": titles[res["status"]],
                    "message": res["message"],
                }
            }

    def action_done(self):
        """Oynani yopadi va transferni yangilaydi.

        MUHIM: skanerlash `move_line` larni to'g'ridan-to'g'ri bazaga yozadi,
        lekin orqada turgan transfer formasi hali ESKI `quantity` ni ushlab
        turadi (masalan 0). `stock.move.quantity` — `store=True` va
        `inverse="_set_quantity"` maydon: forma saqlanganda Odoo eski qiymatni
        qaytib yozadi va `_set_quantity` skanerlangan qatorlarni kamaytiradi
        yoki butunlay o'chiradi. Aynan shu sabab "Yopish" bosilganda miqdor
        o'zgarib qolardi.

        Yechim: hisoblangan maydonlarni bazadan qayta o'qishga majbur qilamiz
        va to'liq `reload` qaytaramiz — brauzerdagi eski qiymatlar
        saqlanmasdan tashlab yuboriladi.
        """
        self.ensure_one()
        moves = self.picking_id._serial_moves()
        # Bazadagi haqiqiy holatni majburan qayta hisoblatamiz — keshdagi
        # eskirgan `quantity` bilan yozib yuborilmasligi uchun.
        moves.invalidate_recordset(["quantity", "picked"])
        moves.modified(["move_line_ids"])
        self.picking_id.invalidate_recordset(["qr_scan_done", "qr_scan_info"])
        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }


class StockPickingQrScanProduct(models.TransientModel):
    """Skanerlash oynasidagi "Mahsulotlar" tabining bitta qatori.

    Alohida model kerak, chunki `stock.move` da "skanerlangan soni" maydoni
    yo'q va uni faqat ko'rsatish uchun asosiy modelga qo'shish ortiqcha —
    u har transferda hisoblanib, tizimni sekinlashtirardi.
    """
    _name = "agronova.picking.qr.scan.product"
    _description = "Skanerlash oynasi — mahsulot holati"

    wizard_id = fields.Many2one(
        "agronova.picking.qr.scan", ondelete="cascade", index=True,
    )
    product_id = fields.Many2one("product.product", "Mahsulot", readonly=True)
    demand_qty = fields.Float("So'ralgan", readonly=True)
    scanned_qty = fields.Float("Skanerlangan", readonly=True)
    remaining_qty = fields.Float(
        "Qolgan", compute="_compute_remaining",
        help="Yana nechta skanerlash kerak.",
    )
    is_complete = fields.Boolean(compute="_compute_remaining")

    @api.depends("demand_qty", "scanned_qty")
    def _compute_remaining(self):
        for line in self:
            line.remaining_qty = max(line.demand_qty - line.scanned_qty, 0)
            line.is_complete = line.scanned_qty >= line.demand_qty


class StockPickingQrBypass(models.TransientModel):
    """Menejer skanerlashni chetlab o'tishi — sabab majburiy."""
    _name = "agronova.picking.qr.bypass"
    _description = "QR skanerlashni chetlab o'tish"

    picking_id = fields.Many2one(
        "stock.picking", "Transfer", required=True, ondelete="cascade",
    )
    reason = fields.Text(
        "Sabab", required=True,
        help="Nima uchun skanerlamasdan o'tkazilyapti? Masalan: eski mahsulot, "
             "QR stikeri yirtilgan.",
    )

    def action_confirm(self):
        self.ensure_one()
        if not self.env.user.has_group("stock.group_stock_manager"):
            raise UserError(_("Faqat ombor menejeri chetlab o'ta oladi."))

        picking = self.picking_id
        picking.qr_scan_bypassed = True
        scanned, demand = picking._qr_scan_progress()
        picking.message_post(body=_(
            "<b>QR skanerlash chetlab o'tildi.</b><br/>"
            "Skanerlangan: %(done)s / %(total)s<br/>"
            "Sabab: %(reason)s",
            done=int(scanned), total=int(demand), reason=self.reason,
        ))
        return {"type": "ir.actions.act_window_close"}
