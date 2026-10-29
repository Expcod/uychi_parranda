"""Chop etish navbati.

Odoo job yaratadi, sexdagi agent uni olib printerga yuboradi va natijani
qaytaradi. Shu bilan server uzoqda (VPS) bo'lsa ham chop etish ishlaydi —
agent o'zi murojaat qiladi, serverga printerga yo'l kerak emas.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessDenied, UserError

_logger = logging.getLogger(__name__)

# Agent bir martada olishi mumkin bo'lgan maksimal job soni
MAX_BATCH = 50


class StockLabelPrintJob(models.Model):
    _name = "agronova.label.print.job"
    _description = "Stiker chop etish ishi"
    _order = "id desc"

    printer_id = fields.Many2one(
        "agronova.label.printer", "Printer", required=True, ondelete="cascade", index=True)
    lot_id = fields.Many2one("stock.lot", "Lot", ondelete="set null", index=True)
    copies = fields.Integer("Nusxalar", default=1)
    payload = fields.Text("Printer buyruqlari", required=True)
    note = fields.Char("Izoh")

    state = fields.Selection(
        [
            ("pending", "Navbatda"),
            ("sent", "Agentga berildi"),
            ("done", "Chop etildi"),
            ("failed", "Xato"),
        ],
        default="pending", required=True, index=True,
    )
    error = fields.Char("Xato xabari")
    sent_at = fields.Datetime("Berilgan vaqt")
    done_at = fields.Datetime("Tugagan vaqt")

    def write(self, vals):
        """Job 'done' bo'lganda lotni "stiker chop etilgan" deb belgilaydi.

        Bu yerda ushlanadi, chunki 'done' uch xil yo'ldan keladi: lokal chop etish,
        agentning hisoboti va qayta urinish. Har birida alohida yozish o'rniga
        bitta nuqta ishonchliroq.
        """
        res = super().write(vals)
        if vals.get("state") == "done":
            lots = self.lot_id.filtered(lambda lot: not lot.label_printed)
            if lots:
                lots.sudo().write({
                    "label_printed": True,
                    "label_printed_at": fields.Datetime.now(),
                })
        return res

    # ------------------------------------------------------------------
    # Lokal chop etish (server va printer bitta kompyuterda)
    # ------------------------------------------------------------------
    def _run_local(self):
        """win32print orqali bevosita chop etadi. Faqat Windows'da ishlaydi."""
        for job in self:
            try:
                job._send_win32(job.printer_id.system_name, job.payload,
                                job.printer_id.encoding)
            except Exception as exc:
                _logger.exception("Lokal chop etish xatosi (job %s)", job.id)
                job.write({"state": "failed", "error": str(exc)[:250]})
            else:
                job.write({
                    "state": "done",
                    "done_at": fields.Datetime.now(),
                    "error": False,
                })

    @staticmethod
    def _send_win32(printer_name, payload, encoding="cp1251"):
        """RAW rejimda printerga yuboradi — drayver buyruqlarni o'zgartirmaydi."""
        try:
            import win32print
        except ImportError:
            raise UserError(_(
                "pywin32 o'rnatilmagan — to'g'ridan-to'g'ri chop etish ishlamaydi. "
                "Navbat usulidan foydalaning."
            ))

        from . import label_renderer as lr
        data = lr.encode_payload(payload, encoding or "cp1251")

        handle = win32print.OpenPrinter(printer_name)
        try:
            win32print.StartDocPrinter(handle, 1, ("Odoo stiker", None, "RAW"))
            win32print.StartPagePrinter(handle)
            win32print.WritePrinter(handle, data)
            win32print.EndPagePrinter(handle)
            win32print.EndDocPrinter(handle)
        finally:
            win32print.ClosePrinter(handle)

    # ------------------------------------------------------------------
    # Agent API — sexdagi dastur shu metodlarni chaqiradi
    # ------------------------------------------------------------------
    @api.model
    def agent_fetch(self, token, limit=10):
        """Navbatdagi ishlarni beradi va ularni 'sent' deb belgilaydi.

        :return: [{id, payload, copies, printer}]
        """
        printer = self._agent_printer(token)
        limit = max(1, min(int(limit or 10), MAX_BATCH))

        jobs = self.sudo().search(
            [("printer_id", "=", printer.id), ("state", "=", "pending")],
            order="id", limit=limit,
        )
        if not jobs:
            return []

        jobs.write({"state": "sent", "sent_at": fields.Datetime.now()})
        return [{
            "id": job.id,
            "payload": job.payload,
            "copies": job.copies,
            "printer": printer.system_name,
            # Agent baytga aylantirishda shuni ishlatadi — kirill matn
            # UTF-8 da yuborilsa printerning ichki shrifti buzib chiqaradi.
            "encoding": printer.encoding,
        } for job in jobs]

    @api.model
    def agent_report(self, token, results):
        """Agent natijalarni qaytaradi.

        :param results: [{id, ok: bool, error: str}]
        """
        printer = self._agent_printer(token)
        if not results:
            return True

        by_id = {int(r["id"]): r for r in results if r.get("id")}
        jobs = self.sudo().search([
            ("id", "in", list(by_id)),
            ("printer_id", "=", printer.id),
        ])
        now = fields.Datetime.now()
        for job in jobs:
            res = by_id[job.id]
            if res.get("ok"):
                job.write({"state": "done", "done_at": now, "error": False})
            else:
                job.write({
                    "state": "failed",
                    "done_at": now,
                    "error": (res.get("error") or _("Noma'lum xato"))[:250],
                })
        return True

    @api.model
    def _agent_printer(self, token):
        """Kalit bo'yicha printerni topadi. Noto'g'ri kalit — kirish rad etiladi."""
        if not token:
            raise AccessDenied()
        printer = self.env["agronova.label.printer"].sudo().search(
            [("agent_token", "=", token)], limit=1)
        if not printer:
            _logger.warning("Stiker agenti noto'g'ri kalit bilan murojaat qildi")
            raise AccessDenied()
        return printer

    # ------------------------------------------------------------------
    # Qo'lda boshqarish
    # ------------------------------------------------------------------
    def action_retry(self):
        """Xato bo'lgan ishni qayta navbatga qo'yadi."""
        stuck = self.filtered(lambda j: j.state in ("failed", "sent"))
        stuck.write({"state": "pending", "error": False,
                     "sent_at": False, "done_at": False})
        if any(j.printer_id.delivery == "local" for j in stuck):
            stuck.filtered(lambda j: j.printer_id.delivery == "local")._run_local()
        return True

    def action_cancel(self):
        self.filtered(lambda j: j.state in ("pending", "sent")).write({
            "state": "failed", "error": _("Bekor qilindi"),
        })
        return True

    @api.autovacuum
    def _gc_old_jobs(self):
        """Eski yakunlangan ishlarni tozalaydi (30 kundan oshgan)."""
        limit_date = fields.Datetime.subtract(fields.Datetime.now(), days=30)
        old = self.search([
            ("state", "in", ("done", "failed")),
            ("done_at", "<", limit_date),
        ])
        if old:
            _logger.info("Stiker navbati: %d ta eski yozuv o'chirildi", len(old))
            old.unlink()
