# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    telegram_chat_id = fields.Char(
        "Telegram chat ID", copy=False, index='btree_not_null', tracking=True,
        groups="hr.group_hr_user",
        help="Xodim botga /start yozadi, bot chat ID sini ko'rsatadi — "
             "shu raqamni mana shu maydonga kiritasiz.")
    telegram_username = fields.Char(
        "Telegram username", copy=False, groups="hr.group_hr_user")
    telegram_linked = fields.Boolean(
        "Botga ulangan", compute='_compute_telegram_linked', store=True,
        groups="hr.group_hr_user")

    _telegram_chat_id_uniq = models.Constraint(
        'UNIQUE(telegram_chat_id)',
        "Bu Telegram chat ID boshqa xodimga biriktirilgan.",
    )

    @api.depends('telegram_chat_id')
    def _compute_telegram_linked(self):
        for employee in self:
            employee.telegram_linked = bool(employee.telegram_chat_id)

    def action_unlink_telegram(self):
        self.write({'telegram_chat_id': False, 'telegram_username': False})
        return True

    # ------------------------------------------------------------------ bot API
    @api.model
    def tg_whoami(self, chat_id, username=None):
        """Bot: chat egasini aniqlaydi.

        Bog'lanmagan bo'lsa chat_id qaytariladi — xodim uni administratorga
        yuboradi, administrator xodim kartochkasiga kiritadi.
        """
        employee = self._tg_find(chat_id)
        if not employee:
            return self._tg_not_linked(chat_id)
        # Username o'zgargan bo'lsa yangilab qo'yamiz
        if username and employee.telegram_username != username:
            employee.telegram_username = username
        return {'ok': True, 'employee_id': employee.id, 'name': employee.name,
                'job': employee.job_id.name or '',
                'department': employee.department_id.name or ''}

    @api.model
    def _tg_find(self, chat_id):
        """Ichki: chat_id bo'yicha xodim yoki bo'sh recordset."""
        return self.sudo().search([('telegram_chat_id', '=', str(chat_id))], limit=1)

    @api.model
    def _tg_not_linked(self, chat_id):
        """Bog'lanmagan chat uchun yagona javob shakli.

        Xato ko'tarilmaydi — bot foydalanuvchidan ism-familiya so'rashi
        kerak. Ariza allaqachon tushgan bo'lsa `ariza_holati` bilan
        qaytadi: bot uni qayta so'ramasdan «kutib turing» deydi.
        """
        chat_id = str(chat_id)
        ariza = self.env['agronova.telegram.request'].sudo().search(
            [('chat_id', '=', chat_id)], limit=1)
        return {'ok': False, 'not_linked': True, 'chat_id': chat_id,
                'ariza_holati': ariza.holat if ariza else False,
                'error': "Akkaunt bog'lanmagan."}
