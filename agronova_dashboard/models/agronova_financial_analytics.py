# -*- coding: utf-8 -*-
"""Moliyaviy va P&L Tahlili (Financial & Branch Profitability Analytics).

Ushbu model (M12.4) barcha 7 ta filial va faoliyat yo'nalishi kesimida Daromad, Xarajat,
Ichki transferlar va Sof foyda marjalarini analitik jurnallar va buxgalteriya yozuvlari asosida
SQL View (Pivot, Grafik, Dashboard) orqali taqdim etadi.
"""
from odoo import api, fields, models, tools


class AgroNovaFinancialAnalytics(models.Model):
    _name = 'agronova.financial.analytics'
    _description = "Moliyaviy va P&L Tahlili (Financial Analytics)"
    _auto = False
    _order = 'sana desc, sektor'

    sana = fields.Date("Sana", readonly=True)
    yil = fields.Char("Yil", readonly=True)
    oy = fields.Char("Oy", readonly=True)

    sektor = fields.Selection([
        ('boquv', "Boquv (Andijon)"),
        ('yem_zavodi', "Yem zavodi (Toshkent)"),
        ('ona_tovuq', "Ona tovuq"),
        ('inkubatoriya', "Inkubatoriya"),
        ('soyish', "So'yish sexi"),
        ('qishloq_xojaligi', "Qishloq xo'jaligi"),
        ('transport', "Transport va logistika"),
        ('savdo_kassa', "Savdo va Kassa"),
    ], string="Filial / Faoliyat yo'nalishi", readonly=True)

    xarajat_turi = fields.Selection([
        ('yem', "Yem xomashyosi va yem sarfi"),
        ('joja', "Jo'ja (boshlang'ich mol)"),
        ('kommunal', "Kommunal (gaz, elektr, suv)"),
        ('ish_haqi', "Ish haqi va xizmatlar"),
        ('veterinariya', "Veterinariya va dori-darmon"),
        ('ijara', "Bino va yer ijarasi"),
        ('transport', "Transport va yoqilg'i"),
        ('amortizatsiya', "Amortizatsiya va boshqa"),
        ('daromad', "Sotuv va xizmat tushumi"),
    ], string="Xarajat / Daromad moddasi", readonly=True)

    daromad_summa = fields.Monetary("Daromad (so'm)", readonly=True, currency_field='currency_id')
    xarajat_summa = fields.Monetary("Xarajat (so'm)", readonly=True, currency_field='currency_id')
    operatsion_foyda = fields.Monetary("Operatsion foyda (so'm)", readonly=True, currency_field='currency_id')

    company_id = fields.Many2one('res.company', string="Kompaniya", readonly=True)
    currency_id = fields.Many2one('res.currency', string="Valyuta", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                -- 1. ANALITIK JURNALLAR VA BUXGALTERIYA OQIMLARI
                SELECT
                    l.id AS id,
                    l.date AS sana,
                    TO_CHAR(l.date, 'YYYY') AS yil,
                    TO_CHAR(l.date, 'YYYY-MM') AS oy,
                    CASE
                        WHEN a.name::text ILIKE '%%boquv%%' THEN 'boquv'
                        WHEN a.name::text ILIKE '%%yem%%' THEN 'yem_zavodi'
                        WHEN a.name::text ILIKE '%%ona%%' THEN 'ona_tovuq'
                        WHEN a.name::text ILIKE '%%inkub%%' THEN 'inkubatoriya'
                        WHEN a.name::text ILIKE '%%so''yish%%' OR a.name::text ILIKE '%%soyish%%' THEN 'soyish'
                        WHEN a.name::text ILIKE '%%qishloq%%' OR a.name::text ILIKE '%%yer%%' THEN 'qishloq_xojaligi'
                        WHEN a.name::text ILIKE '%%reys%%' OR a.name::text ILIKE '%%transport%%' THEN 'transport'
                        ELSE 'savdo_kassa'
                    END AS sektor,
                    CASE
                        WHEN l.amount > 0 THEN 'daromad'
                        WHEN l.name::text ILIKE '%%yem%%' THEN 'yem'
                        WHEN l.name::text ILIKE '%%jo''ja%%' OR l.name::text ILIKE '%%joja%%' THEN 'joja'
                        WHEN l.name::text ILIKE '%%gaz%%' OR l.name::text ILIKE '%%elektr%%' OR l.name::text ILIKE '%%suv%%' THEN 'kommunal'
                        WHEN l.name::text ILIKE '%%ish haqi%%' OR l.name::text ILIKE '%%oylik%%' THEN 'ish_haqi'
                        WHEN l.name::text ILIKE '%%dori%%' OR l.name::text ILIKE '%%vaksina%%' THEN 'veterinariya'
                        WHEN l.name::text ILIKE '%%ijara%%' THEN 'ijara'
                        WHEN l.name::text ILIKE '%%yoqilg''i%%' OR l.name::text ILIKE '%%yo''l%%' THEN 'transport'
                        ELSE 'amortizatsiya'
                    END AS xarajat_turi,
                    CASE WHEN l.amount > 0 THEN l.amount ELSE 0 END AS daromad_summa,
                    CASE WHEN l.amount < 0 THEN ABS(l.amount) ELSE 0 END AS xarajat_summa,
                    l.amount AS operatsion_foyda,
                    l.company_id AS company_id,
                    l.currency_id AS currency_id
                FROM account_analytic_line l
                LEFT JOIN account_analytic_account a ON l.account_id = a.id
            )
        """ % self._table)
