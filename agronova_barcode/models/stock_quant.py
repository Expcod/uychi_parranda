"""Inventarizatsiyada stiker holati va serialli mahsulot himoyasi.

Omborchi ro'yxatga qarab qaysi seriyaning stikeri hali chop etilmaganini
darhol ko'radi — aks holda ommaviy yaratilgan yuzlab seriya orasidan
stikersizini topish imkonsiz bo'lardi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class StockQuant(models.Model):
    _inherit = "stock.quant"

    qr_scan_required = fields.Boolean(
        string="QR skanerlash",
        related="lot_id.qr_scan_required",
        readonly=False,
        store=True,
        help="Bu seriya uchun transferda majburiy QR skanerlash talab qilinadimi. "
             "O'chirib qo'yilsa (False) transferda skanersiz o'tkazish mumkin.",
    )

    # `related` emas, `compute` — lotsiz quant (tracking yo'q mahsulot) uchun
    # "yo'q" holati kerak, related bo'lsa u False bo'lib "chop etilmagan" ga
    # qo'shilib ketardi.
    label_state = fields.Selection(
        [
            ("printed", "Chop etilgan"),
            ("not_printed", "Chop etilmagan"),
            ("na", "Kerak emas"),
        ],
        string="Stiker",
        compute="_compute_label_state",
        search="_search_label_state",
        help="Bu seriyaning QR stikeri chop etilganmi.",
    )
    label_printed_at = fields.Datetime(
        string="Stiker sanasi",
        related="lot_id.label_printed_at",
        readonly=True,
        help="Bu seriyaning QR stikeri chop etilgan sana va vaqt.",
    )

    def _compute_label_state(self):
        for quant in self:
            if not quant.lot_id:
                quant.label_state = "na"
            else:
                quant.label_state = "printed" if quant.lot_id.label_printed else "not_printed"

    # Har holat uchun domen — qidiruvda ham, filtrda ham shu ishlatiladi.
    _LABEL_STATE_DOMAINS = {
        "na": [("lot_id", "=", False)],
        "printed": [("lot_id", "!=", False), ("lot_id.label_printed", "=", True)],
        "not_printed": [("lot_id", "!=", False), ("lot_id.label_printed", "=", False)],
    }

    def _search_label_state(self, operator, value):
        """Ro'yxatni stiker holati bo'yicha filtrlash uchun."""
        if operator not in ("=", "!=") or value not in self._LABEL_STATE_DOMAINS:
            raise UserError(_("Stiker holati bo'yicha bu qidiruv qo'llab-quvvatlanmaydi."))
        domain = self._LABEL_STATE_DOMAINS[value]
        if operator == "=":
            return domain
        # `!=` — shu holatga TUSHMAYDIGANLARI. Domenni teskarilash o'rniga
        # mos yozuvlarni topib, ulardan tashqarisini so'raymiz: `lot_id.x` kabi
        # bog'langan shartlarni qo'lda inkor qilish xatoga olib keladi.
        matching = self.sudo().search(domain)
        return [("id", "not in", matching.ids)]

    # ------------------------------------------------------------------
    # Serialli mahsulot himoyasi
    # ------------------------------------------------------------------
    @api.constrains("quantity", "lot_id", "product_id", "location_id")
    def _check_serial_quantity(self):
        """Serialli mahsulotda seriyasiz yoki 1 dan katta qoldiqni taqiqlaydi.

        Odoo standarti bu bo'shliqni qoldirgan: `check_quantity` faqat LOT BOR
        quantlarni tekshiradi (`and q.lot_id`), shu sababli omborchi seriyasiz
        qatorga "10" yozib qo'ysa hech qanday xato chiqmasdi. Natijada mahsulotda
        10 dona ko'rinardi, lekin ular qaysi tovar ekani noma'lum — stiker chop
        etib bo'lmaydi, sotishda tanlab bo'lmaydi.

        Faqat ijobiy qoldiq tekshiriladi. Manfiy qoldiq (yetishmovchilik) va
        `inventory`/`production` kabi virtual joylar tegilmaydi — ular Odoo ichki
        mexanizmi va uni buzish oqimlarni sindiradi.
        """
        for quant in self:
            product = quant.product_id
            if product.tracking != "serial":
                continue
            if quant.location_id.usage not in ("internal", "transit"):
                continue
            if product.uom_id.compare(quant.quantity, 0) <= 0:
                continue

            if not quant.lot_id:
                raise ValidationError(_(
                    "«%(product)s» seriya bo'yicha kuzatiladi — seriyasiz qoldiq "
                    "kiritib bo'lmaydi.\n\n"
                    "Mahsulot kartasidagi «Ommaviy seriya qo'shish» tugmasidan "
                    "foydalaning: kerakli sonni kiritsangiz har bir dona uchun "
                    "alohida seriya yaratiladi.",
                ) % {"product": product.display_name})

            if product.uom_id.compare(quant.quantity, 1) > 0:
                raise ValidationError(_(
                    "«%(product)s» seriya bo'yicha kuzatiladi — bitta seriyada "
                    "faqat 1 dona bo'lishi mumkin (kiritildi: %(qty)s).\n\n"
                    "«%(lot)s» seriyasi bitta jismoniy tovarni bildiradi.",
                ) % {
                    "product": product.display_name,
                    "qty": quant.quantity,
                    "lot": quant.lot_id.name,
                })

    def action_print_lot_labels(self):
        """Tanlangan qatorlar uchun qutiga solish wizardini ochadi.

        Seriallar sig'im bo'yicha BOX larga jamlanadi va quti QR stikerlari
        chop etiladi; rejimga qarab har serialning alohida stikeri ham chiqadi.
        Lotsiz qatorlar e'tiborga olinmaydi.
        """
        lots = self.mapped("lot_id")
        if not lots:
            raise UserError(_("Tanlangan qatorlarda lot/seriya yo'q."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Qutiga solish va chop etish"),
            "res_model": "agronova.lot.box.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_lot_ids": lots.ids},
        }
