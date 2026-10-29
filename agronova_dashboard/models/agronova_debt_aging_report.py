# -*- coding: utf-8 -*-
"""Mijozlar Qarzdorligi va To'lov Intizomi Tahlili (Debt Aging & Payment Discipline Report).

TT 7.2 va M12.7 talablari:
Mijozlar va filiallararo debitorlik qarzdorligini muddatlari (0–30 kun, 31–60 kun, 60+ kun)
hamda to'lov intizomi xavf darajalari bo'yicha guruhlab ko'rsatadi.
"""
from odoo import api, fields, models, tools


class AgroNovaDebtAgingReport(models.Model):
    _name = 'agronova.debt.aging.report'
    _description = "Mijozlar Qarzdorligi va To'lov Intizomi Tahlili"
    _auto = False
    _order = 'jami_qarz desc'

    partner_id = fields.Many2one('res.partner', string="Mijoz / Kontragent", readonly=True)
    telefon = fields.Char(related='partner_id.phone', string="Telefon", readonly=True)
    masul_sotuvchi_id = fields.Many2one('res.users', string="Mas'ul sotuvchi", readonly=True)

    jami_qarz = fields.Monetary("Jami qarzdorlik (so'm)", readonly=True, currency_field='currency_id')
    qarz_0_30 = fields.Monetary("0 — 30 kun (Joriy qarz)", readonly=True, currency_field='currency_id')
    qarz_31_60 = fields.Monetary("31 — 60 kun (Kechikkan)", readonly=True, currency_field='currency_id')
    qarz_60_plus = fields.Monetary("60+ kun (Xavfli qarz)", readonly=True, currency_field='currency_id')

    eng_eski_faktura_sana = fields.Date("Eng eski ochiq faktura sanasi", readonly=True)
    kechikish_kun_soni = fields.Integer("Maksimal kechikish (kun)", readonly=True)

    xavf_darajasi = fields.Selection([
        ('yaxshi', "Normal (0-30 kun)"),
        ('ogohlantirish', "Diqqat (31-60 kun)"),
        ('xavfli', "Xavfli / Blok (60+ kun)"),
    ], string="To'lov intizomi holati", readonly=True)

    company_id = fields.Many2one('res.company', string="Kompaniya", readonly=True)
    currency_id = fields.Many2one('res.currency', string="Valyuta", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    ROW_NUMBER() OVER (ORDER BY p.id, m.company_id) AS id,
                    p.id AS partner_id,
                    p.user_id AS masul_sotuvchi_id,
                    m.company_id AS company_id,
                    c.currency_id AS currency_id,
                    SUM(m.amount_residual_signed) AS jami_qarz,
                    SUM(CASE WHEN (CURRENT_DATE - m.invoice_date) <= 30 THEN m.amount_residual_signed ELSE 0 END) AS qarz_0_30,
                    SUM(CASE WHEN (CURRENT_DATE - m.invoice_date) BETWEEN 31 AND 60 THEN m.amount_residual_signed ELSE 0 END) AS qarz_31_60,
                    SUM(CASE WHEN (CURRENT_DATE - m.invoice_date) > 60 THEN m.amount_residual_signed ELSE 0 END) AS qarz_60_plus,
                    MIN(m.invoice_date) AS eng_eski_faktura_sana,
                    MAX(CURRENT_DATE - m.invoice_date) AS kechikish_kun_soni,
                    CASE
                        WHEN MAX(CURRENT_DATE - m.invoice_date) > 60 THEN 'xavfli'
                        WHEN MAX(CURRENT_DATE - m.invoice_date) > 30 THEN 'ogohlantirish'
                        ELSE 'yaxshi'
                    END AS xavf_darajasi
                FROM account_move m
                JOIN res_partner p ON m.partner_id = p.id
                LEFT JOIN res_company c ON m.company_id = c.id
                WHERE m.move_type = 'out_invoice'
                  AND m.state = 'posted'
                  AND m.payment_state IN ('not_paid', 'partial')
                  AND m.amount_residual_signed > 0
                GROUP BY p.id, p.user_id, m.company_id, c.currency_id
            )
        """ % self._table)
