# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import AccessError


class ResUsers(models.Model):
    _inherit = 'res.users'

    app_access_grid_placeholder = fields.Char(
        string="Ilovalar",
        compute='_compute_app_access_grid_placeholder',
        help="Faqat 'app_access_grid' widget uchun bog'lanish nuqtasi — qiymati ishlatilmaydi.",
    )

    def _compute_app_access_grid_placeholder(self):
        for rec in self:
            rec.app_access_grid_placeholder = ''

    def get_app_access_grid(self):
        """Barcha ilovalarni (top-level menyular) va shu foydalanuvchi ularga
        kira oladimi-yo'qmi holatini qaytaradi (custom OWL widget uchun).

        Ko'rinish = guruh ruxsati bor VA foydalanuvchi cheklanmagan
        (app_restricted_user_ids ro'yxatida yo'q).
        """
        self.ensure_one()
        apps = self.env['ir.ui.menu'].sudo().search([
            ('parent_id', '=', False),
            ('web_icon_data', '!=', False),
        ], order='sequence, id')
        result = []
        for app in apps:
            groups = app.group_ids
            group_ok = (not groups) or bool(groups & self.group_ids)
            restricted = self.id in app.app_restricted_user_ids.ids
            result.append({
                'id': app.id,
                'name': app.name,
                'has_access': group_ok and not restricted,
                # Barcha ilovalar toggle qilinadi — cheklash mexanizmi guruhdan
                # qat'i nazar ishlaydi.
                'toggleable': True,
            })
        return result

    def toggle_app_access(self, menu_id, enable):
        """Shu foydalanuvchi uchun berilgan ilovani yoqadi/o'chiradi.

        O'chirish  (enable=False): foydalanuvchi menyu qora ro'yxatiga
            qo'shiladi — guruh implikatsiyasidan qat'i nazar ilova yashiriladi.
        Yoqish     (enable=True):  qora ro'yxatdan chiqariladi va (agar menyuda
            guruh bo'lsa) kerakli guruh beriladi, shunda ilova haqiqatan ochiladi.
        """
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_("Faqat administrator ilova kirish huquqini o'zgartira oladi."))

        menu = self.env['ir.ui.menu'].sudo().browse(menu_id)
        if not menu.exists():
            return {'ok': False}

        if enable:
            menu.write({'app_restricted_user_ids': [(3, self.id)]})
            if menu.group_ids:
                self.sudo().write({'group_ids': [(4, menu.group_ids[0].id)]})
        else:
            menu.write({'app_restricted_user_ids': [(4, self.id)]})
        return {'ok': True}
