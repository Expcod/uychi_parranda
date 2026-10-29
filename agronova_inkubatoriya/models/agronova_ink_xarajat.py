# -*- coding: utf-8 -*-
"""Inkubatoriya xarajat hujjati (TZ 7-band).

Umumiy mexanizm `agronova.xarajat.mixin` da. Bu yerda faqat inkubatoriyaga
xos qism: xarajat qaysi partiyalarga taqsimlanishi.

Taqsimlash bazasi sifatida mixinning `bosh_soni` kaliti ishlatiladi — bu
yerda u **qo'yilgan tuxum soni** degani. Inkubatoriyaning asosiy xarajati
(elektr, gaz, suv) inkubatorning ishlash vaqtiga, ya'ni undagi tuxum
miqdoriga proporsional.

`m2` kaliti **inkubator sig'imi** degani: ba'zi xarajat (ijara,
amortizatsiya) tuxum soniga emas, egallangan jihozga bog'liq.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AgroNovaInkXarajat(models.Model):
    _name = 'agronova.ink.xarajat'
    _description = "Inkubatoriya — xarajat hujjati"
    _inherit = ['agronova.xarajat.mixin']

    partiya_id = fields.Many2one(
        'agronova.ink.partiya', string="Partiya",
        help="«Bitta obyekt» maqsadida to'ldiriladi.")
    partiya_ids = fields.Many2many(
        'agronova.ink.partiya', string="Partiyalar",
        help="«Bir necha obyekt» maqsadida to'ldiriladi.")
    taqsimlash_bazasi = fields.Selection(
        selection_add=[('m2', "Inkubator sig'imi bo'yicha")])

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _("Yangi"):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'agronova.ink.xarajat') or _("Yangi")
        return super().create(vals_list)

    def _agronova_taqsimot_targets(self):
        """Xarajat tushadigan obyektlar — inkubatsiya partiyalari.

        «Butun bo'lim» maqsadida faqat **inkubatsiyadagi** partiyalar
        olinadi: yakunlangan partiyaning tannarxi qotgan, unga yangi
        xarajat tushsa o'tmishdagi jo'ja narxi o'zgarib ketardi.
        """
        self.ensure_one()
        if self.maqsad_turi == 'bitta':
            partiyalar = self.partiya_id
            if not partiyalar:
                raise UserError(_(
                    "«Bitta obyekt» maqsadida partiya tanlanishi kerak."))
        elif self.maqsad_turi == 'bir_necha':
            partiyalar = self.partiya_ids
            if not partiyalar:
                raise UserError(_(
                    "«Bir necha obyekt» maqsadida partiyalar tanlanishi "
                    "kerak."))
        else:
            partiyalar = self.env['agronova.ink.partiya'].search([
                ('company_id', '=', self.company_id.id),
                ('holat', '=', 'inkubatsiyada'),
            ])

        targets = []
        for p in partiyalar:
            targets.append({
                'record': p,
                'partiya': p,
                # Mixin `m2` bazasida shu kalitni o'qiydi — bu yerda
                # inkubator sig'imi
                'maydoni': p.inkubator_id.sigim,
                'bosh_soni': p.tuxum_dona,
                'analytic': p.analytic_account_id,
            })
        return targets
