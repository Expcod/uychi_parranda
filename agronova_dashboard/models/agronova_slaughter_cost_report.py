# -*- coding: utf-8 -*-
"""C ilovasi — So'yishda tannarxni taqsimlash hisoboti (Slaughter NRV Cost Allocation).

TT 7.1 va C ilovasidagi talablar:
So'yish jarayonida bitta kirimdan (tirik tovuq) bir nechta mahsulot chiqadi.
Tannarx sotuv narxi koeffitsienti (sof sotish qiymati - Net Realizable Value / NRV) usulida
mahsulotlar (fillet, son-boldir, qanot, tushka, ich-chovoq) orasida taqsimlanadi.
"""
from odoo import api, fields, models


class AgroNovaSlaughterCostReport(models.Model):
    _name = 'agronova.slaughter.cost.report'
    _description = "C Ilovasi: So'yish NRV Tannarx Taqsimoti Hisoboti"
    _order = 'sana desc'

    name = fields.Char("Hisobot / Smena nomi", required=True)
    sana = fields.Date("So'yish sanasi", default=fields.Date.context_today)

    # -------------------------------------------------------------------------
    # KIRIM (TIRIK TOVUQ)
    # -------------------------------------------------------------------------
    kirim_tirik_vazn_kg = fields.Float("Kirim: Jami tirik vazn (kg)", default=1000.0, digits=(12, 2))
    kirim_bosh_soni = fields.Integer("Kirim: Tovuq bosh soni", default=400)
    kirim_tirik_tannarx_kg = fields.Monetary("1 kg tirik tovuq tannarxi (so'm)", default=12180.0)
    kirim_jami_tannarx = fields.Monetary("Kirim jami tannarxi (so'm)", compute='_compute_kirim_tannarx', store=True)

    # -------------------------------------------------------------------------
    # NRV TAQSIMOT KOEFFITSIENTI
    # -------------------------------------------------------------------------
    jami_sotuv_qiymati = fields.Monetary("Jami chiqim sotuv qiymati (so'm)", compute='_compute_chiqim_hisobi', store=True)
    taqsimlash_koeffitsienti = fields.Float("Taqsimlash koeffitsienti (K)", compute='_compute_chiqim_hisobi', store=True, digits=(12, 4))
    chiqim_foizi = fields.Float("Chiqim foizi (%)", compute='_compute_chiqim_hisobi', store=True, digits=(12, 2))

    line_ids = fields.One2many('agronova.slaughter.cost.line', 'report_id', string="Chiqim mahsulotlari qatorlari")
    currency_id = fields.Many2one('res.currency', string="Valyuta", default=lambda self: self.env.company.currency_id)

    @api.depends('kirim_tirik_vazn_kg', 'kirim_tirik_tannarx_kg')
    def _compute_kirim_tannarx(self):
        for rec in self:
            rec.kirim_jami_tannarx = (rec.kirim_tirik_vazn_kg or 0.0) * (rec.kirim_tirik_tannarx_kg or 0.0)

    @api.depends('line_ids.sotuv_qiymati', 'kirim_jami_tannarx', 'kirim_tirik_vazn_kg', 'line_ids.miqdor_kg')
    def _compute_chiqim_hisobi(self):
        for rec in self:
            tot_val = sum(rec.line_ids.mapped('sotuv_qiymati'))
            rec.jami_sotuv_qiymati = tot_val
            rec.taqsimlash_koeffitsienti = (rec.kirim_jami_tannarx / tot_val) if tot_val > 0 else 0.0

            tot_kg = sum(rec.line_ids.mapped('miqdor_kg'))
            rec.chiqim_foizi = (tot_kg / rec.kirim_tirik_vazn_kg * 100) if rec.kirim_tirik_vazn_kg > 0 else 0.0


class AgroNovaSlaughterCostLine(models.Model):
    _name = 'agronova.slaughter.cost.line'
    _description = "So'yish Chiqim Mahsuloti Qatori"

    report_id = fields.Many2one('agronova.slaughter.cost.report', string="Hisobot", ondelete='cascade', required=True)
    mahsulot_nomi = fields.Char("Chiqim mahsuloti", required=True)
    miqdor_kg = fields.Float("Miqdori (kg)", required=True, default=0.0, digits=(12, 2))
    sotuv_narxi_kg = fields.Monetary("Sotuv narxi (so'm/kg)", required=True, default=0.0)
    sotuv_qiymati = fields.Monetary("Sotuv qiymati (so'm)", compute='_compute_qiymat', store=True)

    tannarx_kg = fields.Monetary("Tannarx (so'm/kg)", compute='_compute_tannarx', store=True)
    jami_tannarx = fields.Monetary("Jami tannarxi (so'm)", compute='_compute_tannarx', store=True)
    currency_id = fields.Many2one(related='report_id.currency_id')

    @api.depends('miqdor_kg', 'sotuv_narxi_kg')
    def _compute_qiymat(self):
        for rec in self:
            rec.sotuv_qiymati = (rec.miqdor_kg or 0.0) * (rec.sotuv_narxi_kg or 0.0)

    @api.depends('sotuv_narxi_kg', 'report_id.taqsimlash_koeffitsienti', 'miqdor_kg')
    def _compute_tannarx(self):
        for rec in self:
            k = rec.report_id.taqsimlash_koeffitsienti or 0.0
            narx = rec.sotuv_narxi_kg or 0.0
            t_kg = narx * k
            rec.tannarx_kg = t_kg
            rec.jami_tannarx = t_kg * (rec.miqdor_kg or 0.0)
