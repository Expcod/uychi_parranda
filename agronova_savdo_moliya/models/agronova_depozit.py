# -*- coding: utf-8 -*-
"""Depozit — mas'ul xodim qo'lidagi naqd pul.

Brigadir, bo'lim boshlig'i yoki ta'minotchi qo'liga oldindan naqd pul
beriladi; u shu puldan mayda xarajatlarni to'laydi. Har naqd xarajat
depozitdan chiqim yozadi, qoldiq real vaqtda ko'rinadi.

TZ talabi: harakat **o'chirilmaydi**, faqat storno bilan teskari yoziladi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class AgroNovaDepozit(models.Model):
    _name = 'agronova.depozit'
    _description = "Depozit (mas'ul xodim naqdi)"
    _inherit = ['mail.thread']
    _order = 'name'

    name = fields.Char("Depozit nomi", required=True, tracking=True)
    egasi_id = fields.Many2one(
        'hr.employee', string="Depozit egasi", required=True, tracking=True,
        help="Pul kimning javobgarligida turadi.")
    user_id = fields.Many2one(
        'res.users', string="Foydalanuvchi",
        related='egasi_id.user_id', store=True, readonly=True,
        help="Depozit egasining tizimdagi hisobi — record rule shu bo'yicha ishlaydi.")
    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)
    harakat_ids = fields.One2many(
        'agronova.depozit.harakat', 'depozit_id', string="Harakatlar")
    kirim = fields.Monetary("Jami kirim", compute='_compute_balans', store=True)
    chiqim = fields.Monetary("Jami chiqim", compute='_compute_balans', store=True)
    balans = fields.Monetary(
        "Qoldiq", compute='_compute_balans', store=True, tracking=True)
    limit = fields.Monetary(
        "Ogohlantirish limiti",
        help="Qoldiq shu summadan pastga tushsa egasiga eslatma yuboriladi.")
    active = fields.Boolean("Faol", default=True)

    @api.depends('harakat_ids.summa', 'harakat_ids.turi', 'harakat_ids.holat')
    def _compute_balans(self):
        for dep in self:
            harakatlar = dep.harakat_ids.filtered(lambda h: h.holat == 'tasdiqlangan')
            kirim = sum(harakatlar.filtered(lambda h: h.turi == 'kirim').mapped('summa'))
            chiqim = sum(harakatlar.filtered(lambda h: h.turi == 'chiqim').mapped('summa'))
            dep.kirim = kirim
            dep.chiqim = chiqim
            dep.balans = kirim - chiqim

    def _chiqim_yozish(self, summa, izoh, manba=None, sana=None):
        """Depozitdan chiqim yozadi va harakat yozuvini qaytaradi."""
        self.ensure_one()
        if summa <= 0:
            raise ValidationError(_("Chiqim summasi noldan katta bo'lishi kerak."))
        vals = {
            'depozit_id': self.id,
            'turi': 'chiqim',
            'summa': summa,
            'izoh': izoh,
            'sana': sana or fields.Date.context_today(self),
            'holat': 'tasdiqlangan',
        }
        if manba:
            vals.update({'manba_model': manba._name, 'manba_id': manba.id})
        return self.env['agronova.depozit.harakat'].sudo().create(vals)


class AgroNovaDepozitHarakat(models.Model):
    _name = 'agronova.depozit.harakat'
    _description = "Depozit harakati"
    _order = 'sana desc, id desc'

    depozit_id = fields.Many2one(
        'agronova.depozit', string="Depozit", required=True,
        ondelete='restrict', index=True)
    sana = fields.Date("Sana", required=True, default=fields.Date.context_today)
    turi = fields.Selection(
        [('kirim', "Kirim"), ('chiqim', "Chiqim")],
        string="Turi", required=True, default='chiqim')
    summa = fields.Monetary("Summa", required=True)
    currency_id = fields.Many2one(
        'res.currency', related='depozit_id.currency_id', readonly=True)
    izoh = fields.Char("Izoh")
    holat = fields.Selection(
        [('draft', "Qoralama"),
         ('tasdiqlangan', "Tasdiqlangan"),
         ('storno', "Storno")],
        string="Holati", default='draft', required=True)
    # Manba hujjat (xarajat, kassa orderi) — generic bog'lanish, chunki
    # manba modellari turli bo'limlarda bo'ladi.
    manba_model = fields.Char("Manba modeli", readonly=True)
    manba_id = fields.Integer("Manba yozuvi", readonly=True)

    def action_storno(self):
        """Yozuvni balansdan chiqaradi, lekin tarixda qoldiradi.

        DIQQAT — bu yerda teskari yozuv YARATILMAYDI. Balans faqat
        `tasdiqlangan` yozuvlarni sanagani uchun asl yozuvni `storno` ga
        o'tkazishning o'zi kifoya: 100 lik kirim storno qilinsa balansga
        ta'siri nolga tushadi. Agar bunga qo'shimcha teskari yozuv ham
        yaratilsa, ta'sir −100 bo'lib qolardi (ilgari shunday xato bor edi).
        """
        for h in self:
            if h.holat != 'tasdiqlangan':
                raise UserError(_("Faqat tasdiqlangan harakat storno qilinadi."))
            h.write({
                'holat': 'storno',
                'izoh': _("STORNO: %s", h.izoh or ''),
            })
        return True

    def unlink(self):
        if any(h.holat != 'draft' for h in self):
            raise UserError(_(
                "Tasdiqlangan depozit harakati o'chirilmaydi — storno qiling."))
        return super().unlink()
