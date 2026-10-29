# -*- coding: utf-8 -*-
"""Davr xarajatlarini tannarxga taqsimlash (TZ 9.1, 9.2).

Xomashyo va qadoq buyurtmaga to'g'ridan-to'g'ri tushadi. Ish haqi, elektr,
gaz, uskunaga xizmat va boshqa umumiy xarajatlar esa oy bo'yicha
yig'iladi va shu oyda ishlab chiqarilgan kg ga mutanosib taqsimlanadi:

    1 kg ga ustama = davr xarajatlari / davrda ishlab chiqarilgan kg

Taqsimlash qayta bajarilishi mumkin (xarajat qo'shilsa) — har safar
hamma buyurtmalar qaytadan hisoblanadi, ikki marta qo'shilmaydi.
"""
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

KATEGORIYA = [
    ('ish_haqi', "Ishlab chiqarish ish haqi"),
    ('elektr', "Elektr energiyasi"),
    ('gaz', "Gaz, bug' va boshqa energiya"),
    ('xizmat', "Uskunalarga xizmat ko'rsatish"),
    ('amortizatsiya', "Amortizatsiya"),
    ('bevosita', "Boshqa bevosita xarajatlar"),
    ('bilvosita', "Bilvosita ishlab chiqarish xarajatlari"),
]


class AgroNovaYemXarajat(models.Model):
    _name = 'agronova.yem.xarajat'
    _description = "Yem zavodi — davr xarajatlari taqsimoti"
    _inherit = ['mail.thread']
    _order = 'oy desc'

    name = fields.Char("Nomi", compute='_compute_name', store=True)
    company_id = fields.Many2one('res.company', "Korxona", required=True, default=lambda s: s.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    oy = fields.Date("Oy", required=True,
                     default=lambda s: fields.Date.context_today(s).replace(day=1))
    qator_ids = fields.One2many('agronova.yem.xarajat.qator', 'xarajat_id', "Xarajatlar")
    jami = fields.Monetary("Jami xarajat", compute='_compute_jami', store=True)
    ishlab_chiqarilgan_kg = fields.Float("Ishlab chiqarildi (kg)", readonly=True, digits=(16, 0))
    ustama_1_kg = fields.Float("1 kg ga ustama", readonly=True, digits='Product Price')
    ustama_1_t = fields.Float("1 tonnaga ustama", readonly=True, digits='Product Price')
    state = fields.Selection([('draft', "Loyiha"), ('taqsimlangan', "Taqsimlangan")], "Holat",
                             default='draft', tracking=True)

    _oy_uniq = models.Constraint('unique(oy, company_id)', "Bu oy uchun taqsimot allaqachon bor.")

    @api.depends('oy')
    def _compute_name(self):
        for x in self:
            x.name = _("Xarajatlar %s", x.oy.strftime('%m.%Y')) if x.oy else ''

    @api.depends('qator_ids.summa')
    def _compute_jami(self):
        for x in self:
            x.jami = sum(x.qator_ids.mapped('summa'))

    def _davr(self):
        self.ensure_one()
        dan = self.oy.replace(day=1)
        return dan, dan + relativedelta(months=1)

    def _buyurtmalar(self):
        dan, gacha = self._davr()
        return self.env['mrp.production'].search([
            ('state', '=', 'done'), ('agronova_yem', '=', True), ('company_id', '=', self.company_id.id),
            ('date_finished', '>=', fields.Datetime.to_datetime(dan)),
            ('date_finished', '<', fields.Datetime.to_datetime(gacha)),
        ])

    def action_energiyadan(self):
        """Elektr va gaz qatorlarini energiya yozuvlaridan to'ldiradi."""
        for x in self:
            dan, gacha = x._davr()
            en = self.env['agronova.yem.energiya'].search([
                ('company_id', '=', x.company_id.id), ('sana', '>=', dan), ('sana', '<', gacha)])
            elektr = sum(e.elektr_kwh * e.elektr_narx for e in en)
            gaz = sum(e.gaz_m3 * e.gaz_narx for e in en)
            for kat, summa in (('elektr', elektr), ('gaz', gaz)):
                q = x.qator_ids.filtered(lambda r: r.kategoriya == kat)
                if q:
                    q[:1].summa = summa
                elif summa:
                    x.qator_ids = [(0, 0, {'kategoriya': kat, 'summa': summa,
                                           'izoh': _("Energiya yozuvlaridan")})]
        return True

    def action_taqsimlash(self):
        for x in self:
            mos = x._buyurtmalar()
            kg = sum(mos.mapped('agronova_miqdor_kg'))
            if not kg:
                raise UserError(_("Bu oyda yopilgan yem buyurtmasi yo'q — taqsimlanadigan hajm yo'q."))
            stavka = x.jami / kg
            for mo in mos:
                mo.agronova_ustama_taqsim = mo.agronova_miqdor_kg * stavka
            x.write({'ishlab_chiqarilgan_kg': kg, 'ustama_1_kg': stavka,
                     'ustama_1_t': stavka * 1000.0, 'state': 'taqsimlangan'})
            x.message_post(body=_("%(n)s ta buyurtmaga taqsimlandi: 1 kg ga %(s)s.",
                                  n=len(mos), s=round(stavka, 2)))
        return True

    def action_bekor(self):
        for x in self:
            for mo in x._buyurtmalar():
                mo.agronova_ustama_taqsim = 0.0
            x.state = 'draft'
        return True


class AgroNovaYemXarajatQator(models.Model):
    _name = 'agronova.yem.xarajat.qator'
    _description = "Davr xarajati qatori"

    xarajat_id = fields.Many2one('agronova.yem.xarajat', required=True, ondelete='cascade')
    currency_id = fields.Many2one(related='xarajat_id.currency_id')
    kategoriya = fields.Selection(KATEGORIYA, "Kategoriya", required=True)
    summa = fields.Monetary("Summa")
    izoh = fields.Char("Izoh")
