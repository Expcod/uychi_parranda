# -*- coding: utf-8 -*-
"""So'yish bo'limining foyda-zarar hisoboti.

Tuzilma `agronova.pl.mixin` da. So'yishga xos manbalar:

* analitik hisoblar — so'yish partiyalari;
* **ichki sotuv yo'q** — So'yish zanjirning oxirgi bo'g'ini, mahsulotini
  tashqariga sotadi. Daromadning ikki manbasi bor: go'shtning tashqi
  sotuvi va tashqi mijozdan olingan **so'yish xizmati haqi**. Xizmat
  partiyaga musbat analitik qator bo'lib yozilgani uchun hisobotda
  «Boshqa daromad» satrida chiqadi;
* ishlab chiqarish ko'rsatkichi — tirik vazn, tayyor mahsulot, chiqim
  foizi va 1 kg tannarxi.

Chiqim foizi bu bo'limning asosiy KPI si (TZ 6-band, norma ~74%):
tirik vazndan qancha foiz tayyor mahsulot chiqqani.
"""
from odoo import _, fields, models


class AgroNovaSoyishPl(models.TransientModel):
    _name = 'agronova.soyish.pl'
    _description = "So'yish — bo'lim foyda-zarari"
    _inherit = ['agronova.pl.mixin']

    qator_ids = fields.One2many(
        'agronova.soyish.pl.qator', 'pl_id', string="Xarajat tarkibi")

    # --- So'yishga xos ko'rsatkichlar
    tirik_vazn_kg = fields.Float("Qabul qilingan tirik vazn (kg)",
                                 compute='_compute_pl', digits='Product Unit')
    tayyor_kg = fields.Float("Tayyor mahsulot (kg)", compute='_compute_pl',
                             digits='Product Unit')
    chiqim_foiz = fields.Float("Chiqim foizi (%)", compute='_compute_pl')
    tannarx_1_kg = fields.Monetary("1 kg tannarxi", compute='_compute_pl')
    xizmat_summa = fields.Monetary("Tashqi mijoz xizmati",
                                   compute='_compute_pl')

    # ------------------------------------------------------------- ilgaklar
    def _pl_nom(self):
        return _("So'yish — foyda va zarar")

    def _pl_qator_model(self):
        return 'agronova.soyish.pl.qator'

    def _pl_view_xmlid(self):
        return 'agronova_soyish.view_soyish_pl_form'

    def _pl_company(self):
        """Qabul hujjatlari qaysi korxonada bo'lsa — bo'lim ham o'sha yerda."""
        qabul = self.env['agronova.soyish.qabul'].sudo().search([], limit=1)
        return qabul.company_id or self.env.company

    def _pl_analytic_accounts(self):
        self.ensure_one()
        return (self.env['agronova.soyish.partiya']
                .search([('company_id', '=', self.company_id.id)])
                .mapped('analytic_account_id'))

    def _pl_korsatkichlar(self):
        self.ensure_one()
        jarayonlar = self.env['agronova.soyish.jarayon'].sudo().search([
            ('company_id', '=', self.company_id.id),
            ('holat', '=', 'done'),
            ('sana', '>=', self.davr_boshi),
            ('sana', '<=', self.davr_oxiri),
        ])
        self.tayyor_kg = sum(jarayonlar.mapped('tushka_vazn_kg'))

        # Qabulda sana `Datetime` — kun oxirigacha olmasak davrning
        # oxirgi kunidagi hujjatlar tushib qoladi.
        qabullar = self.env['agronova.soyish.qabul'].sudo().search([
            ('company_id', '=', self.company_id.id),
            ('holat', '=', 'done'),
            ('sana', '>=', fields.Datetime.to_datetime(self.davr_boshi)),
            ('sana', '<=', fields.Datetime.to_datetime(
                self.davr_oxiri).replace(hour=23, minute=59, second=59)),
        ])
        self.tirik_vazn_kg = sum(qabullar.mapped('netto_kg'))
        self.chiqim_foiz = (self.tayyor_kg / self.tirik_vazn_kg * 100.0
                            if self.tirik_vazn_kg else 0.0)
        self.tannarx_1_kg = (self.ishlab_chiqarish / self.tayyor_kg
                             if self.tayyor_kg else 0.0)

        xizmatlar = self.env['agronova.soyish.xizmat'].sudo().search([
            ('company_id', '=', self.company_id.id),
            ('holat', '=', 'done'),
            ('sana', '>=', self.davr_boshi),
            ('sana', '<=', self.davr_oxiri),
        ])
        self.xizmat_summa = sum(xizmatlar.mapped('xizmat_summa'))


class AgroNovaSoyishPlQator(models.TransientModel):
    _name = 'agronova.soyish.pl.qator'
    _description = "So'yish — foyda-zarar hisoboti qatori"
    _inherit = ['agronova.pl.qator.mixin']

    pl_id = fields.Many2one('agronova.soyish.pl', string="Hisobot",
                            ondelete='cascade')
    currency_id = fields.Many2one(related='pl_id.currency_id', readonly=True)
