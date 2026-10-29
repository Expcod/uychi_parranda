# -*- coding: utf-8 -*-
"""Ichki narx — B09.

TZ talabi: narxni **sotuv bo'limi taklif qiladi, bosh buxgalter tasdiqlaydi**.
Tasdiqlangan narx o'zgartirilmaydi — tarix buzilmasligi kerak. Narx
o'zgarsa yangi yozuv ochiladi, eskisi arxivga o'tadi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

TUR = [
    ('tuxum_inkubatsiya', "Tuxum → Inkubatsiya"),
    ('poda_soyish', "Eskirgan poda → So'yish"),
]


class AgroNovaOnaTovuqNarx(models.Model):
    _name = 'agronova.ona_tovuq.narx'
    _description = "Ona tovuq — ichki narx"
    _inherit = ['mail.thread']
    _order = 'amal_sana desc, id desc'

    tur = fields.Selection(TUR, string="Turi", required=True, tracking=True,
                           default='tuxum_inkubatsiya')
    narx = fields.Monetary("Narx (birlik uchun)", required=True, tracking=True)
    amal_sana = fields.Date(
        "Amal qilish sanasi", required=True, tracking=True,
        default=fields.Date.context_today,
        help="Shu sanadan boshlab amal qiladi.")
    tugash_sana = fields.Date(
        "Tugash sanasi", readonly=True, copy=False,
        help="Yangi narx tasdiqlanganda avtomat qo'yiladi.")
    asos = fields.Text(
        "Asos", help="Narx nimaga asoslanadi — bozor narxi, tannarx tahlili.")
    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)

    holat = fields.Selection(
        [('draft', "Taklif"), ('confirmed', "Tasdiqlangan"),
         ('expired', "Muddati o'tgan")],
        string="Holati", default='draft', required=True, tracking=True, copy=False)
    taklif_qildi_id = fields.Many2one(
        'res.users', string="Taklif qildi", readonly=True, copy=False,
        default=lambda self: self.env.user)
    tasdiqladi_id = fields.Many2one(
        'res.users', string="Tasdiqladi", readonly=True, copy=False)
    tasdiq_sana = fields.Datetime("Tasdiqlangan vaqt", readonly=True, copy=False)

    _narx_musbat = models.Constraint(
        'CHECK (narx > 0)', "Narx noldan katta bo'lishi kerak.")

    def _compute_display_name(self):
        for n in self:
            n.display_name = "%s — %s (%s)" % (
                dict(TUR).get(n.tur, ''), n.narx, n.amal_sana or '')

    # ------------------------------------------------------------ tasdiqlash
    def action_tasdiqlash(self):
        """Bosh buxgalter tasdiqlaydi; eski narx muddati yopiladi."""
        for n in self:
            if n.holat != 'draft':
                raise UserError(_("Faqat taklif holatidagi narx tasdiqlanadi."))
            eski = self.search([
                ('tur', '=', n.tur),
                ('holat', '=', 'confirmed'),
                ('company_id', '=', n.company_id.id),
                ('id', '!=', n.id),
            ])
            eski.write({'holat': 'expired', 'tugash_sana': n.amal_sana})
            n.write({
                'holat': 'confirmed',
                'tasdiqladi_id': self.env.user.id,
                'tasdiq_sana': fields.Datetime.now(),
            })
        return True

    def write(self, vals):
        """Tasdiqlangan narx tarixi o'zgartirilmaydi."""
        himoyalangan = {'narx', 'tur', 'amal_sana'}
        for n in self:
            if n.holat == 'confirmed' and himoyalangan & set(vals):
                raise UserError(_(
                    "Tasdiqlangan narx o'zgartirilmaydi — tarix buziladi. "
                    "Yangi narx yozuvini oching."))
        return super().write(vals)

    def unlink(self):
        for n in self:
            if n.holat != 'draft':
                raise UserError(_("Faqat taklif holatidagi narx o'chiriladi."))
        return super().unlink()

    # ------------------------------------------------------------- yordamchi
    @api.model
    def amaldagi(self, tur, sana=None):
        """Berilgan sanada amal qiladigan tasdiqlangan narx."""
        sana = sana or fields.Date.context_today(self)
        return self.search([
            ('tur', '=', tur),
            ('holat', '=', 'confirmed'),
            ('amal_sana', '<=', sana),
        ], order='amal_sana desc', limit=1)
