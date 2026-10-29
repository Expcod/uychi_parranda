# -*- coding: utf-8 -*-
"""Energiya sarfi (TZ 10): elektr va gaz, bir tonna mahsulotga sarf."""
from odoo import _, api, fields, models


class AgroNovaYemEnergiya(models.Model):
    _name = 'agronova.yem.energiya'
    _description = "Yem zavodi — energiya sarfi"
    _inherit = ['mail.thread', 'agronova.yem.smena.qulf.mixin']
    _order = 'sana desc, id desc'
    _smena_qulf_erkin = {'izoh'}

    name = fields.Char("Nomi", compute='_compute_name', store=True)
    company_id = fields.Many2one('res.company', "Korxona", required=True, default=lambda s: s.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    sana = fields.Date("Sana", required=True, default=fields.Date.context_today, tracking=True)
    liniya_id = fields.Many2one('agronova.yem.liniya', "Liniya", required=True)
    smena_id = fields.Many2one('agronova.yem.smena', "Smena", index='btree_not_null',
                               domain="[('liniya_id', '=', liniya_id), ('sana', '=', sana)]")
    elektr_kwh = fields.Float("Elektr (kVt·soat)", digits=(16, 1), tracking=True)
    gaz_m3 = fields.Float("Gaz (m³)", digits=(16, 1), tracking=True)
    elektr_narx = fields.Float("1 kVt·soat narxi", digits='Product Price',
                               default=lambda s: float(s.env['ir.config_parameter'].sudo().get_param(
                                   'agronova_yem.elektr_narx', 0) or 0))
    gaz_narx = fields.Float("1 m³ gaz narxi", digits='Product Price',
                            default=lambda s: float(s.env['ir.config_parameter'].sudo().get_param(
                                'agronova_yem.gaz_narx', 0) or 0))
    summa = fields.Monetary("Summa", compute='_compute_summa', store=True)
    ishlab_chiqarilgan_t = fields.Float("Ishlab chiqarildi (t)", compute='_compute_tonna', store=True,
                                        digits=(16, 2))
    kwh_t = fields.Float("kVt·soat / t", compute='_compute_tonna', store=True, digits=(16, 2))
    gaz_t = fields.Float("m³ / t", compute='_compute_tonna', store=True, digits=(16, 2))
    reja_kwh_t = fields.Float("Me'yor kVt·soat / t", compute='_compute_tonna', store=True, digits=(16, 2))
    farq_pct = fields.Float("Me'yordan farq (%)", compute='_compute_tonna', store=True, digits=(16, 1))
    izoh = fields.Text("Izoh")

    @api.depends('liniya_id', 'sana', 'smena_id')
    def _compute_name(self):
        for e in self:
            e.name = " · ".join(x for x in (e.liniya_id.name, e.sana and e.sana.strftime('%d.%m.%Y'),
                                           e.smena_id.smena_turi_id.name) if x)

    @api.depends('elektr_kwh', 'gaz_m3', 'elektr_narx', 'gaz_narx')
    def _compute_summa(self):
        for e in self:
            e.summa = e.elektr_kwh * e.elektr_narx + e.gaz_m3 * e.gaz_narx

    @api.depends('elektr_kwh', 'gaz_m3', 'smena_id.fakt_kg', 'sana', 'liniya_id')
    def _compute_tonna(self):
        norma = float(self.env['ir.config_parameter'].sudo().get_param('agronova_yem.kwh_norma_t', 0) or 0)
        for e in self:
            if e.smena_id:
                kg = e.smena_id.fakt_kg
            else:
                mos = self.env['mrp.production'].search([
                    ('agronova_liniya_id', '=', e.liniya_id.id), ('state', '=', 'done'),
                ]).filtered(lambda m: m.date_finished and fields.Datetime.context_timestamp(
                    m, m.date_finished).date() == e.sana)
                kg = sum(mos.mapped('agronova_miqdor_kg'))
            t = kg / 1000.0
            e.ishlab_chiqarilgan_t = t
            e.kwh_t = (e.elektr_kwh / t) if t else 0.0
            e.gaz_t = (e.gaz_m3 / t) if t else 0.0
            e.reja_kwh_t = norma
            e.farq_pct = ((e.kwh_t - norma) / norma * 100.0) if norma and e.kwh_t else 0.0

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._smena_qulf_tekshir()
        return recs
