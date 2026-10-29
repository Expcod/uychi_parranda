from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    lot_qr_label_width = fields.Float(
        string="Yorliq kengligi (mm)",
        config_parameter="agronova_barcode.label_width",
        default=50.0,
    )
    lot_qr_label_height = fields.Float(
        string="Yorliq balandligi (mm)",
        config_parameter="agronova_barcode.label_height",
        default=30.0,
    )
    lot_complex_serials = fields.Boolean(
        string="Murakkab serial raqamlar",
        config_parameter="agronova_barcode.complex_serials",
        default=False,
        help="Yoqilgan bo'lsa serial raqamlar 8 xonali murakkab kod bo'ladi "
             "(harf + raqam + belgi, masalan K7#mQ2@x) — ketma-ket raqam o'rniga.\n"
             "O'chirilsa Odoo standart ketma-ket raqamlari ishlatiladi.",
    )
