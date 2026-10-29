# -*- coding: utf-8 -*-
"""Ona tovuq bo'limining foyda-zarar hisoboti — B12.

Tuzilma `agronova.pl.mixin` da — u uch bo'lim uchun umumiy. Bu yerda faqat
Ona tovuqqa xos manbalar:

* analitik hisoblar — o'stirish va tuxum partiyalari;
* ichki sotuv — Inkubatsiyaga tuxum, So'yishga eskirgan poda;
* elminatsiya — `agronova.ona_tovuq.elminatsiya` hujjatlaridan;
* ishlab chiqarish ko'rsatkichi — ishlab chiqarilgan tuxum va 1 dona
  tannarxi.

Hisobot **ikki qatlamni** yonma-yon ko'rsatadi (TZ 3-bo'lim): bo'lim
natijasida ichki sotuv tasdiqlangan narxda daromad hisoblanadi, korxona
natijasida esa realizatsiya qilinmagan marja chiqarib tashlanadi.
"""
from odoo import _, fields, models


class AgroNovaOnaTovuqPl(models.TransientModel):
    _name = 'agronova.ona_tovuq.pl'
    _description = "Ona tovuq — bo'lim foyda-zarari"
    _inherit = ['agronova.pl.mixin']

    qator_ids = fields.One2many(
        'agronova.ona_tovuq.pl.qator', 'pl_id', string="Xarajat tarkibi")

    # --- Ona tovuqqa xos ko'rsatkichlar
    jami_tuxum = fields.Integer("Ishlab chiqarilgan tuxum (dona)",
                                compute='_compute_pl')
    tannarx_1_dona = fields.Monetary("1 dona tuxum tannarxi",
                                     compute='_compute_pl')

    # ------------------------------------------------------------- ilgaklar
    def _pl_nom(self):
        return _("Ona tovuq — foyda va zarar")

    def _pl_qator_model(self):
        return 'agronova.ona_tovuq.pl.qator'

    def _pl_view_xmlid(self):
        return 'agronova_ona_tovuq.view_ot_pl_form'

    def _pl_company(self):
        """Sexlar qaysi korxonada bo'lsa, bo'lim ham o'sha yerda.

        Foydalanuvchining joriy korxonasiga bog'lanmaydi: hisobot Ona
        Tovuq ilovasi ichida turibdi, demak ochilishi bilan aynan shu
        bo'limning raqamlarini ko'rsatishi kerak.
        """
        sex = self.env['agronova.ona_tovuq.sex'].sudo().search([], limit=1)
        return sex.company_id or self.env.company

    def _pl_analytic_accounts(self):
        self.ensure_one()
        Tuxum = self.env['agronova.ona_tovuq.partiya.tuxum']
        Ostirish = self.env['agronova.ona_tovuq.partiya.ostirish']
        return (Tuxum.search([('company_id', '=', self.company_id.id)])
                .mapped('analytic_account_id')
                | Ostirish.search([('company_id', '=', self.company_id.id)])
                .mapped('analytic_account_id'))

    def _pl_ichki_sotuv(self):
        self.ensure_one()
        sotuvlar = self.env['agronova.ona_tovuq.ichki_sotuv'].sudo().search([
            ('company_id', '=', self.company_id.id),
            ('holat', '=', 'done'),
            ('date', '>=', self.davr_boshi),
            ('date', '<=', self.davr_oxiri),
        ])
        # Korxonalararo sotuv buyurtmalari ham hisobga olinadi.
        return super()._pl_ichki_sotuv() + sum(sotuvlar.mapped('summa'))

    def _pl_elminatsiya(self):
        self.ensure_one()
        docs = self.env['agronova.ona_tovuq.elminatsiya'].sudo().search([
            ('company_id', '=', self.company_id.id),
            ('holat', '=', 'posted'),
            ('davr_oxiri', '>=', self.davr_boshi),
            ('davr_oxiri', '<=', self.davr_oxiri),
        ])
        return sum(docs.mapped('jami_elminatsiya'))

    def _pl_korsatkichlar(self):
        self.ensure_one()
        jurnal = self.env['agronova.ona_tovuq.jurnal.tuxum'].sudo().search([
            ('company_id', '=', self.company_id.id),
            ('date', '>=', self.davr_boshi),
            ('date', '<=', self.davr_oxiri),
        ])
        self.jami_tuxum = sum(jurnal.mapped('jami_tuxum'))
        self.tannarx_1_dona = (self.ishlab_chiqarish / self.jami_tuxum
                               if self.jami_tuxum else 0.0)


class AgroNovaOnaTovuqPlQator(models.TransientModel):
    _name = 'agronova.ona_tovuq.pl.qator'
    _description = "Ona tovuq — foyda-zarar hisoboti qatori"
    _inherit = ['agronova.pl.qator.mixin']

    pl_id = fields.Many2one('agronova.ona_tovuq.pl', string="Hisobot",
                            ondelete='cascade')
    currency_id = fields.Many2one(related='pl_id.currency_id', readonly=True)
