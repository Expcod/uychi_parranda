"""Inventarizatsiyadan qutiga solish — tanlangan seriallarni BOX larga jamlaydi.

Nima uchun kerak: yuzlab serial stikerini birma-bir chop etish o'rniga
omborchi seriallarni qutilarga soladi va har qutiga bitta jamlangan QR
yopishtiradi — transferda quti QR bir marta skanerlanadi, ichidagi barcha
serial biriktiriladi. Wizard stock.quant ro'yxatidagi «QR stikerlarni chop
etish» tugmasidan ochiladi.
"""
import math

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StockLotBoxWizard(models.TransientModel):
    _name = "agronova.lot.box.wizard"
    _description = "Qutiga solish va chop etish"

    lot_ids = fields.Many2many("stock.lot", string="Serial raqamlar", required=True)
    lot_count = fields.Integer("Tanlangan", compute="_compute_counts")
    in_box_count = fields.Integer(
        "Allaqachon qutida", compute="_compute_counts",
        help="Boshqa qutiga solib bo'lingan seriallar — qayta qutilanmaydi.",
    )
    box_count = fields.Integer("Yaratiladigan quti", compute="_compute_counts")
    printer_id = fields.Many2one(
        "agronova.label.printer", "Printer", required=True,
        default=lambda self: self.env["agronova.label.printer"].search([], limit=1),
    )
    date = fields.Date(
        "Quti sanasi", default=fields.Date.context_today, required=True,
        help="Quti stikerida chiqadigan sana.",
    )
    mode = fields.Selection(
        [
            ("box_and_labels", "BOX + alohida stikerlar"),
            ("box_only", "Faqat BOX stikeri"),
            ("labels_only", "Faqat stikerlar"),
        ],
        string="Chop etish rejimi", default="box_and_labels", required=True,
        help="BOX + alohida stikerlar: har serialga stiker ham, qutilarga stiker ham chiqadi.\n"
             "Faqat BOX stikeri: har serialga stiker chiqmaydi, faqat quti stikeri.\n"
             "Faqat stikerlar: quti yaratilmaydi, faqat har serialga alohida stiker chiqadi.",
    )
    capacity = fields.Integer(
        "Quti sig'imi", default=30, required=True,
        help="Har qutiga nechta serial. Ko'proq tanlansa bir nechta qutiga bo'linadi.",
    )

    def _lots_to_box(self):
        """Qutilanmagan seriallar — allaqachon qutida bo'lganlar qayta qutilanmaydi."""
        lots = self.lot_ids.filtered("name")
        boxed = self.env["agronova.lot.box"].sudo().search(
            [("lot_ids", "in", lots.ids)]).mapped("lot_ids")
        return lots - boxed

    @api.depends("lot_ids", "capacity", "mode")
    def _compute_counts(self):
        for wiz in self:
            lots = wiz.lot_ids.filtered("name")
            to_box = wiz._lots_to_box()
            wiz.lot_count = len(lots)
            wiz.in_box_count = len(lots) - len(to_box)
            if wiz.mode == "labels_only" or wiz.capacity < 1 or not to_box:
                wiz.box_count = 0
                continue
            count = 0
            for product in to_box.mapped("product_id"):
                qty = len(to_box.filtered(lambda lot: lot.product_id == product))
                count += math.ceil(qty / wiz.capacity)
            wiz.box_count = count

    def action_confirm(self):
        self.ensure_one()
        lots = self.lot_ids.filtered("name")
        if not lots:
            raise UserError(_("Tanlangan qatorlarda lot/seriya yo'q."))

        # ── Faqat stikerlar rejimi — quti yaratilmaydi ──
        if self.mode == "labels_only":
            label_jobs = self.printer_id.print_lots(lots)
            errors = [e.error or _("Noma'lum xato")
                      for e in label_jobs.filtered(lambda j: j.state == "failed")]
            if errors:
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Chop etishda xato bor"),
                        "message": "\n".join(errors[:5]),
                        "type": "warning",
                        "sticky": True,
                    },
                }
            if self.printer_id.delivery == "local":
                msg = _("%d ta stiker chop etildi.") % len(label_jobs)
            else:
                msg = _("%d ta stiker navbatga qo'yildi.") % len(label_jobs)
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {"message": msg, "type": "success", "sticky": False},
            }

        # ── BOX rejimlar (box_and_labels / box_only) ──
        if self.capacity < 1:
            raise UserError(_("Quti sig'imi kamida 1 bo'lishi kerak."))
        to_box = self._lots_to_box()

        errors = []
        boxes = self.env["agronova.lot.box"].browse()
        total_label_jobs = 0
        for product in to_box.mapped("product_id"):
            group = to_box.filtered(lambda lot: lot.product_id == product)
            for i in range(0, len(group), self.capacity):
                chunk = group[i:i + self.capacity]
                box = self.env["agronova.lot.box"].create_for_lots(
                    chunk, capacity=self.capacity, date=self.date,
                )
                boxes |= box

                # Avval shu qutidagi seriallar stikeri
                if self.mode == "box_and_labels":
                    chunk_jobs = self.printer_id.print_lots(chunk)
                    total_label_jobs += len(chunk_jobs)
                    for job in chunk_jobs.filtered(lambda j: j.state == "failed"):
                        errors.append(job.error or _("Noma'lum xato"))

                # Keyin quti stikeri
                job = box.print_box_label(printer=self.printer_id)
                if job.state == "failed":
                    errors.append("%s: %s" % (box.name, job.error or _("Noma'lum xato")))

        if errors:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Qutilar yaratildi, lekin chop etishda xato bor"),
                    "message": "\n".join(errors[:5]),
                    "type": "warning",
                    "sticky": True,
                },
            }

        parts = [_("%d ta quti yaratildi.") % len(boxes)]
        if self.mode == "box_and_labels":
            if self.printer_id.delivery == "local":
                parts.append(_("%d ta stiker chop etildi.") % total_label_jobs)
            else:
                parts.append(_("%d ta stiker navbatga qo'yildi.") % total_label_jobs)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"message": " ".join(parts), "type": "success", "sticky": False},
        }
