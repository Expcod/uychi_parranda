# -*- coding: utf-8 -*-
"""Qishloq xo'jaligi xarajat hujjati (TZ 5-band).

Umumiy mexanizm `agronova.xarajat.mixin` da (naqd/qarz, foto majburiy,
tahrirlash muddati, storno). Bu yerda faqat qishloq xo'jaligiga xos qism:
xarajat qaysi yerlarga va ulardagi faol partiyalarga taqsimlanishi.

Taqsimlash bazasi sifatida mixinning `m2` kaliti ishlatiladi, lekin bu
yerda u **gektar** degani — shuning uchun yorlig'i qayta nomlangan.
Sug'orish, elektr, texnika xarajati aynan maydon nisbatida bo'linadi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AgroNovaQxXarajat(models.Model):
    _name = 'agronova.qx.xarajat'
    _description = "Qishloq xo'jaligi — xarajat hujjati"
    _inherit = ['agronova.xarajat.mixin']

    yer_id = fields.Many2one(
        'agronova.qx.yer', string="Yer maydoni",
        help="«Bitta obyekt» maqsadida to'ldiriladi.")
    yer_ids = fields.Many2many(
        'agronova.qx.yer', string="Yer maydonlari",
        help="«Bir necha obyekt» maqsadida to'ldiriladi.")
    # `m2` kaliti saqlanadi (mixin shu bo'yicha og'irlik hisoblaydi),
    # faqat foydalanuvchi ko'radigan yorlig'i almashtiriladi.
    taqsimlash_bazasi = fields.Selection(
        selection_add=[('m2', "Maydon (gektar) bo'yicha")])

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _("Yangi"):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'agronova.qx.xarajat') or _("Yangi")
        return super().create(vals_list)

    # --------------------------------------------------------------- maqsad
    def _agronova_taqsimot_targets(self):
        """Xarajat tushadigan obyektlar — yerlar.

        Yerda faol partiya bo'lsa xarajat partiyaga yoziladi (tannarxga
        kirsin), bo'lmasa yerning o'z analitik hisobiga.
        """
        self.ensure_one()
        if self.maqsad_turi == 'bitta':
            yerlar = self.yer_id
            if not yerlar:
                raise UserError(_("«Bitta obyekt» maqsadida yer tanlanishi kerak."))
        elif self.maqsad_turi == 'bir_necha':
            yerlar = self.yer_ids
            if not yerlar:
                raise UserError(_(
                    "«Bir necha obyekt» maqsadida yerlar tanlanishi kerak."))
        else:
            yerlar = self.env['agronova.qx.yer'].search(
                [('company_id', '=', self.company_id.id)])

        targets = []
        for yer in yerlar:
            partiya = yer.aktiv_partiya_id
            targets.append({
                'record': partiya or yer,
                'yer': yer,
                # Mixin `m2` bazasida shu kalitni o'qiydi — bu yerda gektar.
                'maydoni': (partiya.maydoni_ga or yer.maydoni_ga
                            if partiya else yer.maydoni_ga),
                'bosh_soni': 0.0,
                'analytic': (partiya or yer).analytic_account_id,
            })
        return targets
