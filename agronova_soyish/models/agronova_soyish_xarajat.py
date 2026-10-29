# -*- coding: utf-8 -*-
"""So'yish xarajat hujjati (TZ 11-band).

Umumiy mexanizm `agronova.xarajat.mixin` da. Bu yerda faqat so'yishga xos
qism: xarajat qaysi partiyalarga taqsimlanishi.

Taqsimlash bazasi sifatida mixinning `bosh_soni` kaliti ishlatiladi —
so'yish xarajatining katta qismi (ishchi kuchi, elektr, suv) **so'yilgan
bosh soniga** proporsional. Vazn bo'yicha taqsimlash kerak bo'lsa `m2`
kaliti ishlatiladi, u bu yerda **tirik vazn** degani.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AgroNovaSoyishXarajat(models.Model):
    _name = 'agronova.soyish.xarajat'
    _description = "So'yish — xarajat hujjati"
    _inherit = ['agronova.xarajat.mixin']

    partiya_id = fields.Many2one(
        'agronova.soyish.partiya', string="Partiya",
        help="«Bitta obyekt» maqsadida to'ldiriladi.")
    partiya_ids = fields.Many2many(
        'agronova.soyish.partiya', string="Partiyalar",
        help="«Bir necha obyekt» maqsadida to'ldiriladi.")
    # `m2` kaliti saqlanadi (mixin shu bo'yicha og'irlik hisoblaydi),
    # faqat yorlig'i almashtiriladi — bu yerda u tirik vazn degani.
    taqsimlash_bazasi = fields.Selection(
        selection_add=[('m2', "Tirik vazn (kg) bo'yicha")])

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _("Yangi"):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'agronova.soyish.xarajat') or _("Yangi")
        return super().create(vals_list)

    def _agronova_taqsimot_targets(self):
        """Xarajat tushadigan obyektlar — so'yish partiyalari.

        Tashqi mijoz partiyasi ham kiradi: unga ham ishchi kuchi va elektr
        sarflanadi, xizmat haqining rentabelligi shundan ko'rinadi.
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
                    "«Bir necha obyekt» maqsadida partiyalar tanlanishi kerak."))
        else:
            partiyalar = self.env['agronova.soyish.partiya'].search([
                ('company_id', '=', self.company_id.id),
                ('holat', '=', 'active'),
            ])

        targets = []
        for p in partiyalar:
            targets.append({
                'record': p,
                'partiya': p,
                # Mixin `m2` bazasida shu kalitni o'qiydi — bu yerda tirik vazn
                'maydoni': p.tirik_vazn_kg,
                'bosh_soni': p.soyilgan_son or p.tirik_son,
                'analytic': p.analytic_account_id,
            })
        return targets
