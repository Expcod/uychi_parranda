"""Quti (karobka) — bir nechta serialni bitta QR ostida jamlaydi.

Nima uchun kerak: omborchi 30 ta mahsulotni bittalab skanerlash o'rniga
qutining bitta QR kodini skanerlaydi va tizim ichidagi 30 ta serialni biladi.

Oqim:
  sexda tugatish → serial skanerlanadi → quti to'ladi → quti QR chop etiladi
  omborda transfer → quti QR skanerlanadi → 30 ta serial biriktiriladi
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Quti kodi prefiksi — skanerlanganda oddiy serialdan darhol ajratish uchun.
BOX_PREFIX = "BOX-"


class StockLotBox(models.Model):
    _name = "agronova.lot.box"
    _description = "Mahsulot qutisi (jamlangan QR)"
    _order = "id desc"

    name = fields.Char(
        "Quti kodi", required=True, copy=False, index=True,
        help="Quti QR kodida shu matn saqlanadi (BOX- bilan boshlanadi).",
    )
    product_id = fields.Many2one(
        "product.product", "Mahsulot", required=True, ondelete="cascade", index=True,
    )
    lot_ids = fields.Many2many(
        "stock.lot", "stock_lot_box_lot_rel", "box_id", "lot_id",
        string="Ichidagi serial raqamlar",
    )
    lot_count = fields.Integer("Soni", compute="_compute_lot_count", store=True)
    capacity = fields.Integer(
        "Sig'imi", help="Qutiga rejalashtirilgan mahsulot soni.",
    )
    date = fields.Date(
        "Sana", default=fields.Date.context_today, index=True,
        help="Quti yaratilgan sana (stikerda shu sana chiqadi).",
    )
    company_id = fields.Many2one(
        "res.company", "Kompaniya", default=lambda s: s.env.company,
    )
    printed = fields.Boolean("Chop etilgan", default=False)
    note = fields.Char("Izoh")

    # Odoo 19: `_sql_constraints` jimgina e'tiborsiz qoldiriladi — models.Constraint.
    _name_uniq = models.Constraint("unique(name)", "Quti kodi takrorlanmasligi kerak.")

    @api.depends("lot_ids")
    def _compute_lot_count(self):
        for box in self:
            box.lot_count = len(box.lot_ids)

    @api.constrains("lot_ids", "capacity")
    def _check_capacity(self):
        for box in self:
            if box.capacity > 0 and len(box.lot_ids) > box.capacity:
                raise UserError(_(
                    "Quti sig'imidan ortiq mahsulot solib bo'lmaydi! "
                    "Quti sig'imi: %(cap)s, solingan: %(cnt)s.",
                    cap=box.capacity,
                    cnt=len(box.lot_ids),
                ))

    # ------------------------------------------------------------------
    # Yaratish
    # ------------------------------------------------------------------
    @api.model
    def create_for_lots(self, lots, capacity=0, note=None, date=None):
        """Berilgan lotlar uchun quti yaratadi va takrorlanmas kod beradi.

        Kod `stock.lot` bilan bir xil murakkab generatordan olinadi — shunda
        quti kodi ham taxmin qilinmaydi va chalkash belgilar bo'lmaydi.
        """
        lots = lots.exists()
        if not lots:
            raise UserError(_("Quti uchun serial raqam yo'q."))

        # Qat'iy sig'im nazorati: sig'imdan ortiq lot berilsa faqat sig'imgachasi olinadi
        if capacity and len(lots) > capacity:
            lots = lots[:capacity]

        products = lots.mapped("product_id")
        if len(products) > 1:
            raise UserError(_("Bitta qutida faqat bitta mahsulot turi bo'lishi mumkin."))

        Lot = self.env["stock.lot"].sudo()
        # Takrorlanmas kod: BOX- + murakkab kod. Bandligini o'zimiz tekshiramiz,
        # chunki generator faqat stock.lot bo'ylab qaraydi.
        code = None
        for _attempt in range(50):
            candidate = BOX_PREFIX + Lot.generate_complex_serials(1)[0]
            if not self.sudo().search_count([("name", "=", candidate)], limit=1):
                code = candidate
                break
        if not code:
            raise UserError(_("Quti kodi yaratib bo'lmadi. Administratorga murojaat qiling."))

        return self.sudo().create({
            "name": code,
            "product_id": products.id,
            "lot_ids": [(6, 0, lots.ids)],
            "capacity": capacity or len(lots),
            "date": date or fields.Date.context_today(self),
            "note": note or False,
        })

    # ------------------------------------------------------------------
    # Skanerlash yordamchisi
    # ------------------------------------------------------------------
    @api.model
    def resolve_scan(self, code):
        """Skanerlangan kodni quti sifatida topadi (yo'q bo'lsa bo'sh recordset).

        Transfer sahifasi va sex wizardi shu orqali "bu quti kodimi?" deb
        tekshiradi.
        """
        code = (code or "").strip()
        if not code or not code.startswith(BOX_PREFIX):
            return self.browse()
        return self.sudo().search([("name", "=", code)], limit=1)

    # ------------------------------------------------------------------
    # Chop etish — agronova_barcode navbatini qayta ishlatadi
    # ------------------------------------------------------------------
    def action_print_box_label(self):
        """Quti stikerini chop etish (bir nechta printer bo'lsa tanlash oynasi ochiladi)."""
        boxes = self.exists()
        if not boxes:
            raise UserError(_("Quti topilmadi."))

        printers = self.env["agronova.label.printer"].search([])
        if not printers:
            raise UserError(_(
                "Stiker printeri sozlanmagan.\n\n"
                "Stiker printerlari bo'limida printer qo'shing."
            ))

        if len(printers) > 1:
            return {
                "type": "ir.actions.act_window",
                "name": _("Quti stikerini chop etish"),
                "res_model": "agronova.label.print.wizard",
                "view_mode": "form",
                "target": "new",
                "context": {"default_box_ids": boxes.ids},
            }

        jobs = self.env["agronova.label.print.job"].browse()
        for box in boxes:
            jobs |= box.print_box_label(printer=printers[0])
        return self.env["stock.lot"]._label_print_notification(jobs, printers[0])

    def print_box_label(self, printer=None):
        """Quti stikerini printerga yuboradi.

        Stikerda quti kodi QR sifatida chiqadi. Lot stikeri bilan bir xil
        renderer ishlatiladi — quti "virtual lot" sifatida beriladi.
        """
        self.ensure_one()
        printer = printer or self.env["agronova.label.printer"].sudo().search([], limit=1)
        if not printer:
            raise UserError(_(
                "Stiker printeri sozlanmagan.\n\n"
                "Stiker printerlari bo'limida printer qo'shing."
            ))

        payload = printer._build_box_payload(self)
        job = self.env["agronova.label.print.job"].sudo().create({
            "printer_id": printer.id,
            "copies": 1,
            "payload": payload,
            "note": _("Quti: %s") % self.name,
        })
        if printer.delivery == "local":
            job._run_local()
        if job.state != "failed":
            self.printed = True
        return job
