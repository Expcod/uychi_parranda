# -*- coding: utf-8 -*-
"""Ona tovuqning ichki marja elminatsiyasi — B12.

Butun mexanizm `agronova.elminatsiya.mixin` da — u bo'limlar uchun umumiy.
Bu yerda faqat Ona tovuqqa xos qism: qaysi ichki sotuv modeli yig'iladi,
hujjat raqami qaysi ketma-ketlikdan olinadi va analitik qatorda qaysi tur
ko'rsatiladi.
"""
from odoo import _, fields, models

from .agronova_ona_tovuq_ichki_sotuv import TUR


class AgroNovaOnaTovuqElminatsiya(models.Model):
    _name = 'agronova.ona_tovuq.elminatsiya'
    _description = "Ona tovuq — ichki marja elminatsiyasi"
    _inherit = ['agronova.elminatsiya.mixin']

    qator_ids = fields.One2many(
        'agronova.ona_tovuq.elminatsiya.qator', 'elminatsiya_id',
        string="Qatorlar", copy=False)

    # ------------------------------------------------------------- ilgaklar
    def _elm_ichki_sotuv_model(self):
        return 'agronova.ona_tovuq.ichki_sotuv'

    def _elm_sequence(self):
        return 'agronova.ona_tovuq.elminatsiya'

    def _elm_hisob_nomi(self):
        return _("Elminatsiya — Ona tovuq")

    def _elm_plan_xmlid(self):
        return 'agronova_ona_tovuq.analytic_plan_konsolidatsiya'

    def _elm_qator_matni(self, q):
        return _("Elminatsiya: %(hujjat)s — %(tur)s (%(miqdor)s / %(jami)s)",
                 hujjat=q.ichki_sotuv_id.name,
                 tur=dict(TUR).get(q.tur, ''),
                 miqdor=q.qolgan_miqdor, jami=q.miqdor)


class AgroNovaOnaTovuqElminatsiyaQator(models.Model):
    _name = 'agronova.ona_tovuq.elminatsiya.qator'
    _description = "Ona tovuq — elminatsiya qatori"
    _inherit = ['agronova.elminatsiya.qator.mixin']

    elminatsiya_id = fields.Many2one(
        'agronova.ona_tovuq.elminatsiya', string="Hujjat", required=True,
        ondelete='cascade', index=True)
    company_id = fields.Many2one(
        related='elminatsiya_id.company_id', store=True, readonly=True)
    currency_id = fields.Many2one(
        related='elminatsiya_id.currency_id', readonly=True)

    ichki_sotuv_id = fields.Many2one(
        'agronova.ona_tovuq.ichki_sotuv', string="Ichki sotuv", required=True,
        ondelete='restrict', index=True)
    tur = fields.Selection(
        related='ichki_sotuv_id.tur', string="Turi", store=True, readonly=True)
    date = fields.Date(
        related='ichki_sotuv_id.date', string="Sana", store=True, readonly=True)
    partiya_id = fields.Many2one(
        related='ichki_sotuv_id.partiya_id', string="Partiya", store=True,
        readonly=True)

    miqdor = fields.Integer(
        related='ichki_sotuv_id.dona', string="Berilgan miqdor", store=True,
        readonly=True)
    summa = fields.Monetary(
        related='ichki_sotuv_id.summa', string="Ichki sotuv summasi",
        store=True, readonly=True)
    tannarx_summa = fields.Monetary(
        related='ichki_sotuv_id.tannarx_summa', string="Tannarx", store=True,
        readonly=True)
    ichki_marja = fields.Monetary(
        related='ichki_sotuv_id.ichki_foyda', string="Ichki marja", store=True,
        readonly=True)
