# -*- coding: utf-8 -*-
"""Inkubatoriya bo'limining foyda-zarar hisoboti.

Tuzilma `agronova.pl.mixin` da — u bo'limlar uchun umumiy. Bu yerda faqat
Inkubatoriyaga xos manbalar:

* analitik hisoblar — inkubatsiya partiyalari;
* ichki sotuv — Boquvga berilgan jo'ja;
* elminatsiya — `agronova.ink.elminatsiya` hujjatlaridan;
* ishlab chiqarish ko'rsatkichlari — qo'yilgan tuxum, ochilgan jo'ja,
  ochilish foizi va 1 dona jo'ja tannarxi.

**Ochilish foizi** bu bo'limning asosiy ko'rsatkichi (TZ 5-band): qo'yilgan
tuxumdan necha foizi jo'ja bo'lib chiqdi.
"""
from odoo import _, fields, models


class AgroNovaInkPl(models.TransientModel):
    _name = 'agronova.ink.pl'
    _description = "Inkubatoriya — bo'lim foyda-zarari"
    _inherit = ['agronova.pl.mixin']

    qator_ids = fields.One2many(
        'agronova.ink.pl.qator', 'pl_id', string="Xarajat tarkibi")

    # --- Inkubatoriyaga xos ko'rsatkichlar
    tuxum_dona = fields.Integer("Qo'yilgan tuxum (dona)", compute='_compute_pl')
    ochilgan_joja = fields.Integer("Ochilgan jo'ja (dona)",
                                   compute='_compute_pl')
    sof_joja = fields.Integer("Yaroqli jo'ja (dona)", compute='_compute_pl')
    ochilish_foiz = fields.Float("Ochilish foizi (%)", compute='_compute_pl')
    tannarx_1_joja = fields.Monetary("1 dona jo'ja tannarxi",
                                     compute='_compute_pl')

    # ------------------------------------------------------------- ilgaklar
    def _pl_nom(self):
        return _("Inkubatoriya — foyda va zarar")

    def _pl_qator_model(self):
        return 'agronova.ink.pl.qator'

    def _pl_view_xmlid(self):
        return 'agronova_inkubatoriya.view_ink_pl_form'

    def _pl_company(self):
        """Inkubatorlar qaysi korxonada bo'lsa — bo'lim ham o'sha yerda.

        Foydalanuvchining joriy korxonasiga bog'lanmaydi: hisobot
        Inkubatoriya ilovasi ichida turibdi, demak ochilishi bilan aynan
        shu bo'limning raqamlarini ko'rsatishi kerak.
        """
        ink = self.env['agronova.ink.inkubator'].sudo().search([], limit=1)
        if ink:
            return ink.company_id
        partiya = self.env['agronova.ink.partiya'].sudo().search([], limit=1)
        return partiya.company_id or self.env.company

    def _pl_analytic_accounts(self):
        self.ensure_one()
        return (self.env['agronova.ink.partiya']
                .search([('company_id', '=', self.company_id.id)])
                .mapped('analytic_account_id'))

    def _pl_ichki_sotuv(self):
        self.ensure_one()
        sotuvlar = self.env['agronova.ink.ichki_sotuv'].sudo().search([
            ('company_id', '=', self.company_id.id),
            ('holat', '=', 'done'),
            ('date', '>=', self.davr_boshi),
            ('date', '<=', self.davr_oxiri),
        ])
        # Korxonalararo sotuv buyurtmalari ham hisobga olinadi.
        return super()._pl_ichki_sotuv() + sum(sotuvlar.mapped('summa'))

    def _pl_elminatsiya(self):
        self.ensure_one()
        docs = self.env['agronova.ink.elminatsiya'].sudo().search([
            ('company_id', '=', self.company_id.id),
            ('holat', '=', 'posted'),
            ('davr_oxiri', '>=', self.davr_boshi),
            ('davr_oxiri', '<=', self.davr_oxiri),
        ])
        return sum(docs.mapped('jami_elminatsiya'))

    def _pl_korsatkichlar(self):
        self.ensure_one()
        # Ochilish sanasi bo'yicha olinadi: davrning natijasi — shu davrda
        # ochilgan jo'ja, qachon qo'yilganidan qat'i nazar.
        ochilishlar = self.env['agronova.ink.ochilish'].sudo().search([
            ('company_id', '=', self.company_id.id),
            ('holat', '=', 'done'),
            ('sana', '>=', self.davr_boshi),
            ('sana', '<=', self.davr_oxiri),
        ])
        self.ochilgan_joja = sum(ochilishlar.mapped('ochilgan_joja'))
        self.sof_joja = sum(ochilishlar.mapped('sof_joja'))
        # Maxraj — shu ochilishlarga tegishli partiyalarga qo'yilgan tuxum.
        partiyalar = ochilishlar.mapped('partiya_id')
        self.tuxum_dona = sum(partiyalar.mapped('tuxum_dona'))
        self.ochilish_foiz = (self.ochilgan_joja / self.tuxum_dona * 100.0
                              if self.tuxum_dona else 0.0)
        # Tannarx davrning umumiy xarajatidan emas, **aynan shu ochilgan
        # partiyalarning** xarajatidan hisoblanadi. Aks holda davr ichida
        # boshlangan, lekin hali ochilmagan partiyaning xarajati ham
        # maxrajga tushmay, faqat suratga qo'shilib ketardi va 1 dona jo'ja
        # tannarxi ikki barobar oshib ko'rinardi.
        xarajat = sum(
            p._agronova_analytic_amount(sign='cost', faqat_tannarx=True)
            for p in partiyalar)
        self.tannarx_1_joja = (xarajat / self.sof_joja
                               if self.sof_joja else 0.0)


class AgroNovaInkPlQator(models.TransientModel):
    _name = 'agronova.ink.pl.qator'
    _description = "Inkubatoriya — foyda-zarar hisoboti qatori"
    _inherit = ['agronova.pl.qator.mixin']

    pl_id = fields.Many2one('agronova.ink.pl', string="Hisobot",
                            ondelete='cascade')
    currency_id = fields.Many2one(related='pl_id.currency_id', readonly=True)
