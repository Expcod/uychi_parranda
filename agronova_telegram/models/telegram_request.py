# -*- coding: utf-8 -*-
"""Botga ulanish arizasi.

Ilgari xodim `/start` bosganda bot unga chat ID raqamini ko'rsatardi va
xodim uni administratorga o'zi yuborishi kerak edi. Raqam uzun, xato
ko'chiriladi, kim yuborganini bilib bo'lmasdi.

Endi xodim ism-familiyasini yozadi va «Jo'natish» ni bosadi — Odooda shu
ro'yxatga bitta ariza tushadi. Administrator arizani xodimga biriktiradi,
shundan keyin bot ishlay boshlaydi.

Ro'yxatda Telegram username va Telegram profildagi ism ham ko'rinadi:
xodim o'zini kim deb yozganini profildagi nom bilan solishtirib bo'ladi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SssTelegramRequest(models.Model):
    _name = 'agronova.telegram.request'
    _description = "Telegram botga ulanish arizasi"
    _order = 'create_date desc'
    _rec_name = 'ism'

    ism = fields.Char("Ism-familiya", required=True,
                      help="Xodim botga o'zi yozgan ism-familiya.")
    chat_id = fields.Char("Chat ID", required=True, index='btree_not_null',
                          readonly=True)
    telegram_username = fields.Char("Telegram username", readonly=True,
                                    help="@ belgisisiz. Profilda bo'lmasligi "
                                         "ham mumkin.")
    telegram_ism = fields.Char("Telegram profildagi ism", readonly=True,
                               help="Telegram akkauntdagi ism va familiya — "
                                    "xodim yozgani bilan solishtirish uchun.")
    employee_id = fields.Many2one('hr.employee', string="Xodim",
                                  help="Ariza qaysi xodimga tegishli.")
    holat = fields.Selection([
        ('yangi', "Yangi"),
        ('biriktirilgan', "Biriktirilgan"),
        ('rad', "Rad etilgan"),
    ], string="Holat", default='yangi', required=True, index=True)
    izoh = fields.Text("Izoh")

    _chat_id_uniq = models.Constraint(
        'UNIQUE(chat_id)',
        "Bu Telegram akkauntdan ariza allaqachon tushgan.",
    )

    # ------------------------------------------------------------- bot API
    @api.model
    def tg_register(self, chat_id, ism, username=None, telegram_ism=None):
        """Bot: ariza qoldiradi.

        Idempotent — xodim `/start` ni qayta bossa yangi ariza yaratilmaydi,
        borlari yangilanadi. Xodim biriktirilgan bo'lsa ariza olinmaydi:
        bot allaqachon ishlaydi.
        """
        chat_id = str(chat_id)
        employee = self.env['hr.employee'].sudo().search(
            [('telegram_chat_id', '=', chat_id)], limit=1)
        if employee:
            return {'ok': True, 'holat': 'biriktirilgan', 'name': employee.name}

        ariza = self.sudo().search([('chat_id', '=', chat_id)], limit=1)
        vals = {'ism': ism, 'telegram_username': username or False,
                'telegram_ism': telegram_ism or False}
        if ariza:
            # Rad etilgan ariza qayta yuborilsa yana ko'rib chiqilsin.
            if ariza.holat == 'rad':
                vals['holat'] = 'yangi'
            ariza.write(vals)
        else:
            vals['chat_id'] = chat_id
            ariza = self.sudo().create(vals)
        self.env['agronova.telegram.log'].tg_log(
            "Botga ulanish arizasi", chat_id=chat_id,
            payload="%s (@%s)" % (ism, username or '—'))
        return {'ok': True, 'holat': ariza.holat, 'request_id': ariza.id}

    @api.model
    def tg_holat(self, chat_id):
        """Bot: shu chatdan ariza bormi va qaysi holatda."""
        ariza = self.sudo().search([('chat_id', '=', str(chat_id))], limit=1)
        if not ariza:
            return {'ok': True, 'holat': False}
        return {'ok': True, 'holat': ariza.holat, 'ism': ariza.ism}

    # --------------------------------------------------------------- amallar
    def action_biriktir(self):
        """Arizani xodimga biriktiradi — shundan keyin bot ishlaydi."""
        for ariza in self:
            if not ariza.employee_id:
                raise UserError(_(
                    "Avval «%(ism)s» arizasida xodimni tanlang.",
                    ism=ariza.ism))
            band = self.env['hr.employee'].sudo().search([
                ('telegram_chat_id', '=', ariza.chat_id),
                ('id', '!=', ariza.employee_id.id),
            ], limit=1)
            if band:
                raise UserError(_(
                    "Bu Telegram akkaunt «%(xodim)s» ga biriktirilgan. "
                    "Avval o'sha kartochkadan uzing.", xodim=band.name))
            ariza.employee_id.sudo().write({
                'telegram_chat_id': ariza.chat_id,
                'telegram_username': ariza.telegram_username,
            })
            ariza.holat = 'biriktirilgan'
            self.env['agronova.telegram.log'].tg_log(
                "Bot akkaunti biriktirildi", chat_id=ariza.chat_id,
                employee_id=ariza.employee_id.id, payload=ariza.ism)
        return True

    def action_rad(self):
        for ariza in self:
            ariza.holat = 'rad'
            self.env['agronova.telegram.log'].tg_log(
                "Bot arizasi rad etildi", chat_id=ariza.chat_id,
                payload=ariza.ism, success=False)
        return True

    def action_qayta_ochish(self):
        self.write({'holat': 'yangi'})
        return True
