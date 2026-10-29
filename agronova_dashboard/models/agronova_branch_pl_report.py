# -*- coding: utf-8 -*-
"""7 Ta Filial Konsolidatsiyalangan P&L Hisoboti (Consolidated Branch P&L Report).

TT 4.2 va 7.2 talablari:
Korxonaning 7 ta asosiy foyda-zarar markazi (Yem zavodi, Ona tovuq, Inkubatsiya, Boquv 1-7,
So'yish, QX va Transport) bo'yicha Daromad, Xarajat, Sof foyda va Rentabellik ko'rsatkichlarini taqdim etadi.
"""
from odoo import api, fields, models, tools


class AgroNovaBranchPLReport(models.Model):
    _name = 'agronova.branch.pl.report'
    _description = "Filiallar konsolidatsiyalangan P&L hisoboti"
    _auto = False
    _order = 'oy desc, sof_foyda desc'

    oy = fields.Char("Hisobot davri (Oy)", readonly=True)
    sektor_nomi = fields.Char("Filial / Foyda-Zarar Markazi", readonly=True)
    sektor_kodi = fields.Selection([
        ('yem_zavodi', "1. Yem zavodi (Toshkent)"),
        ('ona_tovuq', "2. Ona tovuq filiali"),
        ('inkubatoriya', "3. Inkubatoriya"),
        ('boquv', "4. Boquv filiallari (1–7)"),
        ('soyish', "5. So'yish va qayta ishlash"),
        ('qishloq_xojaligi', "6. Qishloq xo'jaligi"),
        ('transport', "7. Transport logistika"),
        ('boshqa', "8. Boshqa / Umumiy"),
    ], string="Sektor kodi", readonly=True)

    daromad_tushum = fields.Monetary("Jami Daromad (so'm)", readonly=True, currency_field='currency_id')
    xarajat_jami = fields.Monetary("Jami Xarajat (so'm)", readonly=True, currency_field='currency_id')
    sof_foyda = fields.Monetary("Sof Foyda / Zarar (so'm)", readonly=True, currency_field='currency_id')
    rentabellik_foiz = fields.Float("Rentabellik (%)", readonly=True, aggregator='avg', digits=(12, 2))

    company_id = fields.Many2one('res.company', string="Kompaniya", readonly=True)
    currency_id = fields.Many2one('res.currency', string="Valyuta", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    ROW_NUMBER() OVER () AS id,
                    TO_CHAR(l.date, 'YYYY-MM') AS oy,
                    CASE
                        WHEN a.name::text ILIKE '%%yem%%' THEN '1. Yem zavodi (Toshkent)'
                        WHEN a.name::text ILIKE '%%ona%%' THEN '2. Ona tovuq filiali'
                        WHEN a.name::text ILIKE '%%inkub%%' THEN '3. Inkubatoriya'
                        WHEN a.name::text ILIKE '%%boquv%%' THEN '4. Boquv filiallari (1–7)'
                        WHEN a.name::text ILIKE '%%so''yish%%' OR a.name::text ILIKE '%%soyish%%' THEN '5. So''yish va qayta ishlash'
                        WHEN a.name::text ILIKE '%%qishloq%%' OR a.name::text ILIKE '%%yer%%' THEN '6. Qishloq xo''jaligi'
                        WHEN a.name::text ILIKE '%%reys%%' OR a.name::text ILIKE '%%transport%%' THEN '7. Transport logistika'
                        ELSE '8. Markaziy savdo va boshqaruv'
                    END AS sektor_nomi,
                    CASE
                        WHEN a.name::text ILIKE '%%yem%%' THEN 'yem_zavodi'
                        WHEN a.name::text ILIKE '%%ona%%' THEN 'ona_tovuq'
                        WHEN a.name::text ILIKE '%%inkub%%' THEN 'inkubatoriya'
                        WHEN a.name::text ILIKE '%%boquv%%' THEN 'boquv'
                        WHEN a.name::text ILIKE '%%so''yish%%' OR a.name::text ILIKE '%%soyish%%' THEN 'soyish'
                        WHEN a.name::text ILIKE '%%qishloq%%' OR a.name::text ILIKE '%%yer%%' THEN 'qishloq_xojaligi'
                        WHEN a.name::text ILIKE '%%reys%%' OR a.name::text ILIKE '%%transport%%' THEN 'transport'
                        ELSE 'boshqa'
                    END AS sektor_kodi,
                    SUM(CASE WHEN l.amount > 0 THEN l.amount ELSE 0 END) AS daromad_tushum,
                    SUM(CASE WHEN l.amount < 0 THEN ABS(l.amount) ELSE 0 END) AS xarajat_jami,
                    SUM(l.amount) AS sof_foyda,
                    CASE
                        WHEN SUM(CASE WHEN l.amount < 0 THEN ABS(l.amount) ELSE 0 END) > 0
                        THEN (SUM(l.amount) / SUM(CASE WHEN l.amount < 0 THEN ABS(l.amount) ELSE 0 END) * 100)
                        ELSE 0
                    END AS rentabellik_foiz,
                    l.company_id AS company_id,
                    l.currency_id AS currency_id
                FROM account_analytic_line l
                LEFT JOIN account_analytic_account a ON l.account_id = a.id
                GROUP BY TO_CHAR(l.date, 'YYYY-MM'), sektor_nomi, sektor_kodi, l.company_id, l.currency_id
            )
        """ % self._table)
