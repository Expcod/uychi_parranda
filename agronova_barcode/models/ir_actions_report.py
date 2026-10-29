from odoo import models


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        # Lot QR stikeri chop etilishidan oldin paperformat o'lchamini
        # Sozlamalardagi qiymatlar bilan sinxronlaymiz — foydalanuvchi mm da
        # kenglik/balandlikni o'zgartira olishi uchun.
        report = self._get_report(report_ref)
        if report.report_name == "agronova_barcode.report_lot_qr_label":
            params = self.env["ir.config_parameter"].sudo()
            width = float(params.get_param("agronova_barcode.label_width", 50) or 50)
            height = float(params.get_param("agronova_barcode.label_height", 30) or 30)
            paperformat = report.paperformat_id
            if paperformat and (
                paperformat.page_width != width or paperformat.page_height != height
            ):
                paperformat.sudo().write(
                    {"page_width": width, "page_height": height}
                )
        return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)
