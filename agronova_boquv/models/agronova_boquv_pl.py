# -*- coding: utf-8 -*-
"""Boquv bo'limining foyda-zarar hisoboti.

Tuzilma `agronova.pl.mixin` da — barcha bo'limlar uchun yagona standart.
Bu yerda Boquv bo'limiga xos manbalar:

* analitik hisoblar — boquv partiyalari, binolari va filiallari;
* ichki sotuv — So'yish filialiga jo'natilgan tirik tovuqlar (`agronova.boquv.jonatma`);
* ishlab chiqarish ko'rsatkichlari — boqilayotgan bosh soni, tirik va nobud soni,
  nobudgarchilik %, yem sarfi (kg), o'rtacha FCR, EPEF, 1 bosh va 1 kg tannarxi.

Hisobot bo'lim natijasida ichki sotuvni daromad deb hisoblaydi va rentabellikni
aniqlaydi (TZ 19, 20-bandlar).
"""
from odoo import _, fields, models


class AgroNovaBoquvPl(models.TransientModel):
    _name = 'agronova.boquv.pl'
    _description = "Boquv — bo'lim foyda-zarari"
    _inherit = ['agronova.pl.mixin']

    qator_ids = fields.One2many(
        'agronova.boquv.pl.qator', 'pl_id', string="Xarajat tarkibi")

    # --- Boquvga xos zooveterinariya ko'rsatkichlari (TZ 20-band)
    jami_bosh = fields.Integer(
        "Jami boqilgan jo'jalar (bosh)", compute='_compute_pl')
    tirik_bosh = fields.Integer(
        "Hozirgi tirik jo'jalar (bosh)", compute='_compute_pl')
    nobud_bosh = fields.Integer(
        "Nobud bo'lgan (bosh)", compute='_compute_pl')
    nobud_foiz = fields.Float(
        "Nobudgarchilik (%)", compute='_compute_pl', digits=(12, 2))
    yem_sarf_kg = fields.Float(
        "Jami yem sarfi (kg)", compute='_compute_pl', digits='Product Unit')
    ortacha_fcr = fields.Float(
        "O'rtacha FCR", compute='_compute_pl', digits=(12, 3))
    ortacha_epef = fields.Float(
        "O'rtacha EPEF", compute='_compute_pl', digits=(12, 1))
    tannarx_1_bosh = fields.Monetary(
        "1 bosh o'rtacha tannarxi", compute='_compute_pl')
    tannarx_1_kg = fields.Monetary(
        "1 kg tirik vazn tannarxi", compute='_compute_pl')
    faol_partiya_soni = fields.Integer(
        "Faol partiyalar soni", compute='_compute_pl')
    soyilgan_bosh = fields.Integer(
        "So'yishga jo'natilgan (bosh)", compute='_compute_pl')
    soyilgan_kg = fields.Float(
        "So'yishga jo'natilgan (kg)", compute='_compute_pl', digits='Product Unit')

    # ------------------------------------------------------------- ilgaklar
    def _pl_nom(self):
        return _("Boquv — foyda va zarar")

    def _pl_qator_model(self):
        return 'agronova.boquv.pl.qator'

    def _pl_view_xmlid(self):
        return 'agronova_boquv.view_boquv_pl_form'

    def _pl_company(self):
        """Filiallar qaysi korxonada bo'lsa — hisobot ham o'sha korxonani ko'rsatadi."""
        filial = self.env['agronova.boquv.filial'].sudo().search([], limit=1)
        return filial.company_id or self.env.company

    def _pl_analytic_accounts(self):
        self.ensure_one()
        Partiya = self.env['agronova.boquv.partiya']
        Bino = self.env['agronova.boquv.bino']
        Filial = self.env['agronova.boquv.filial']
        return (
            Partiya.search([('company_id', '=', self.company_id.id)]).mapped('analytic_account_id')
            | Bino.search([('company_id', '=', self.company_id.id)]).mapped('analytic_account_id')
            | Filial.search([('company_id', '=', self.company_id.id)]).mapped('analytic_account_id')
        )

    def _pl_ichki_sotuv(self):
        self.ensure_one()
        jonatmalar = self.env['agronova.boquv.jonatma'].sudo().search([
            ('company_id', '=', self.company_id.id),
            ('holat', '=', 'done'),
            ('tur', '=', 'soyish'),
            ('sana', '>=', self.davr_boshi),
            ('sana', '<=', self.davr_oxiri),
        ])
        return super()._pl_ichki_sotuv() + sum(jonatmalar.mapped('summa'))

    def _pl_korsatkichlar(self):
        self.ensure_one()
        partiyalar = self.env['agronova.boquv.partiya'].sudo().search([
            ('company_id', '=', self.company_id.id),
            ('ochilish_sana', '<=', self.davr_oxiri),
            '|', ('yopilish_sana', '=', False),
                 ('yopilish_sana', '>=', self.davr_boshi),
            ('holat', 'not in', ('draft', 'cancel')),
        ])
        self.faol_partiya_soni = len(partiyalar.filtered(lambda p: p.holat == 'active'))
        self.jami_bosh = sum(partiyalar.mapped('boshlangich_son'))
        self.tirik_bosh = sum(partiyalar.mapped('joriy_son'))
        self.nobud_bosh = sum(partiyalar.mapped('nobud_son'))
        self.nobud_foiz = (self.nobud_bosh / self.jami_bosh * 100.0) if self.jami_bosh else 0.0

        jurnallar = self.env['agronova.boquv.jurnal'].sudo().search([
            ('company_id', '=', self.company_id.id),
            ('holat', '=', 'posted'),
            ('sana', '>=', self.davr_boshi),
            ('sana', '<=', self.davr_oxiri),
        ])
        self.yem_sarf_kg = sum(jurnallar.mapped('yem_kg'))

        jonatmalar = self.env['agronova.boquv.jonatma'].sudo().search([
            ('company_id', '=', self.company_id.id),
            ('holat', '=', 'done'),
            ('tur', '=', 'soyish'),
            ('sana', '>=', self.davr_boshi),
            ('sana', '<=', self.davr_oxiri),
        ])
        self.soyilgan_bosh = sum(jonatmalar.mapped(lambda j: j.qabul_bosh_soni or j.bosh_soni))
        self.soyilgan_kg = sum(jonatmalar.mapped(lambda j: j.qabul_vazn or j.jonatilgan_vazn))

        tirik_vazn_jami = sum(partiyalar.mapped('jami_tirik_vazn')) + self.soyilgan_kg
        self.ortacha_fcr = (self.yem_sarf_kg / tirik_vazn_jami) if tirik_vazn_jami else 0.0

        faol_epef = [p.epef for p in partiyalar if p.epef]
        self.ortacha_epef = (sum(faol_epef) / len(faol_epef)) if faol_epef else 0.0

        self.tannarx_1_bosh = (self.ishlab_chiqarish / self.jami_bosh) if self.jami_bosh else 0.0
        self.tannarx_1_kg = (self.ishlab_chiqarish / tirik_vazn_jami) if tirik_vazn_jami else 0.0


class AgroNovaBoquvPlQator(models.TransientModel):
    _name = 'agronova.boquv.pl.qator'
    _description = "Boquv — foyda-zarar hisoboti qatori"
    _inherit = ['agronova.pl.qator.mixin']

    pl_id = fields.Many2one('agronova.boquv.pl', string="Hisobot", ondelete='cascade')
    currency_id = fields.Many2one(related='pl_id.currency_id', readonly=True)

