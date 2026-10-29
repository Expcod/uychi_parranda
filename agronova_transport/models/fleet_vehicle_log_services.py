# -*- coding: utf-8 -*-
from odoo import fields, models


class FleetVehicleLogServices(models.Model):
    _inherit = 'fleet.vehicle.log.services'

    trip_id = fields.Many2one(
        'agronova.trip', string="Reys", index='btree_not_null', ondelete='set null',
        help="Yo'lda qilingan ta'mir yoki xizmat shu reysning xarajatiga qo'shiladi.")
