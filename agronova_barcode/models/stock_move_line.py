"""Skanerlangan qatorni rezervatsiyadan ajratish.

Odoo transferni tayyorlaganda (`_action_assign`) omborda mavjud seriyalarni
avtomatik topib `move_line` ga biriktiradi — bunda `lot_id` to'ladi, lekin
hech kim hech narsani skanerlamagan. Modul avval "skanerlangan" ni faqat
`lot_id` borligiga qarab hisoblardi va rezerv qilingan qatorlarni skanerlangan
deb o'qib qo'yardi ("4 / 10 skanerlangan" — omborchi hali boshlamagan bo'lsa ham).

`picked` ga tayanib bo'lmaydi: u Odoo'ning o'z maydoni, boshqa modullar va
oqimlar ham unga yozadi. Shuning uchun modulning O'Z belgisi kerak.
"""
from odoo import fields, models


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    qr_scanned = fields.Boolean(
        "QR skanerlangan", default=False, copy=False, index=True,
        help="Bu qator QR skaner orqali kiritilganmi. Tizim avtomatik "
             "rezerv qilgan qatorlarda False bo'ladi.",
    )
    qr_box_id = fields.Many2one(
        "agronova.lot.box", "Skanerlangan quti", copy=False, index=True,
        ondelete="set null",
        help="Bu seriya quti QR kodi orqali kirgan bo'lsa — o'sha quti. "
             "Bittalab skanerlanganda bo'sh bo'ladi.",
    )
