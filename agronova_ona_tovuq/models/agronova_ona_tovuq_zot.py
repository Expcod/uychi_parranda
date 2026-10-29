# -*- coding: utf-8 -*-
from odoo import fields, models


class AgroNovaOnaTovuqZot(models.Model):
    """Tovuq zoti / turi (Lohmann, Hy-Line, Ross va h.k.)."""
    _name = 'agronova.ona_tovuq.zot'
    _description = "Ona tovuq zoti"
    _order = 'name'

    name = fields.Char("Zot nomi", required=True)
    code = fields.Char("Kod")
    active = fields.Boolean("Faol", default=True)
    ostirish_kun = fields.Integer(
        "O'stirish davri (kun)", default=140,
        help="Jo'ja kelganidan tuxumga kirguncha o'rtacha kun soni. "
             "Jo'ja o'stirish partiyasini yopish vaqtini rejalashtirishda ishlatiladi.")
    tuxum_davri_hafta = fields.Integer(
        "Tuxum berish davri (hafta)", default=60,
        help="Podaning normal tuxum berish davri. Shundan keyin poda "
             "eskirgan deb hisoblanadi.")
    normativ_ids = fields.One2many(
        'agronova.ona_tovuq.normativ', 'zot_id', string="Normativlar")
    note = fields.Text("Izoh")

    _name_uniq = models.Constraint(
        'UNIQUE(name)', "Bu nomdagi zot allaqachon mavjud.")
