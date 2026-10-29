# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AgroNovaYemLiniya(models.Model):
    _name = 'agronova.yem.liniya'
    _description = "Yem zavodi — ishlab chiqarish liniyasi"
    _inherit = ['mail.thread']
    _order = 'sequence, name'

    name = fields.Char("Nomi", required=True, tracking=True)
    kod = fields.Char("Kodi")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', "Korxona", required=True,
                                 default=lambda s: s.env.company)
    workcenter_id = fields.Many2one('mrp.workcenter', "Ish markazi",
                                    help="Operatsiyalar va ish markazi tarifi tannarxga shu orqali kiradi.")
    quvvat_t_soat = fields.Float("Quvvati (t/soat)", default=10.0, tracking=True,
                                 help="Rejalashtirishda liniya yuklamasi shu bo'yicha hisoblanadi.")
    tarozi_id = fields.Many2one('agronova.tarozi', "Qadoqlash tarozisi",
                                domain="[('turi', 'in', ('qadoq', 'platforma'))]")
    color = fields.Integer()
    izoh = fields.Text("Izoh")

    production_count = fields.Integer(compute='_compute_production_count')

    def _compute_production_count(self):
        data = self.env['mrp.production']._read_group(
            [('agronova_liniya_id', 'in', self.ids)], ['agronova_liniya_id'], ['__count'])
        counts = {l.id: c for l, c in data}
        for l in self:
            l.production_count = counts.get(l.id, 0)

    def action_productions(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('mrp.mrp_production_action')
        action['domain'] = [('agronova_liniya_id', '=', self.id)]
        action['context'] = {'default_agronova_liniya_id': self.id}
        return action


class AgroNovaYemSmenaTuri(models.Model):
    _name = 'agronova.yem.smena.turi'
    _description = "Yem zavodi — smena"
    _order = 'sequence, id'

    name = fields.Char("Nomi", required=True)
    sequence = fields.Integer(default=10)
    boshlanish = fields.Float("Boshlanishi", default=8.0, help="Soat, masalan 8.0 = 08:00")
    tugash = fields.Float("Tugashi", default=20.0)
    davomiylik = fields.Float("Davomiyligi (soat)", compute='_compute_davomiylik')
    active = fields.Boolean(default=True)

    @api.depends('boshlanish', 'tugash')
    def _compute_davomiylik(self):
        for s in self:
            d = s.tugash - s.boshlanish
            s.davomiylik = d if d > 0 else d + 24.0
