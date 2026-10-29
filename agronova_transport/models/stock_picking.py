# -*- coding: utf-8 -*-
from odoo import fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    trip_id = fields.Many2one(
        'agronova.trip', string="Reys", index='btree_not_null', ondelete='set null',
        copy=False,
        help="Tovar shu reysda tashilgan. Reys kartochkasida qaysi mahsulot, "
             "qayerdan qayerga va qancha ketgani ko'rinadi.")
