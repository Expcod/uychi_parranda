# -*- coding: utf-8 -*-
from odoo import _, fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    agronova_tortish_ids = fields.One2many('agronova.tarozi.tortish', 'picking_id',
                                           "Tarozi varaqalari")
    agronova_tortish_count = fields.Integer(compute='_compute_agronova_tortish_count')
    agronova_tarozi_netto = fields.Float(
        "Tarozi netto (kg)", compute='_compute_agronova_tortish_count',
        help="Yakunlangan tortish varaqalari bo'yicha haqiqiy netto.")

    def _compute_agronova_tortish_count(self):
        for p in self:
            done = p.agronova_tortish_ids.filtered(lambda t: t.state == 'done')
            p.agronova_tortish_count = len(p.agronova_tortish_ids)
            p.agronova_tarozi_netto = sum(done.mapped('netto'))

    def _agronova_hujjat_kg(self):
        """Hujjatdagi og'irlik birligidagi qatorlar yig'indisi, kg da."""
        self.ensure_one()
        kg = self.env.ref('uom.product_uom_kgm')
        jami = 0.0
        for m in self.move_ids.filtered(lambda m: m.state != 'cancel'):
            if m.product_uom._has_common_reference(kg):
                jami += m.product_uom._compute_quantity(m.product_uom_qty, kg)
        return jami

    def action_agronova_tortish(self):
        """Hujjatdan tortish varaqasini ochadi (yo'q bo'lsa yaratadi)."""
        self.ensure_one()
        ochiq = self.agronova_tortish_ids.filtered(lambda t: t.state in ('draft', 'vazn1'))
        if not ochiq:
            kod = self.picking_type_id.code
            ochiq = self.env['agronova.tarozi.tortish'].create({
                'picking_id': self.id,
                'yonalish': {'incoming': 'kirim', 'outgoing': 'chiqim'}.get(kod, 'ichki'),
                'partner_id': self.partner_id.id,
                'product_id': self.move_ids[:1].product_id.id,
                'hujjat_netto': self._agronova_hujjat_kg(),
                'company_id': self.company_id.id,
            })
        return {
            'type': 'ir.actions.act_window', 'res_model': 'agronova.tarozi.tortish',
            'res_id': ochiq[:1].id, 'view_mode': 'form', 'target': 'current',
            'name': _("Tortish"),
        }

    def action_agronova_tortishlar(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'agronova_tarozi.action_agronova_tarozi_tortish')
        action['domain'] = [('picking_id', '=', self.id)]
        return action
