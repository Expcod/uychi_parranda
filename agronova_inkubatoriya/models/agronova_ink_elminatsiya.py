# -*- coding: utf-8 -*-
"""Inkubatoriyaning ichki marja elminatsiyasi.

Butun mexanizm `agronova.elminatsiya.mixin` da. Bu yerda faqat
Inkubatoriyaga xos qism.

Bu bo'limda elminatsiya ayniqsa muhim: jo'ja Boquvga berilganda 45 kun
davomida u yerda o'sadi, ya'ni ichki marja **uzoq vaqt realizatsiya
qilinmagan** bo'lib turadi. Elminatsiyasiz konsolidatsiyalangan foyda
ikki oy oldin yaratilgan «qog'ozdagi» marja bilan shishib ketardi.
"""
from odoo import _, fields, models


class AgroNovaInkElminatsiya(models.Model):
    _name = 'agronova.ink.elminatsiya'
    _description = "Inkubatoriya — ichki marja elminatsiyasi"
    _inherit = ['agronova.elminatsiya.mixin']

    qator_ids = fields.One2many(
        'agronova.ink.elminatsiya.qator', 'elminatsiya_id', string="Qatorlar",
        copy=False)

    # ------------------------------------------------------------- ilgaklar
    def _elm_ichki_sotuv_model(self):
        return 'agronova.ink.ichki_sotuv'

    def _elm_sequence(self):
        return 'agronova.ink.elminatsiya'

    def _elm_hisob_nomi(self):
        return _("Elminatsiya — Inkubatoriya")

    def _elm_qator_matni(self, q):
        return _("Elminatsiya: %(hujjat)s — jo'ja (%(miqdor)s / %(jami)s)",
                 hujjat=q.ichki_sotuv_id.name, miqdor=q.qolgan_miqdor,
                 jami=q.miqdor)


class AgroNovaInkElminatsiyaQator(models.Model):
    _name = 'agronova.ink.elminatsiya.qator'
    _description = "Inkubatoriya — elminatsiya qatori"
    _inherit = ['agronova.elminatsiya.qator.mixin']

    elminatsiya_id = fields.Many2one(
        'agronova.ink.elminatsiya', string="Hujjat", required=True,
        ondelete='cascade', index=True)
    company_id = fields.Many2one(
        related='elminatsiya_id.company_id', store=True, readonly=True)
    currency_id = fields.Many2one(
        related='elminatsiya_id.currency_id', readonly=True)

    ichki_sotuv_id = fields.Many2one(
        'agronova.ink.ichki_sotuv', string="Ichki sotuv", required=True,
        ondelete='restrict', index=True)
    date = fields.Date(
        related='ichki_sotuv_id.date', string="Sana", store=True, readonly=True)
    partiya_id = fields.Many2one(
        related='ichki_sotuv_id.partiya_id', string="Partiya", store=True,
        readonly=True)
    qabul_company_id = fields.Many2one(
        related='ichki_sotuv_id.qabul_company_id', string="Qabul qiluvchi",
        store=True, readonly=True)

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
        related='ichki_sotuv_id.marja', string="Ichki marja", store=True,
        readonly=True)
