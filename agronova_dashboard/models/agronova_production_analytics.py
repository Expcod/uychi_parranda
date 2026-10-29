# -*- coding: utf-8 -*-
"""Ishlab chiqarish va Agrar Tahlili (Production & Farming Analytics).

Ushbu model (M12.3) parrandachilik zanjirining barcha bosqichlari bo'yicha ishlab chiqarish
samaradorligini yagona SQL View (Pivot va Grafik ko'rinishlar) orqali tahlil qiladi.
"""
from odoo import api, fields, models, tools


class AgroNovaProductionAnalytics(models.Model):
    _name = 'agronova.production.analytics'
    _description = "Ishlab chiqarish va Agrar Tahlili (Production Analytics)"
    _auto = False
    _order = 'sana desc, sektor, filial_id'

    name = fields.Char("Nomi / Partiya", readonly=True)
    sektor = fields.Selection([
        ('boquv', "Boquv filiali"),
        ('ona_tovuq', "Ona tovuq"),
        ('inkubatoriya', "Inkubatoriya"),
        ('soyish', "So'yish va qadoqlash"),
        ('yem_zavodi', "Yem zavodi"),
        ('qishloq_xojaligi', "Qishloq xo'jaligi"),
    ], string="Sektor / Bo'lim", readonly=True)

    sana = fields.Date("Sana", readonly=True)
    filial_id = fields.Many2one('agronova.boquv.filial', string="Filial / Obyekt", readonly=True)
    bino_id = fields.Many2one('agronova.boquv.bino', string="Bino / Seh", readonly=True)
    company_id = fields.Many2one('res.company', string="Kompaniya", readonly=True)

    # -------------------------------------------------------------------------
    # SAMARADORLIK METRIKALARI (KPI)
    # -------------------------------------------------------------------------
    boshlangich_soni = fields.Float("Boshlang'ich miqdor / Bosh soni", readonly=True)
    yakuniy_soni = fields.Float("Yakuniy miqdor / Tirik bosh", readonly=True)
    chiqim_miqdori = fields.Float("Chiqim / Mahsulot miqdori (kg/dona)", readonly=True)

    nobud_soni = fields.Float("Nobudgarchilik / Yo'qotish (bosh/kg)", readonly=True)
    nobud_foiz = fields.Float("Nobudgarchilik (%)", readonly=True, aggregator='avg', digits=(12, 2))
    nobud_norma = fields.Float("Nobud normativ (%)", readonly=True, aggregator='avg', digits=(12, 2))
    nobud_ogish = fields.Float("Nobud og'ishi (p.p.)", readonly=True, aggregator='avg', digits=(12, 2))

    fcr_fakt = fields.Float("FCR (Ozuqa konversiyasi)", readonly=True, aggregator='avg', digits=(12, 3))
    fcr_norma = fields.Float("FCR normativ", readonly=True, aggregator='avg', digits=(12, 3))
    fcr_ogish = fields.Float("FCR og'ishi (+/-)", readonly=True, aggregator='avg', digits=(12, 3))

    ortacha_vazn_kg = fields.Float("O'rtacha vazn (kg)", readonly=True, aggregator='avg', digits=(12, 3))
    epef_indeks = fields.Float("EPEF Samaradorlik indeksi", readonly=True, aggregator='avg', digits=(12, 1))
    chiqim_foiz = fields.Float("Chiqim koeffitsienti (%)", readonly=True, aggregator='avg', digits=(12, 2))

    # -------------------------------------------------------------------------
    # TANNARX VA XARAJAT
    # -------------------------------------------------------------------------
    jami_xarajat = fields.Monetary("Jami xarajat (so'm)", readonly=True, currency_field='currency_id')
    birlik_tannarx = fields.Monetary("1 birlik / 1 kg tannarxi (so'm)", readonly=True, aggregator='avg', currency_field='currency_id')
    reja_birlik_tannarx = fields.Monetary("Reja 1 birlik tannarxi (so'm)", readonly=True, aggregator='avg', currency_field='currency_id')
    tannarx_ogish_foiz = fields.Float("Tannarx og'ishi (%)", readonly=True, aggregator='avg', digits=(12, 2))

    currency_id = fields.Many2one('res.currency', string="Valyuta", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                -- 1. BOQUV PARTIYALARI
                SELECT
                    p.id AS id,
                    p.name AS name,
                    'boquv'::varchar AS sektor,
                    COALESCE(p.ochilish_sana, CURRENT_DATE) AS sana,
                    p.filial_id AS filial_id,
                    p.bino_id AS bino_id,
                    p.company_id AS company_id,
                    p.boshlangich_son::numeric AS boshlangich_soni,
                    p.joriy_son::numeric AS yakuniy_soni,
                    p.jami_tirik_vazn::numeric AS chiqim_miqdori,
                    p.nobud_son::numeric AS nobud_soni,
                    p.nobud_foiz::numeric AS nobud_foiz,
                    3.5::numeric AS nobud_norma,
                    (COALESCE(p.nobud_foiz, 0) - 3.5)::numeric AS nobud_ogish,
                    p.fcr::numeric AS fcr_fakt,
                    1.60::numeric AS fcr_norma,
                    (COALESCE(p.fcr, 0) - 1.60)::numeric AS fcr_ogish,
                    p.ortacha_vazn::numeric AS ortacha_vazn_kg,
                    p.epef::numeric AS epef_indeks,
                    p.yashovchanlik::numeric AS chiqim_foiz,
                    (COALESCE(p.tannarx_1_kg, 0) * COALESCE(p.jami_tirik_vazn, 0))::numeric AS jami_xarajat,
                    p.tannarx_1_kg::numeric AS birlik_tannarx,
                    12000.0::numeric AS reja_birlik_tannarx,
                    CASE WHEN p.tannarx_1_kg > 0 AND 12000 > 0
                         THEN ((p.tannarx_1_kg - 12000.0) / 12000.0 * 100)::numeric
                         ELSE 0 END AS tannarx_ogish_foiz,
                    c.currency_id AS currency_id
                FROM agronova_boquv_partiya p
                LEFT JOIN res_company c ON p.company_id = c.id

                UNION ALL

                -- 2. YEM ZAVODI ISHLAB CHIQARISH
                SELECT
                    (1000000 + m.id) AS id,
                    m.name AS name,
                    'yem_zavodi'::varchar AS sektor,
                    COALESCE(m.date_start::date, CURRENT_DATE) AS sana,
                    NULL::integer AS filial_id,
                    NULL::integer AS bino_id,
                    m.company_id AS company_id,
                    m.product_qty::numeric AS boshlangich_soni,
                    COALESCE(m.qty_producing, m.product_qty)::numeric AS yakuniy_soni,
                    COALESCE(m.agronova_miqdor_kg, m.product_qty)::numeric AS chiqim_miqdori,
                    0::numeric AS nobud_soni,
                    0::numeric AS nobud_foiz,
                    0::numeric AS nobud_norma,
                    0::numeric AS nobud_ogish,
                    0::numeric AS fcr_fakt,
                    0::numeric AS fcr_norma,
                    0::numeric AS fcr_ogish,
                    0::numeric AS ortacha_vazn_kg,
                    0::numeric AS epef_indeks,
                    100.0::numeric AS chiqim_foiz,
                    COALESCE(m.agronova_jami_tannarx, 0)::numeric AS jami_xarajat,
                    COALESCE(m.agronova_tannarx_1_kg, 0)::numeric AS birlik_tannarx,
                    COALESCE(m.agronova_reja_tannarx_1_kg, 0)::numeric AS reja_birlik_tannarx,
                    COALESCE(m.agronova_chetlanish, 0)::numeric AS tannarx_ogish_foiz,
                    c.currency_id AS currency_id
                FROM mrp_production m
                LEFT JOIN res_company c ON m.company_id = c.id
                WHERE m.state = 'done'
            )
        """ % self._table)
