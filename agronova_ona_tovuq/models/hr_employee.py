# -*- coding: utf-8 -*-
"""Xodimni sexga biriktirish va biriktirish tarixi — B01 / B07.

Ish haqi taqsimoti shu maydonga tayanadi: sex belgilangan xodim (operator)
ish haqi to'g'ridan-to'g'ri o'sha sexning aktiv partiyasiga yoziladi,
belgilanmagani (bo'lim boshlig'i, veterinar) m² bo'yicha taqsimlanadi.

Oy o'rtasida sex o'zgarsa, ish haqi kunlar bo'yicha bo'linishi kerak —
shuning uchun har o'zgarish tarix yozuvi bilan qayd etiladi.
"""
from odoo import _, api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    agronova_ot_sex_id = fields.Many2one(
        'agronova.ona_tovuq.sex', string="Ona tovuq sexi", tracking=True,
        groups="hr.group_hr_user",
        help="Belgilansa — ish haqi to'g'ridan-to'g'ri shu sexga yoziladi. "
             "Bo'sh bo'lsa m² bo'yicha barcha sexlarga taqsimlanadi.")
    agronova_ot_sex_tarix_ids = fields.One2many(
        'agronova.ona_tovuq.xodim.sex.tarix', 'employee_id',
        string="Sex biriktirish tarixi", groups="hr.group_hr_user")

    def write(self, vals):
        """Sex o'zgarsa tarixga yozadi."""
        if 'agronova_ot_sex_id' in vals:
            bugun = fields.Date.context_today(self)
            Tarix = self.env['agronova.ona_tovuq.xodim.sex.tarix'].sudo()
            for emp in self:
                if emp.agronova_ot_sex_id.id == vals['agronova_ot_sex_id']:
                    continue
                ochiq = Tarix.search([
                    ('employee_id', '=', emp.id),
                    ('tugash_sana', '=', False),
                ])
                ochiq.write({'tugash_sana': bugun})
                if vals['agronova_ot_sex_id']:
                    Tarix.create({
                        'employee_id': emp.id,
                        'sex_id': vals['agronova_ot_sex_id'],
                        'boshlanish_sana': bugun,
                    })
        return super().write(vals)


class AgroNovaOnaTovuqXodimSexTarix(models.Model):
    """Xodim qaysi sexda, qaysi kundan qaysi kungacha ishlagani."""
    _name = 'agronova.ona_tovuq.xodim.sex.tarix'
    _description = "Ona tovuq — xodim sex tarixi"
    _order = 'boshlanish_sana desc, id desc'

    employee_id = fields.Many2one(
        'hr.employee', string="Xodim", required=True, ondelete='cascade',
        index=True)
    sex_id = fields.Many2one(
        'agronova.ona_tovuq.sex', string="Sex", required=True, ondelete='restrict')
    boshlanish_sana = fields.Date("Boshlanish sanasi", required=True)
    tugash_sana = fields.Date("Tugash sanasi")

    def kunlar(self, davr_boshi, davr_oxiri):
        """Berilgan davrda shu sexda ishlagan kunlar soni."""
        self.ensure_one()
        boshi = max(self.boshlanish_sana, davr_boshi)
        oxiri = min(self.tugash_sana or davr_oxiri, davr_oxiri)
        return max((oxiri - boshi).days + 1, 0)
