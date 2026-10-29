# -*- coding: utf-8 -*-
"""A ilovasi — Boquv partiyasi tannarxi hisobi (Batch Cost & Variance Report).

TT 7.1 va A ilovasidagi rasmiy hisobot shakli:
1 bosh va 1 kg tirik vazn tannarxini xarajat turlari kesimida (Yem 74.5%, Jo'ja 16.4%,
Kommunal 3.0%, Ish haqi 2.5%, Veterinariya 2.0%, Amortizatsiya 1.6%) va normativdan og'ishlar
(FCR og'ishi, nobudgarchilik og'ishi) bilan avtomat taqdim etadi.
"""
from odoo import api, fields, models


class AgroNovaBatchCostReport(models.Model):
    _name = 'agronova.batch.cost.report'
    _description = "A Ilovasi: Partiya Tannarxi Hisoboti"
    _order = 'partiya_id desc'

    partiya_id = fields.Many2one('agronova.boquv.partiya', string="Boquv Partiyasi", required=True, ondelete='cascade')
    name = fields.Char(related='partiya_id.name', string="Partiya kodi", readonly=True)
    filial_id = fields.Many2one(related='partiya_id.filial_id', string="Filial", readonly=True, store=True)
    bino_id = fields.Many2one(related='partiya_id.bino_id', string="Bino / Seh", readonly=True, store=True)
    davr_kun = fields.Integer(related='partiya_id.yosh_kun', string="Davri (kun)", readonly=True)

    # -------------------------------------------------------------------------
    # BOSH SONI VA VAZN
    # -------------------------------------------------------------------------
    boshlangich_son = fields.Integer(related='partiya_id.boshlangich_son', string="Boshlang'ich bosh soni", readonly=True)
    nobud_son = fields.Integer(related='partiya_id.nobud_son', string="Nobudgarchilik (bosh)", readonly=True)
    nobud_foiz = fields.Float(related='partiya_id.nobud_foiz', string="Nobudgarchilik (%)", readonly=True, digits=(12, 2))
    yakuniy_son = fields.Integer(related='partiya_id.joriy_son', string="Yakuniy bosh soni", readonly=True)
    ortacha_vazn = fields.Float(related='partiya_id.ortacha_vazn', string="O'rtacha vazn (kg)", readonly=True, digits=(12, 3))
    jami_tirik_vazn = fields.Float(related='partiya_id.jami_tirik_vazn', string="Jami tirik vazn (kg)", readonly=True, digits=(12, 2))
    yem_sarfi_kg = fields.Float("Jami yem sarfi (kg)", compute='_compute_xarajat_tuzilishi', digits=(12, 2))
    fcr = fields.Float(related='partiya_id.fcr', string="FCR (fakt)", readonly=True, digits=(12, 3))

    # -------------------------------------------------------------------------
    # XARAJATLAR TUZILISHI (Summa va Ulush %)
    # -------------------------------------------------------------------------
    yem_xarajat = fields.Monetary("1. Yem sarfi (so'm)", compute='_compute_xarajat_tuzilishi')
    yem_ulush = fields.Float("Yem ulushi (%)", compute='_compute_xarajat_tuzilishi', digits=(12, 2))

    joja_xarajat = fields.Monetary("2. Jo'ja (boshlang'ich mol) (so'm)", compute='_compute_xarajat_tuzilishi')
    joja_ulush = fields.Float("Jo'ja ulushi (%)", compute='_compute_xarajat_tuzilishi', digits=(12, 2))

    kommunal_xarajat = fields.Monetary("3. Kommunal xarajatlar (gaz, elektr, suv)", compute='_compute_xarajat_tuzilishi')
    kommunal_ulush = fields.Float("Kommunal ulushi (%)", compute='_compute_xarajat_tuzilishi', digits=(12, 2))

    ish_haqi_xarajat = fields.Monetary("4. Ish haqi xarajatlari", compute='_compute_xarajat_tuzilishi')
    ish_haqi_ulush = fields.Float("Ish haqi ulushi (%)", compute='_compute_xarajat_tuzilishi', digits=(12, 2))

    vet_dori_xarajat = fields.Monetary("5. Veterinariya va dori-darmon", compute='_compute_xarajat_tuzilishi')
    vet_dori_ulush = fields.Float("Veterinariya ulushi (%)", compute='_compute_xarajat_tuzilishi', digits=(12, 2))

    amortizatsiya_boshqa_xarajat = fields.Monetary("6. Amortizatsiya va boshqa xarajatlar", compute='_compute_xarajat_tuzilishi')
    amortizatsiya_ulush = fields.Float("Amortizatsiya ulushi (%)", compute='_compute_xarajat_tuzilishi', digits=(12, 2))

    jami_xarajat = fields.Monetary("JAMI XARAJAT", compute='_compute_xarajat_tuzilishi')

    # -------------------------------------------------------------------------
    # YAKUNIY KO'RSATKICHLAR VA OG'ISHLAR
    # -------------------------------------------------------------------------
    bir_bosh_tannarx = fields.Monetary(related='partiya_id.tannarx_1_bosh', string="1 bosh tannarxi (so'm)", readonly=True)
    bir_kg_tannarx = fields.Monetary(related='partiya_id.tannarx_1_kg', string="1 kg tirik vazn tannarxi (so'm)", readonly=True)

    normativ_fcr = fields.Float("Normativ FCR", default=1.60, digits=(12, 3))
    fcr_ogish = fields.Float("FCR og'ishi (+/-)", compute='_compute_ogishlar', digits=(12, 3))

    normativ_nobud = fields.Float("Normativ nobudgarchilik (%)", default=3.5, digits=(12, 2))
    nobud_ogish = fields.Float("Nobudgarchilik og'ishi (+/- p.p.)", compute='_compute_ogishlar', digits=(12, 2))

    currency_id = fields.Many2one('res.currency', string="Valyuta", default=lambda self: self.env.company.currency_id)

    @api.depends('partiya_id')
    def _compute_xarajat_tuzilishi(self):
        for rec in self:
            p = rec.partiya_id
            if not p:
                rec.yem_xarajat = 0.0
                rec.yem_ulush = 0.0
                rec.joja_xarajat = 0.0
                rec.joja_ulush = 0.0
                rec.kommunal_xarajat = 0.0
                rec.kommunal_ulush = 0.0
                rec.ish_haqi_xarajat = 0.0
                rec.ish_haqi_ulush = 0.0
                rec.vet_dori_xarajat = 0.0
                rec.vet_dori_ulush = 0.0
                rec.amortizatsiya_boshqa_xarajat = 0.0
                rec.amortizatsiya_ulush = 0.0
                rec.jami_xarajat = 0.0
                rec.yem_sarfi_kg = 0.0
                continue

            total = p.jami_xarajat or 0.0
            rec.jami_xarajat = total

            # Partiyaga tegishli analitik yozuvlar bo'yicha taqsimlash
            lines = self.env['account.analytic.line'].sudo().search([
                ('account_id', '=', p.analytic_account_id.id)
            ]) if hasattr(p, 'analytic_account_id') and p.analytic_account_id else []

            yem = 0.0
            joja = 0.0
            kommunal = 0.0
            ish_haqi = 0.0
            vet = 0.0
            boshqa = 0.0

            for l in lines:
                amt = abs(l.amount)
                lname = (l.name or '').lower()
                if 'yem' in lname:
                    yem += amt
                elif 'joja' in lname or "jo'ja" in lname:
                    joja += amt
                elif any(k in lname for k in ['gaz', 'elektr', 'suv', 'kommunal']):
                    kommunal += amt
                elif any(k in lname for k in ['ish haqi', 'oylik', 'ishchi']):
                    ish_haqi += amt
                elif any(k in lname for k in ['dori', 'vaksina', 'vet']):
                    vet += amt
                else:
                    boshqa += amt

            # Agar analitik yozuvlar hali to'liq bo'lmasa, TT dagi standart normativ ulushlar asosida baholanadi
            if total > 0 and (yem + joja + kommunal + ish_haqi + vet + boshqa) == 0:
                yem = total * 0.745
                joja = total * 0.164
                kommunal = total * 0.030
                ish_haqi = total * 0.025
                vet = total * 0.020
                boshqa = total * 0.016

            rec.yem_xarajat = yem
            rec.joja_xarajat = joja
            rec.kommunal_xarajat = kommunal
            rec.ish_haqi_xarajat = ish_haqi
            rec.vet_dori_xarajat = vet
            rec.amortizatsiya_boshqa_xarajat = boshqa

            rec.yem_ulush = (yem / total * 100) if total > 0 else 74.5
            rec.joja_ulush = (joja / total * 100) if total > 0 else 16.4
            rec.kommunal_ulush = (kommunal / total * 100) if total > 0 else 3.0
            rec.ish_haqi_ulush = (ish_haqi / total * 100) if total > 0 else 2.5
            rec.vet_dori_ulush = (vet / total * 100) if total > 0 else 2.0
            rec.amortizatsiya_ulush = (boshqa / total * 100) if total > 0 else 1.6

            # Yem sarfi partiyada kunlik jurnaldan allaqachon kg da jamlangan
            # (`yem_sarf_kg`). Jurnal hali bo'sh bo'lsa — FCR orqali baholanadi.
            rec.yem_sarfi_kg = p.yem_sarf_kg or ((p.jami_tirik_vazn or 0.0) * (p.fcr or 1.65))

    @api.depends('fcr', 'normativ_fcr', 'nobud_foiz', 'normativ_nobud')
    def _compute_ogishlar(self):
        for rec in self:
            rec.fcr_ogish = (rec.fcr or 0.0) - (rec.normativ_fcr or 1.60)
            rec.nobud_ogish = (rec.nobud_foiz or 0.0) - (rec.normativ_nobud or 3.5)
