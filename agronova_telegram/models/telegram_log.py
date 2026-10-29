# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SssTelegramLog(models.Model):
    """Bot orqali o'tgan muhim amallar jurnali.

    TZ M11: «Yuborilgan xabarlar jurnaliga yoziladi». Har bir xarajat, ulanish
    va xatolik shu yerda qoladi — keyin kim nima yuborganini tekshirish uchun.
    """
    _name = 'agronova.telegram.log'
    _description = 'Telegram bot jurnali'
    _order = 'create_date desc'

    name = fields.Char("Amal", required=True)
    chat_id = fields.Char("Chat ID", index='btree_not_null')
    employee_id = fields.Many2one('hr.employee', string="Xodim")
    trip_id = fields.Many2one('agronova.trip', string="Reys")
    expense_id = fields.Many2one('hr.expense', string="Xarajat")
    payload = fields.Text("Ma'lumot")
    success = fields.Boolean("Muvaffaqiyatli", default=True)
    error = fields.Char("Xato")

    @api.model
    def tg_log(self, name, chat_id=None, employee_id=None, trip_id=None,
               expense_id=None, payload=None, success=True, error=None):
        return self.sudo().create({
            'name': name,
            'chat_id': chat_id and str(chat_id) or False,
            'employee_id': employee_id or False,
            'trip_id': trip_id or False,
            'expense_id': expense_id or False,
            'payload': payload or False,
            'success': success,
            'error': error or False,
        }).id
