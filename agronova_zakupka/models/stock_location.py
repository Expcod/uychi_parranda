# -*- coding: utf-8 -*-
"""Zakupchik tranzit ombori (TZ 7-bo'lim).

Sotib olingan, lekin omborchi hali qabul qilmagan tovar zakupchikning
shaxsiy tranzit joyida turadi. Joy `usage='internal'` — ya'ni tovar
korxona balansida qoladi va zakupchik zimmasida ko'rinadi.

Joylar xmlid orqali emas, **koddan** yaratiladi: `stock.warehouse0` kabi
tashqi xmlid ba'zi bazalarda (restore qilingan nusxalarda) mavjud emas.
"""
from odoo import _, api, fields, models

TRANZIT_ROOT_NOMI = "Zakupchik tranziti"


class StockLocation(models.Model):
    _inherit = 'stock.location'

    zakupchik_tranzit = fields.Boolean(
        "Zakupchik tranzit ombori", index='btree_not_null',
        help="Sotib olingan, omborchi qabul qilmagan tovar shu joyda turadi.")
    zakupchik_user_id = fields.Many2one(
        'res.users', string="Zakupchik", index='btree_not_null',
        help="Tranzit joy qaysi zakupchikning zimmasida.")

    _zakupchik_tranzit_uniq = models.Constraint(
        'UNIQUE(zakupchik_user_id)',
        "Har bir zakupchikka faqat bitta tranzit ombori bo'ladi.",
    )

    @api.model
    def _agronova_tranzit_root(self, company):
        """Barcha zakupchik tranzitlari uchun ota «view» joy."""
        root = self.sudo().search([
            ('name', '=', TRANZIT_ROOT_NOMI),
            ('usage', '=', 'view'),
            ('company_id', '=', company.id),
        ], limit=1)
        if not root:
            root = self.sudo().create({
                'name': TRANZIT_ROOT_NOMI,
                'usage': 'view',
                'location_id': False,
                'company_id': company.id,
            })
        return root

    @api.model
    def _agronova_tranzit_olish(self, user, company=None, yaratish=True):
        """Zakupchikning tranzit joyi; bo'lmasa yaratadi."""
        company = company or user.company_id or self.env.company
        joy = self.sudo().search([
            ('zakupchik_user_id', '=', user.id),
            ('company_id', '=', company.id),
        ], limit=1)
        if joy or not yaratish:
            return joy
        root = self._agronova_tranzit_root(company)
        return self.sudo().create({
            'name': _("Tranzit — %s", user.name),
            'usage': 'internal',
            'location_id': root.id,
            'company_id': company.id,
            'zakupchik_tranzit': True,
            'zakupchik_user_id': user.id,
        })
