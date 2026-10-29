# -*- coding: utf-8 -*-
"""Xodimni Boquv filiali va binosiga biriktirish.

Yakuniy TZ, «Ish haqi yo'nalishi»:

    Xodim kartochkasida **filial va bino** belgilanadi. Bino belgilangan
    (operator) → to'g'ridan-to'g'ri partiyaga. Bino belgilanmagan (brigadir,
    qorovul, oshpaz) → m² bo'yicha. Bino o'zgarsa tarix saqlanadi, oy
    o'rtasidagi ko'chish kunlar bo'yicha bo'linadi.

Ona Tovuqdan farqi ikkita:

1. **Ikki daraja** — filial va bino. Filial belgilangan, bino yo'q bo'lsa
   (filial boshlig'i, oshpaz) xarajat faqat o'sha filial binolariga
   taqsimlanadi, boshqa filiallarga tegmaydi.
2. **Qamrov** — veterinar mehnati faqat *aktiv* binoga tushadi
   (dizinfeksiyadagi binoda jo'ja yo'q), qolganlari *aktiv + dizinfeksiya*
   binolariga tushadi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    agronova_boquv_filial_id = fields.Many2one(
        'agronova.boquv.filial', string="Boquv filiali", tracking=True,
        groups="hr.group_hr_user",
        help="Belgilansa — ish haqi shu filial binolariga taqsimlanadi. "
             "Bo'sh bo'lsa barcha filiallarga.")
    agronova_boquv_bino_id = fields.Many2one(
        'agronova.boquv.bino', string="Boquv binosi", tracking=True,
        groups="hr.group_hr_user",
        domain="[('filial_id', '=', agronova_boquv_filial_id)]",
        help="Belgilansa — ish haqi to'g'ridan-to'g'ri shu binoning faol "
             "partiyalariga yoziladi (bino operatori). Bo'sh bo'lsa m² "
             "bo'yicha taqsimlanadi.")
    agronova_boquv_faqat_aktiv = fields.Boolean(
        "Faqat aktiv binolarga", groups="hr.group_hr_user",
        help="Veterinar kabi xodimlar uchun: mehnati faqat jo'ja bor "
             "binolarga tushadi, dizinfeksiyadagi bo'sh binoga emas.")
    agronova_boquv_bino_tarix_ids = fields.One2many(
        'agronova.boquv.xodim.bino.tarix', 'employee_id',
        string="Bino biriktirish tarixi", groups="hr.group_hr_user")

    @api.constrains('agronova_boquv_filial_id', 'agronova_boquv_bino_id')
    def _check_boquv_bino(self):
        for emp in self:
            bino = emp.agronova_boquv_bino_id
            if bino and emp.agronova_boquv_filial_id \
                    and bino.filial_id != emp.agronova_boquv_filial_id:
                raise ValidationError(_(
                    "«%(xodim)s»: «%(bino)s» binosi «%(bfilial)s» filialiga "
                    "tegishli, kartochkada esa «%(kfilial)s» ko'rsatilgan.",
                    xodim=emp.name, bino=bino.display_name,
                    bfilial=bino.filial_id.name,
                    kfilial=emp.agronova_boquv_filial_id.name))

    @api.onchange('agronova_boquv_bino_id')
    def _onchange_boquv_bino(self):
        """Bino tanlanganda filial avtomat to'ldiriladi."""
        if self.agronova_boquv_bino_id:
            self.agronova_boquv_filial_id = self.agronova_boquv_bino_id.filial_id

    def write(self, vals):
        """Bino o'zgarsa tarixga yozadi — ish haqi kunlar bo'yicha bo'linadi."""
        if 'agronova_boquv_bino_id' in vals:
            bugun = fields.Date.context_today(self)
            Tarix = self.env['agronova.boquv.xodim.bino.tarix'].sudo()
            for emp in self:
                if emp.agronova_boquv_bino_id.id == vals['agronova_boquv_bino_id']:
                    continue
                ochiq = Tarix.search([
                    ('employee_id', '=', emp.id),
                    ('tugash_sana', '=', False),
                ])
                ochiq.write({'tugash_sana': bugun})
                if vals['agronova_boquv_bino_id']:
                    Tarix.create({
                        'employee_id': emp.id,
                        'bino_id': vals['agronova_boquv_bino_id'],
                        'boshlanish_sana': bugun,
                    })
        return super().write(vals)


class AgroNovaBoquvXodimBinoTarix(models.Model):
    """Xodim qaysi binoda, qaysi kundan qaysi kungacha ishlagani."""
    _name = 'agronova.boquv.xodim.bino.tarix'
    _description = "Boquv — xodim bino tarixi"
    _order = 'boshlanish_sana desc, id desc'

    employee_id = fields.Many2one(
        'hr.employee', string="Xodim", required=True, ondelete='cascade',
        index=True)
    bino_id = fields.Many2one(
        'agronova.boquv.bino', string="Bino", required=True, ondelete='restrict')
    filial_id = fields.Many2one(
        related='bino_id.filial_id', string="Filial", store=True, readonly=True)
    boshlanish_sana = fields.Date("Boshlanish sanasi", required=True)
    tugash_sana = fields.Date(
        "Tugash sanasi",
        help="Bo'sh bo'lsa — xodim hozir shu binoda ishlaydi.")

    _sana_togri = models.Constraint(
        'CHECK (tugash_sana IS NULL OR tugash_sana >= boshlanish_sana)',
        "Tugash sanasi boshlanish sanasidan oldin bo'lmaydi.")

    def kunlar(self, davr_boshi, davr_oxiri):
        """Shu biriktirish davr ichida necha kunni qamraydi."""
        self.ensure_one()
        boshi = max(self.boshlanish_sana, davr_boshi)
        oxiri = min(self.tugash_sana or davr_oxiri, davr_oxiri)
        return (oxiri - boshi).days + 1 if oxiri >= boshi else 0

    @api.depends('employee_id', 'bino_id', 'boshlanish_sana')
    def _compute_display_name(self):
        for t in self:
            t.display_name = "%s · %s (%s)" % (
                t.employee_id.name or '', t.bino_id.display_name or '',
                t.boshlanish_sana or '')
