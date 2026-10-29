# -*- coding: utf-8 -*-
"""
Hikvision Face ID Device Model

Bu model barcha Hikvision mixin'larini birlashtiradi va
asosiy fields'larni o'z ichiga oladi.
"""

import logging

from odoo import models, fields

_logger = logging.getLogger(__name__)


class HikvisionDevice(models.Model):
    """Hikvision Face ID qurilmasini boshqarish modeli"""
    
    _name = 'hikvision.device'
    _description = 'Hikvision Face ID Device'
    _inherit = [
        'hikvision.api.mixin',
        'hikvision.sync.mixin',
        'hikvision.attendance.mixin',
        'hikvision.cron.mixin',
    ]

    # =====================================================
    # FIELDS
    # =====================================================
    name = fields.Char(string='Device Name', required=True)
    ip_address = fields.Char(string='IP Address', required=True)
    port = fields.Integer(string='Port', default=80, required=True)
    # Ulanish ma'lumotlari faqat HR menejerlariga. ACL qator darajasida
    # ishlaydi, maydon darajasida emas - groups= bo'lmasa istalgan
    # foydalanuvchi RPC orqali read(['password']) qila oladi.
    username = fields.Char(
        string='Username', required=True, groups='hr.group_hr_manager')
    password = fields.Char(
        string='Password', required=True, groups='hr.group_hr_manager')
    device_id = fields.Char(string='Device ID')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('error', 'Error')
    ], string='Status', default='draft')
    last_fetch_time = fields.Datetime(string='Last Fetch Time')

    # Avtomatik sinxronizatsiya switch
    auto_sync_enabled = fields.Boolean(
        string='Avtomatik Sinxronlash',
        default=True,
        help="Yoqilganda: Xodim yaratilganda, o'zgartirilganda yoki o'chirilganda "
             "avtomatik qurilmaga sinxronlanadi.\n"
             "O'chirilganda: Faqat qo'lda 'Xodimlarni Yuklash' tugmasi orqali sinxronlanadi."
    )

    # =====================================================
    # HELPER METHODS
    # =====================================================
    
    def _notify(self, title, message, notif_type='success', sticky=False):
        """Foydalanuvchiga xabar ko'rsatish."""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': message,
                'type': notif_type,
                'sticky': sticky,
            }
        }

    # =====================================================
    # DEVICE ACTIONS
    # =====================================================
    
    def action_test_connection(self):
        """Qurilma bilan ulanishni test qilish"""
        self.ensure_one()
        try:
            self._make_request('GET', 'System/deviceInfo')
            self.state = 'confirmed'
            return self._notify('Muvaffaqiyatli', 'Qurilmaga ulanish muvaffaqiyatli!')
        except Exception as e:
            self.state = 'error'
            return self._notify('Ulanish xatosi', str(e), 'danger', sticky=True)
