# -*- coding: utf-8 -*-
"""Xodimning ish haqi tarifi (TZ M09).

Uch xil tarif bor — mijozning «Xodimlar» jadvalidagi «Maoshi ta'rifi»
ustuni bilan bir xil:

* **Oklad** — oylik summa oydagi ish kuni normasiga bo'linadi va ishlagan
  kuniga ko'paytiriladi. Mijozda normasi 26;
* **Kunbay** — hisoblash formulasi bir xil, lekin normasi boshqa: mijozda
  15 yoki 30. Qorovul, oshpaz, elektrik kabilarda uchraydi;
* **Soatli** — stavka 1 soat narxi, ishlagan soatiga ko'paytiriladi.
  Mijozda 19 000 dan 38 000 so'mgacha.

Shuning uchun norma **tarifda saqlanadi**, kodga qattiq yozilmaydi:
xodimdan xodimga o'zgaradi.

Tarif **tarixi bilan** yuritiladi: oylik o'zgarsa eski yozuv o'zgartirilmaydi,
yangisi ochiladi. Shunda o'tgan oylarning hisob-kitobi qayta hisoblansa ham
o'sha paytdagi tarif bilan chiqadi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

TUR = [
    ('oklad', "Oklad"),
    ('kunbay', "Kunbay"),
    ('soatlik', "Soatli"),
]

# Kun normasi talab qilinadigan turlar
KUNLIK = ('oklad', 'kunbay')


class AgroNovaIshHaqiTarif(models.Model):
    _name = 'agronova.ish_haqi.tarif'
    _description = "Ish haqi tarifi"
    _inherit = ['mail.thread']
    _order = 'amal_sana desc, id desc'

    employee_id = fields.Many2one(
        'hr.employee', string="Xodim", required=True, ondelete='cascade',
        index=True, tracking=True)
    tur = fields.Selection(TUR, string="Tarif turi", required=True,
                           default='oklad', tracking=True)
    stavka = fields.Monetary(
        "Stavka", required=True, tracking=True,
        help="Oklad va kunbayda — oylik summa, soatlida — 1 soat narxi.")
    norma_kun = fields.Float(
        "Oydagi ish kuni", tracking=True,
        help="Oylik summa shu kunga bo'linadi. Mijoz jadvalidagi «Oydagi "
             "ish kuni» ustuni: okladda 26, kunbayda 15 yoki 30. "
             "Soatli tarifda ishlatilmaydi.")
    amal_sana = fields.Date(
        "Amal qilish sanasi", required=True, tracking=True,
        default=fields.Date.context_today)
    tugash_sana = fields.Date(
        "Tugash sanasi", readonly=True, copy=False,
        help="Yangi tarif tasdiqlanganda avtomat qo'yiladi.")
    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True, readonly=True,
        store=True, precompute=True, compute='_compute_company_id')
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)
    holat = fields.Selection(
        [('draft', "Taklif"), ('confirmed', "Amalda"),
         ('expired', "Muddati o'tgan")],
        string="Holati", default='draft', required=True, tracking=True,
        copy=False)
    izoh = fields.Text("Asos")

    _stavka_musbat = models.Constraint(
        'CHECK (stavka > 0)', "Stavka noldan katta bo'lishi kerak.")
    _norma_musbat = models.Constraint(
        'CHECK (norma_kun >= 0)', "Ish kuni normasi manfiy bo'lolmaydi.")

    @api.depends('employee_id')
    def _compute_company_id(self):
        for t in self:
            t.company_id = t.employee_id.company_id or self.env.company

    def _compute_display_name(self):
        for t in self:
            t.display_name = "%s — %s (%s)" % (
                t.employee_id.name or '', dict(TUR).get(t.tur, ''),
                t.amal_sana or '')

    @api.constrains('tur', 'norma_kun')
    def _check_norma(self):
        for t in self:
            if t.tur in KUNLIK and t.norma_kun <= 0:
                raise ValidationError(_(
                    "«%s» tarifida oydagi ish kuni ko'rsatilishi shart — "
                    "oylik summa shunga bo'linadi.",
                    dict(TUR).get(t.tur, t.tur)))

    # ------------------------------------------------------------ tasdiqlash
    def action_tasdiqlash(self):
        for t in self:
            if t.holat != 'draft':
                raise UserError(_("Faqat taklif holatidagi tarif tasdiqlanadi."))
            eski = self.search([
                ('employee_id', '=', t.employee_id.id),
                ('holat', '=', 'confirmed'),
                ('id', '!=', t.id),
            ])
            eski.write({'holat': 'expired', 'tugash_sana': t.amal_sana})
            t.holat = 'confirmed'
        return True

    def write(self, vals):
        himoyalangan = {'stavka', 'tur', 'amal_sana', 'employee_id',
                        'norma_kun'}
        for t in self:
            if t.holat == 'confirmed' and himoyalangan & set(vals):
                raise UserError(_(
                    "Amaldagi tarif o'zgartirilmaydi — o'tgan oylarning "
                    "hisob-kitobi buziladi. Yangi tarif yozuvini oching."))
        return super().write(vals)

    def unlink(self):
        for t in self:
            if t.holat != 'draft':
                raise UserError(_("Faqat taklif holatidagi tarif o'chiriladi."))
        return super().unlink()

    # ------------------------------------------------------------- yordamchi
    @api.model
    def amaldagi(self, employee, sana=None):
        """Berilgan sanada amal qilgan tarif."""
        sana = sana or fields.Date.context_today(self)
        return self.search([
            ('employee_id', '=', employee.id),
            ('holat', 'in', ('confirmed', 'expired')),
            ('amal_sana', '<=', sana),
            '|', ('tugash_sana', '=', False), ('tugash_sana', '>', sana),
        ], order='amal_sana desc', limit=1)
