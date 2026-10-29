# -*- coding: utf-8 -*-
"""Vazn nazorati — davriy tortish (TZ 13-band).

Belgilangan davrlarda jo'jalarning bir qismi tortiladi va o'rtacha, minimal,
maksimal vazn qayd etiladi. Partiyaning `ortacha_vazn` maydoni **oxirgi
tortishdan** olinadi, `jami_tirik_vazn` esa undan hisoblanadi:

    Jami tirik vazn = tirik jo'jalar soni × o'rtacha vazn

Bu ikki ko'rsatkich **1 kg tirik vazn tannarxi** (TZ 16-band) va **FCR**
uchun baza bo'ladi — shuning uchun tortish muntazam bo'lishi kerak.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AgroNovaBoquvVazn(models.Model):
    _name = 'agronova.boquv.vazn'
    _description = "Boquv — vazn nazorati"
    _inherit = ['mail.thread']
    _order = 'sana desc, id desc'

    name = fields.Char("Tortish", compute='_compute_name', store=True)
    sana = fields.Date(
        "Tortish sanasi", required=True, default=fields.Date.context_today,
        tracking=True, index=True)
    partiya_id = fields.Many2one(
        'agronova.boquv.partiya', string="Partiya", required=True, tracking=True,
        ondelete='cascade', index=True,
        domain="[('holat', '=', 'active')]")
    bino_id = fields.Many2one(
        related='partiya_id.bino_id', string="Bino", store=True, readonly=True)
    filial_id = fields.Many2one(
        related='partiya_id.filial_id', string="Filial", store=True, readonly=True)
    company_id = fields.Many2one(
        related='partiya_id.company_id', string="Korxona",
        store=True, readonly=True)

    yosh_kun = fields.Integer(
        "Yoshi (kun)", compute='_compute_yosh', store=True,
        help="Tortish kunidagi jo'ja yoshi — normativ bilan solishtirish uchun.")

    # --- o'lchov
    tortilgan_son = fields.Integer(
        "Tortilgan bosh soni", required=True, default=100,
        help="Namuna hajmi. Odatda podaning bir qismi tortiladi.")
    ortacha_vazn = fields.Float(
        "O'rtacha vazn (kg)", required=True, digits='Product Unit', tracking=True)
    min_vazn = fields.Float("Minimal vazn (kg)", digits='Product Unit')
    max_vazn = fields.Float("Maksimal vazn (kg)", digits='Product Unit')
    bir_xillik = fields.Float(
        "Bir xillik (%)", compute='_compute_bir_xillik', store=True,
        digits=(12, 2),
        help="(1 − (max − min) / o'rtacha) × 100. Yuqori qiymat — poda "
             "bir tekis o'sgan.")

    # --- partiya kesimi (o'sha kundagi holat)
    tirik_son = fields.Integer(
        "Tirik bosh soni", readonly=True,
        help="Tortish paytidagi partiya soni — avtomat.")
    jami_tirik_vazn = fields.Float(
        "Jami tirik vazn (kg)", compute='_compute_jami', store=True,
        digits='Product Unit',
        help="Tirik bosh soni × o'rtacha vazn (TZ 13-band).")

    # --- reja-fakt
    vazn_norma = fields.Float(
        "Normativ vazn (kg)", compute='_compute_norma', digits='Product Unit')
    vazn_ogish = fields.Float(
        "Og'ish (kg)", compute='_compute_norma', digits='Product Unit',
        help="Fakt − norma. Manfiy qiymat — o'sish normadan orqada.")

    mas_ul_id = fields.Many2one('hr.employee', string="Mas'ul xodim")
    izoh = fields.Text("Izoh")

    _vazn_musbat = models.Constraint(
        'CHECK (ortacha_vazn > 0)',
        "O'rtacha vazn noldan katta bo'lishi kerak.")
    _tortilgan_musbat = models.Constraint(
        'CHECK (tortilgan_son > 0)',
        "Tortilgan bosh soni noldan katta bo'lishi kerak.")
    _partiya_sana_uniq = models.Constraint(
        'UNIQUE(partiya_id, sana)',
        "Bu partiya uchun shu sanadagi tortish allaqachon qayd etilgan.")

    # ------------------------------------------------------------- compute
    @api.depends('partiya_id', 'sana')
    def _compute_name(self):
        for v in self:
            v.name = ("%s / %s" % (v.partiya_id.name, v.sana)
                      if v.partiya_id and v.sana else _("Yangi"))

    @api.depends('sana', 'partiya_id.joja_sana')
    def _compute_yosh(self):
        for v in self:
            joja = v.partiya_id.joja_sana
            v.yosh_kun = max((v.sana - joja).days, 0) if (joja and v.sana) else 0

    @api.depends('ortacha_vazn', 'min_vazn', 'max_vazn')
    def _compute_bir_xillik(self):
        for v in self:
            if v.ortacha_vazn and v.max_vazn and v.min_vazn:
                tarqoqlik = (v.max_vazn - v.min_vazn) / v.ortacha_vazn
                v.bir_xillik = max((1.0 - tarqoqlik) * 100.0, 0.0)
            else:
                v.bir_xillik = 0.0

    @api.depends('tirik_son', 'ortacha_vazn')
    def _compute_jami(self):
        for v in self:
            v.jami_tirik_vazn = v.tirik_son * v.ortacha_vazn

    @api.depends('ortacha_vazn', 'yosh_kun')
    def _compute_norma(self):
        Normativ = self.env['agronova.boquv.normativ']
        for v in self:
            norma = Normativ.qiymat('ortacha_vazn_norma', yosh_kun=v.yosh_kun)
            v.vazn_norma = norma
            v.vazn_ogish = (v.ortacha_vazn - norma) if norma else 0.0

    # ----------------------------------------------------------- validatsiya
    @api.constrains('min_vazn', 'max_vazn', 'ortacha_vazn')
    def _check_vaznlar(self):
        for v in self:
            if v.min_vazn and v.max_vazn and v.min_vazn > v.max_vazn:
                raise ValidationError(_(
                    "Minimal vazn maksimaldan katta bo'lmaydi («%s»).", v.name))
            if v.min_vazn and v.ortacha_vazn < v.min_vazn:
                raise ValidationError(_(
                    "O'rtacha vazn minimaldan kichik bo'lmaydi («%s»).", v.name))
            if v.max_vazn and v.ortacha_vazn > v.max_vazn:
                raise ValidationError(_(
                    "O'rtacha vazn maksimaldan katta bo'lmaydi («%s»).", v.name))

    @api.onchange('partiya_id')
    def _onchange_partiya(self):
        if self.partiya_id:
            self.tirik_son = self.partiya_id.joriy_son

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'tirik_son' not in vals and vals.get('partiya_id'):
                partiya = self.env['agronova.boquv.partiya'].browse(vals['partiya_id'])
                vals['tirik_son'] = partiya.joriy_son
        return super().create(vals_list)
