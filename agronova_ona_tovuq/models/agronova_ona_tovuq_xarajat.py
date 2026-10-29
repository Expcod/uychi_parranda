# -*- coding: utf-8 -*-
"""Ona tovuq xarajat hujjati — B05 / B06.

Umumiy mexanizm `agronova.xarajat.mixin` da (naqd/qarz, foto majburiy,
tahrirlash muddati, storno). Bu yerda faqat Ona Tovuqqa xos qism:
xarajat qaysi sexlarga va ulardagi aktiv partiyalarga taqsimlanishi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AgroNovaOnaTovuqXarajat(models.Model):
    _name = 'agronova.ona_tovuq.xarajat'
    _description = "Ona tovuq — xarajat hujjati"
    _inherit = ['agronova.xarajat.mixin']

    sex_id = fields.Many2one(
        'agronova.ona_tovuq.sex', string="Sex",
        help="«Bitta obyekt» maqsadida to'ldiriladi.")
    sex_ids = fields.Many2many(
        'agronova.ona_tovuq.sex', string="Sexlar",
        help="«Bir necha obyekt» maqsadida to'ldiriladi.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _("Yangi"):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'agronova.ona_tovuq.xarajat') or _("Yangi")
        return super().create(vals_list)

    # --------------------------------------------------------------- maqsad
    def _agronova_taqsimot_targets(self):
        """Xarajat tushadigan obyektlar — sexlar.

        Sexda aktiv partiya bo'lsa, xarajat partiyaga yoziladi (tannarxga
        kirsin), bo'lmasa sexning o'z analitik hisobiga.
        """
        self.ensure_one()
        if self.maqsad_turi == 'bitta':
            sexlar = self.sex_id
            if not sexlar:
                raise UserError(_("«Bitta obyekt» maqsadida sex tanlanishi kerak."))
        elif self.maqsad_turi == 'bir_necha':
            sexlar = self.sex_ids
            if not sexlar:
                raise UserError(_("«Bir necha obyekt» maqsadida sexlar tanlanishi kerak."))
        else:
            sexlar = self.env['agronova.ona_tovuq.sex'].search(
                [('company_id', '=', self.company_id.id)])

        targets = []
        for sex in sexlar:
            partiya = sex.aktiv_partiya_id or sex.aktiv_ostirish_id
            targets.append({
                'record': partiya or sex,
                'sex': sex,
                'maydoni': sex.maydoni,
                'bosh_soni': sex.joriy_son,
                'analytic': (partiya or sex).analytic_account_id,
            })
        return targets
