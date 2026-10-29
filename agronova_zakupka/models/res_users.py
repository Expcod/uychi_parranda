# -*- coding: utf-8 -*-
"""Xarid bo'limi xodimlari (TZ 4.11, 17-bo'lim).

Zakupchiklar soni o'zgaruvchan — rol qattiq kodlanmaydi. Admin userga
`group_zakupka_zakupchik` guruhini bersa, tranzit ombori va depozit
bog'lanishi shu yerda avtomat hal bo'ladi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

ZAKUPKA_ROLI = [
    ('zakupchik', "Zakupchik"),
    ('bolim_boshligi', "Zakupka bo'lim boshlig'i"),
    ('sifat_nazorat', "Sifat va narx nazorati boshlig'i"),
    ('omborchi', "Omborchi"),
    ('buxgalter', "Buxgalter"),
]


class ResUsers(models.Model):
    _inherit = 'res.users'

    zakupka_roli = fields.Selection(
        ZAKUPKA_ROLI, string="Xarid roli",
        help="Ma'lumot uchun. Haqiqiy huquqlar guruhlar orqali beriladi.")
    zakupka_tranzit_id = fields.Many2one(
        'stock.location', string="Tranzit ombori", readonly=True, copy=False,
        help="Zakupchikka biriktirilgan shaxsiy tranzit joyi.")
    zakupka_depozit_id = fields.Many2one(
        'agronova.depozit', string="Depoziti",
        compute='_compute_zakupka_depozit_id',
        help="`agronova_savdo_moliya` dagi depozit — naqd xarid shundan chiqadi.")
    zakupka_orinbosar_id = fields.Many2one(
        'res.users', string="Tasdiqlash o'rinbosari",
        help="Tasdiqlash muddati o'tsa so'rov o'rinbosarga ham ko'rinadi "
             "(TZ 6-bo'lim).")
    zakupka_rahbar_id = fields.Many2one(
        'res.users', string="Yuqori rahbar",
        help="Ikkinchi muddat ham o'tsa so'rov shu odamga eskalatsiya "
             "qilinadi. O'z-o'zini tasdiqlash bloklanganda ham so'rov shu "
             "odamga ko'tariladi.")

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + [
            'zakupka_roli', 'zakupka_tranzit_id', 'zakupka_depozit_id',
            'zakupka_orinbosar_id', 'zakupka_rahbar_id',
        ]

    def _compute_zakupka_depozit_id(self):
        Depozit = self.env['agronova.depozit'].sudo()
        for user in self:
            user.zakupka_depozit_id = Depozit.search(
                [('user_id', '=', user.id)], limit=1)

    # ------------------------------------------------------------ tranzit
    def action_zakupka_tranzit_yaratish(self):
        """Tanlangan zakupchiklarga tranzit ombori ochadi (B01)."""
        Location = self.env['stock.location']
        for user in self:
            if not user.zakupka_tranzit_id:
                user.sudo().zakupka_tranzit_id = Location._agronova_tranzit_olish(user)
        return True

    def _agronova_tranzit(self):
        """Zakupchik tranziti; yo'q bo'lsa yaratadi va biriktiradi."""
        self.ensure_one()
        if not self.zakupka_tranzit_id:
            self.sudo().zakupka_tranzit_id = self.env[
                'stock.location']._agronova_tranzit_olish(self)
        return self.zakupka_tranzit_id

    def _agronova_depozit(self):
        self.ensure_one()
        depozit = self.zakupka_depozit_id
        if not depozit:
            raise UserError(_(
                "«%s» uchun depozit ochilmagan — naqd xarid rasmiylashtirib "
                "bo'lmaydi. Moliya bo'limida depozit oching.", self.name))
        return depozit

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        users.filtered(
            lambda u: u.has_group('agronova_zakupka.group_zakupka_zakupchik')
        ).action_zakupka_tranzit_yaratish()
        return users
