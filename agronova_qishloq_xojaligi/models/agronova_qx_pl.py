# -*- coding: utf-8 -*-
"""Qishloq xo'jaligi bo'limining foyda-zarar hisoboti.

Tuzilma `agronova.pl.mixin` da. Bu bo'limga xos manbalar:

* analitik hisoblar — **ekin partiyalari va yer maydonlari**. Yer alohida
  reja: unga partiyaga bog'lanmagan doimiy xarajat tushadi (yer solig'i,
  sug'orish tarmog'i), shuning uchun ikkalasi ham hisobga olinadi;
* ichki sotuv — `agronova.qx.ichki_berish`, ya'ni Yem zavodiga berilgan don;
* ishlab chiqarish ko'rsatkichi — olingan hosil, hosildorlik va 1 kg
  tannarxi.

Hosildorlik (kg/ga) bu bo'limning asosiy KPI si: bir gektardan qancha
mahsulot olingani.
"""
from odoo import _, fields, models


class AgroNovaQxPl(models.TransientModel):
    _name = 'agronova.qx.pl'
    _description = "Qishloq xo'jaligi — bo'lim foyda-zarari"
    _inherit = ['agronova.pl.mixin']

    qator_ids = fields.One2many(
        'agronova.qx.pl.qator', 'pl_id', string="Xarajat tarkibi")

    # --- Qishloq xo'jaligiga xos ko'rsatkichlar
    olingan_hosil_kg = fields.Float("Olingan hosil (kg)", compute='_compute_pl',
                                    digits='Product Unit')
    maydon_ga = fields.Float("Hosil olingan maydon (ga)", compute='_compute_pl')
    hosildorlik = fields.Float("Hosildorlik (kg/ga)", compute='_compute_pl')
    tannarx_1_kg = fields.Monetary("1 kg tannarxi", compute='_compute_pl')

    # ------------------------------------------------------------- ilgaklar
    def _pl_nom(self):
        return _("Qishloq xo'jaligi — foyda va zarar")

    def _pl_qator_model(self):
        return 'agronova.qx.pl.qator'

    def _pl_view_xmlid(self):
        return 'agronova_qishloq_xojaligi.view_qx_pl_form'

    def _pl_company(self):
        """Yer maydonlari qaysi korxonada bo'lsa — bo'lim ham o'sha yerda."""
        yer = self.env['agronova.qx.yer'].sudo().search([], limit=1)
        return yer.company_id or self.env.company

    def _pl_analytic_accounts(self):
        self.ensure_one()
        Partiya = self.env['agronova.qx.partiya']
        Yer = self.env['agronova.qx.yer']
        return (Partiya.search([('company_id', '=', self.company_id.id)])
                .mapped('analytic_account_id')
                | Yer.search([('company_id', '=', self.company_id.id)])
                .mapped('analytic_account_id'))

    def _pl_ichki_sotuv(self):
        self.ensure_one()
        berishlar = self.env['agronova.qx.ichki_berish'].sudo().search([
            ('company_id', '=', self.company_id.id),
            ('holat', '=', 'done'),
            ('date', '>=', self.davr_boshi),
            ('date', '<=', self.davr_oxiri),
        ])
        # Don Yem zavodiga ba'zan ichki berish hujjati bilan, ba'zan
        # korxonalararo sotuv buyurtmasi bilan o'tadi — ikkalasi ham.
        return super()._pl_ichki_sotuv() + sum(berishlar.mapped('summa'))

    def _pl_korsatkichlar(self):
        self.ensure_one()
        hosillar = self.env['agronova.qx.hosil'].sudo().search([
            ('company_id', '=', self.company_id.id),
            ('holat', '=', 'done'),
            ('date', '>=', self.davr_boshi),
            ('date', '<=', self.davr_oxiri),
        ])
        self.olingan_hosil_kg = sum(hosillar.mapped('miqdor_kg'))

        # Maydon davr bo'yicha emas, hosil olingan partiyalar bo'yicha —
        # bir partiyadan bir necha marta hosil olinsa ikki marta sanalmasin.
        partiyalar = hosillar.mapped('partiya_id')
        self.maydon_ga = sum(
            p.maydoni_ga or p.yer_id.maydoni_ga for p in partiyalar)
        self.hosildorlik = (self.olingan_hosil_kg / self.maydon_ga
                            if self.maydon_ga else 0.0)
        self.tannarx_1_kg = (self.ishlab_chiqarish / self.olingan_hosil_kg
                             if self.olingan_hosil_kg else 0.0)


class AgroNovaQxPlQator(models.TransientModel):
    _name = 'agronova.qx.pl.qator'
    _description = "Qishloq xo'jaligi — foyda-zarar hisoboti qatori"
    _inherit = ['agronova.pl.qator.mixin']

    pl_id = fields.Many2one('agronova.qx.pl', string="Hisobot",
                            ondelete='cascade')
    currency_id = fields.Many2one(related='pl_id.currency_id', readonly=True)
