# -*- coding: utf-8 -*-
from odoo import _, fields, models


class SssTripAttachPicking(models.TransientModel):
    """Mavjud ombor hujjatini reysga biriktirish oynasi.

    Hujjat reysdan yaratilmaydi — ombor jarayonida allaqachon yaratilgan
    transferlardan tanlanadi va shu reysga bog'lanadi.
    """
    _name = 'agronova.trip.attach.picking'
    _description = 'Reysga ombor hujjatini biriktirish'

    trip_id = fields.Many2one('agronova.trip', string="Reys", required=True,
                              ondelete='cascade')
    picking_ids = fields.Many2many(
        'stock.picking', string="Ombor hujjatlari", required=True,
        domain="[('trip_id', '=', False), ('state', '!=', 'cancel')]",
        help="Faqat boshqa reysga biriktirilmagan hujjatlar ko'rinadi.")

    def action_attach(self):
        self.ensure_one()
        self.picking_ids.write({'trip_id': self.trip_id.id})
        self.trip_id.message_post(
            body=_("Reysga %s ta ombor hujjati biriktirildi: %s",
                   len(self.picking_ids),
                   ", ".join(self.picking_ids.mapped('name'))))
        return {'type': 'ir.actions.act_window_close'}
