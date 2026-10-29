# -*- coding: utf-8 -*-
"""B ilovasi — Yem tannarxida ijara ulushi va to'liq tannarx hisoboti (Feed Cost & Rent Allocation).

TT 7.1 va B ilovasidagi talablar:
Zavod hududi ijarasi: oyiga 18 000 USD. Ijara to'g'ridan-to'g'ri davr xarajatiga emas,
ishlab chiqarilgan yem tannarxiga ish kunlari (26 kun) va ishlab chiqarish tonnajiga qarab taqsimlanadi.
1 kg yemning to'liq tannarxini (xomashyo, qayta ishlash, ijara, kommunal, ish haqi, amortizatsiya) taqdim etadi.
"""
from odoo import api, fields, models


class AgroNovaFeedCostReport(models.Model):
    _name = 'agronova.feed.cost.report'
    _description = "B Ilovasi: Yem Tannarxi va Ijara Taqsimoti Hisoboti"
    _order = 'davr desc'

    name = fields.Char("Hisobot nomi", required=True)
    davr = fields.Date("Hisobot oyi / davri", default=fields.Date.context_today)

    # -------------------------------------------------------------------------
    # IJARA VA ISH KUNLARI PARAMETRLARI
    # -------------------------------------------------------------------------
    ijara_usd = fields.Float("Oylik ijara (USD)", default=18000.0, digits=(16, 2))
    valyuta_kursi = fields.Float("Valyuta kursi (so'm)", default=12800.0, digits=(12, 2))
    ijara_som = fields.Monetary("Oylik ijara (so'm)", compute='_compute_ijara_hisobi', store=True)

    ish_kunlari = fields.Integer("Oylik ish kunlari soni", default=26)
    bir_kunlik_ijara_som = fields.Monetary("Bir kunlik ijara (so'm)", compute='_compute_ijara_hisobi', store=True)

    oylik_ishlab_chiqarish_tonna = fields.Float("Oylik ishlab chiqarish (tonna)", default=1300.0, digits=(12, 2))
    bir_kg_ijara_som = fields.Float("1 kg yemga ijara ulushi (so'm)", compute='_compute_ijara_hisobi', store=True, digits=(12, 2))

    # -------------------------------------------------------------------------
    # 1 KG YEMNING TO'LIQ TANNARX TARKIBI
    # -------------------------------------------------------------------------
    xomashyo_qiymat_kg = fields.Monetary("1. Xomashyo qiymati (BOM / FIFO)", default=3200.0)
    qayta_ishlash_xarajat_kg = fields.Monetary("2. Qayta ishlash xarajati (ish markazi)", default=250.0)
    ijara_ulushi_kg = fields.Monetary("3. Ijara ulushi", compute='_compute_tannarx_tarkibi', store=True)
    elektr_gaz_kg = fields.Monetary("4. Elektr va gaz", default=180.0)
    ish_haqi_kg = fields.Monetary("5. Ish haqi", default=150.0)
    amortizatsiya_kg = fields.Monetary("6. Amortizatsiya", default=80.0)

    bir_kg_toliq_tannarx = fields.Monetary("JAMI 1 KG YEM TANNARXI", compute='_compute_tannarx_tarkibi', store=True)
    bir_tonna_toliq_tannarx = fields.Monetary("JAMI 1 TONNA YEM TANNARXI", compute='_compute_tannarx_tarkibi', store=True)

    reja_1_kg_tannarx = fields.Monetary("Reja: 1 kg tannarxi", default=4000.0)
    ogish_som = fields.Monetary("Rejadan og'ish (so'm)", compute='_compute_tannarx_tarkibi', store=True)
    ogish_foiz = fields.Float("Rejadan og'ish (%)", compute='_compute_tannarx_tarkibi', store=True, digits=(12, 2))

    currency_id = fields.Many2one('res.currency', string="Valyuta", default=lambda self: self.env.company.currency_id)

    @api.depends('ijara_usd', 'valyuta_kursi', 'ish_kunlari', 'oylik_ishlab_chiqarish_tonna')
    def _compute_ijara_hisobi(self):
        for rec in self:
            som = (rec.ijara_usd or 0.0) * (rec.valyuta_kursi or 1.0)
            rec.ijara_som = som
            kunlar = rec.ish_kunlari or 26
            rec.bir_kunlik_ijara_som = som / kunlar if kunlar > 0 else 0.0
            tonna = rec.oylik_ishlab_chiqarish_tonna or 1300.0
            rec.bir_kg_ijara_som = (som / (tonna * 1000.0)) if tonna > 0 else 0.0

    @api.depends('xomashyo_qiymat_kg', 'qayta_ishlash_xarajat_kg', 'bir_kg_ijara_som',
                 'elektr_gaz_kg', 'ish_haqi_kg', 'amortizatsiya_kg', 'reja_1_kg_tannarx')
    def _compute_tannarx_tarkibi(self):
        for rec in self:
            rec.ijara_ulushi_kg = rec.bir_kg_ijara_som or 0.0
            jami_1_kg = (
                (rec.xomashyo_qiymat_kg or 0.0) +
                (rec.qayta_ishlash_xarajat_kg or 0.0) +
                (rec.ijara_ulushi_kg or 0.0) +
                (rec.elektr_gaz_kg or 0.0) +
                (rec.ish_haqi_kg or 0.0) +
                (rec.amortizatsiya_kg or 0.0)
            )
            rec.bir_kg_toliq_tannarx = jami_1_kg
            rec.bir_tonna_toliq_tannarx = jami_1_kg * 1000.0
            reja = rec.reja_1_kg_tannarx or 0.0
            rec.ogish_som = jami_1_kg - reja
            rec.ogish_foiz = ((jami_1_kg - reja) / reja * 100) if reja > 0 else 0.0
