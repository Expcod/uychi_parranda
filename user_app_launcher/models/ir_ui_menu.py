# -*- coding: utf-8 -*-
from odoo import fields, models


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    # Har bir foydalanuvchi uchun menyu (ilova) qora ro'yxati. Guruh
    # implikatsiyasidan qat'i nazar ishlaydi — restrict qilingan foydalanuvchiga
    # menyu umuman ko'rsatilmaydi.
    app_restricted_user_ids = fields.Many2many(
        'res.users',
        'ir_ui_menu_app_restrict_rel',
        'menu_id', 'user_id',
        string="Cheklangan foydalanuvchilar",
        help="Bu menyu (ilova) ko'rsatilmaydigan foydalanuvchilar.",
    )

    def _filter_visible_menus(self):
        """Joriy foydalanuvchi uchun cheklangan menyularni yashiradi.

        Administrator (base.group_system) hamma narsani ko'radi.
        """
        menus = super()._filter_visible_menus()
        if self.env.user.has_group('base.group_system'):
            return menus
        uid = self.env.user.id
        return menus.filtered(lambda m: uid not in m.app_restricted_user_ids.ids)
