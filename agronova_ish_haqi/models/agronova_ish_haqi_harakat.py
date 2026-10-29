# -*- coding: utf-8 -*-
"""Xodim bilan hisob-kitob harakati — «hisoblandi / berildi / qoldiq».

TZ M09 talabi: rahbariyat ham, xodimning o'zi ham istalgan paytda qancha
hisoblangani, qancha berilgani va qancha qolganini ko'rishi kerak.

Odooning `hr_payroll` moduli buni bermaydi — u hisobvaraq (payslip)
yaratadi, lekin xodim bilan **joriy hisob** tushunchasi yo'q. Shuning uchun
loyihadagi brigadir depoziti bilan bir xil uslub tanlandi: har bir pul
harakati alohida qator, balans esa ularning yig'indisi.

Ishorasi turga qarab avtomat: hisoblangan va bonus balansni oshiradi,
avans, jarima va berilgan pul kamaytiradi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

TUR = [
    ('hisoblandi', "Hisoblandi"),
    ('bonus', "Bonus"),
    ('avans', "Avans"),
    ('jarima', "Jarima"),
    ('berildi', "Berildi"),
]

# Balansga qanday ta'sir qiladi
ISHORA = {
    'hisoblandi': 1,
    'bonus': 1,
    'avans': -1,
    'jarima': -1,
    'berildi': -1,
}


class AgroNovaIshHaqiHarakat(models.Model):
    _name = 'agronova.ish_haqi.harakat'
    _description = "Ish haqi — xodim bilan hisob-kitob harakati"
    _order = 'sana desc, id desc'

    employee_id = fields.Many2one(
        'hr.employee', string="Xodim", required=True, ondelete='cascade',
        index=True)
    sana = fields.Date("Sana", required=True, index=True,
                       default=fields.Date.context_today)
    tur = fields.Selection(TUR, string="Turi", required=True, index=True)
    summa = fields.Monetary(
        "Summa", required=True,
        help="Har doim musbat kiritiladi — balansga ta'siri turdan aniqlanadi.")
    balans_summa = fields.Monetary(
        "Balansga ta'siri", compute='_compute_balans_summa', store=True,
        help="Hisoblangan va bonus musbat, avans/jarima/berilgan manfiy.")
    davr_id = fields.Many2one(
        'agronova.ish_haqi.davr', string="Hisoblash davri", ondelete='cascade',
        index=True, help="Oylik hisoblash hujjatidan kelgan bo'lsa.")
    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True, readonly=True,
        store=True, precompute=True, compute='_compute_company_id')
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)
    kassa_harakat_id = fields.Many2one(
        'agronova.kassa.harakat', string="Kassa orderi", readonly=True,
        index=True, ondelete='cascade',
        help="Kassadan berilgan bo'lsa — qaysi order orqali.")
    izoh = fields.Char("Izoh")

    _summa_musbat = models.Constraint(
        'CHECK (summa > 0)',
        "Summa musbat kiritiladi — kamaytirish turdan aniqlanadi.")

    @api.depends('employee_id')
    def _compute_company_id(self):
        for h in self:
            h.company_id = h.employee_id.company_id or self.env.company

    @api.depends('tur', 'summa')
    def _compute_balans_summa(self):
        for h in self:
            h.balans_summa = ISHORA.get(h.tur, 0) * h.summa

    def _compute_display_name(self):
        for h in self:
            h.display_name = "%s — %s" % (dict(TUR).get(h.tur, ''), h.summa)

    def write(self, vals):
        # Oylik hisoblashdan kelgan qatorlar hujjat orqali boshqariladi
        if not self.env.context.get('agronova_ish_haqi_post'):
            for h in self:
                if h.davr_id and set(vals) - {'izoh'}:
                    raise UserError(_(
                        "Bu qator «%s» hisoblash hujjatidan kelgan — "
                        "to'g'ridan-to'g'ri tahrirlanmaydi. Hujjatni storno "
                        "qiling.", h.davr_id.display_name))
        return super().write(vals)

    def unlink(self):
        if not self.env.context.get('agronova_ish_haqi_post'):
            for h in self:
                if h.davr_id:
                    raise UserError(_(
                        "Hisoblash hujjatidan kelgan qator o'chirilmaydi "
                        "(%s).", h.davr_id.display_name))
        return super().unlink()
