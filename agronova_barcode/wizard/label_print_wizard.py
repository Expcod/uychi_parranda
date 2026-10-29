"""Bir nechta printer bo'lganda tanlash oynasi."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StockLabelPrintWizard(models.TransientModel):
    _name = "agronova.label.print.wizard"
    _description = "Stiker chop etish"

    printer_id = fields.Many2one(
        "agronova.label.printer", "Printer", required=True,
        default=lambda self: self.env["agronova.label.printer"].search([], limit=1),
    )
    lot_ids = fields.Many2many("stock.lot", string="Lotlar")
    box_ids = fields.Many2many("agronova.lot.box", string="Qutilar")
    copies = fields.Integer("Har biridan nechta", default=1, required=True)

    total_labels = fields.Integer("Jami stiker", compute="_compute_total")

    @api.depends("lot_ids", "box_ids", "copies")
    def _compute_total(self):
        for wiz in self:
            count = len(wiz.lot_ids) + len(wiz.box_ids)
            wiz.total_labels = count * max(1, wiz.copies)

    def action_print(self):
        self.ensure_one()
        if self.copies < 1:
            raise UserError(_("Nusxalar soni 1 dan kam bo'lmasligi kerak."))

        jobs = self.env["agronova.label.print.job"].browse()
        if self.lot_ids:
            jobs |= self.printer_id.print_lots(self.lot_ids, copies=self.copies)
        if self.box_ids:
            for box in self.box_ids:
                for _ in range(self.copies):
                    jobs |= box.print_box_label(printer=self.printer_id)
        return self.env["stock.lot"]._label_print_notification(jobs, self.printer_id)
