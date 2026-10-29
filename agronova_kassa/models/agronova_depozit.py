# -*- coding: utf-8 -*-
"""Depozitni kassa bilan bog'lash.

`agronova_savdo_moliya` depozitni bilardi, lekin pul unga QAYERDAN kelishini
bilmasdi — brigadirning qo'lidagi naqd «osmondan tushgan» edi. Endi
zanjir yopiladi:

    kassa CHIQIM (depozit moddasi) → depozitga KIRIM
    kassa KIRIM  (depozit moddasi) → depozitdan CHIQIM (qaytardi)

Depozitdagi pul kassa qoldig'iga kirmaydi — u kassadan chiqib bo'lgan.
Ikkovining yig'indisi korxonaning qo'lidagi umumiy naqdni beradi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AgroNovaDepozit(models.Model):
    _inherit = 'agronova.depozit'

    kassa_harakat_ids = fields.One2many(
        'agronova.kassa.harakat', 'depozit_id', string="Kassa yozuvlari",
        help="Shu depozit bo'yicha kassadan berilgan va qaytarilgan pul.",
    )
    kassa_harakat_count = fields.Integer(
        string="Kassa yozuvlari soni", compute='_compute_kassa_count',
    )
    kassadan_olingan = fields.Monetary(
        string="Kassadan olingan", compute='_compute_kassadan',
        help="Shu depozitga kassadan berilgan jami naqd (storno hisobga "
             "olingan holda).",
    )

    def _compute_kassa_count(self):
        groups = self.env['agronova.kassa.harakat'].sudo()._read_group(
            [('depozit_id', 'in', self.ids)], ['depozit_id'], ['__count'],
        )
        mapped = {dep.id: count for dep, count in groups}
        for dep in self:
            dep.kassa_harakat_count = mapped.get(dep.id, 0)

    def _compute_kassadan(self):
        groups = self.env['agronova.kassa.harakat'].sudo()._read_group(
            [('depozit_id', 'in', self.ids), ('state', '=', 'posted'),
             ('direction', '=', 'out')],
            ['depozit_id'], ['amount:sum'],
        )
        mapped = {dep.id: total for dep, total in groups}
        for dep in self:
            dep.kassadan_olingan = mapped.get(dep.id, 0.0)

    def action_open_kassa_harakat(self):
        self.ensure_one()
        return {
            'name': _("«%s» — kassa yozuvlari", self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'agronova.kassa.harakat',
            'views': [(False, 'list'), (False, 'form')],
            'domain': [('depozit_id', '=', self.id)],
            'context': {'create': False},
        }

    def action_kassadan_toldirish(self):
        """Depozit formasidan «kassadan pul olish» oynasini ochadi."""
        self.ensure_one()
        modda = self.env['agronova.kassa.modda'].sudo().search([
            ('depozit', '=', True), ('direction', '=', 'out'),
        ], limit=1)
        if not modda:
            raise UserError(_(
                "«Depozit harakati» belgisi qo'yilgan chiqim moddasi "
                "topilmadi (Kassa → Sozlamalar → Moddalar)."))
        kassa = self.env['agronova.kassa']._default_kassa(company=self.company_id)
        return {
            'name': _("«%s» depozitiga kassadan pul berish", self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'agronova.kassa.harakat',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {
                'default_direction': 'out',
                'default_depozit_id': self.id,
                'default_modda_id': modda.id,
                'default_kassa_id': kassa.id or False,
                'default_izoh': _("«%s» depozitiga naqd berildi", self.name),
            },
        }


class AgroNovaDepozitHarakat(models.Model):
    _inherit = 'agronova.depozit.harakat'

    kassa_harakat_id = fields.Many2one(
        'agronova.kassa.harakat', string="Kassa yozuvi",
        compute='_compute_kassa_harakat',
        help="Depozitga pul qaysi kassa orderi bilan kelgani.",
    )

    @api.depends('manba_model', 'manba_id')
    def _compute_kassa_harakat(self):
        for rec in self:
            if rec.manba_model == 'agronova.kassa.harakat' and rec.manba_id:
                rec.kassa_harakat_id = rec.manba_id
            else:
                rec.kassa_harakat_id = False
