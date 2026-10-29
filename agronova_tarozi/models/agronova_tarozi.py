# -*- coding: utf-8 -*-
"""Tarozi qurilmasi va undan kelgan ko'rsatkichlar.

Tarozi bilan Odoo o'rtasida **agent** turadi: kichik dastur tarozi
indikatoridan (RS-232/RS-485/TCP) vaznni o'qiydi va Odoo'ga
`/agronova/tarozi/vazn` orqali yuboradi. Odoo tarozining protokolini
bilmaydi — shu sabab har xil ishlab chiqaruvchining tarozisi bir xil
ulanadi, faqat agent o'zgaradi.

Tortish varaqasi vaznni qo'lda emas, shu yerdan oladi: oxirgi **barqaror**
ko'rsatkich va u yetarlicha yangi bo'lsa. Eski ko'rsatkich (masalan agent
uzilib qolgan) olinmaydi — aks holda oldingi mashinaning vazni yozilib
ketardi.
"""
import secrets
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Ko'rsatkich shuncha soniyadan eski bo'lsa tortishga olinmaydi.
YANGI_SONIYA = 120


class AgroNovaTarozi(models.Model):
    _name = 'agronova.tarozi'
    _description = "Tarozi qurilmasi"
    _inherit = ['mail.thread']
    _order = 'sequence, name'

    name = fields.Char("Nomi", required=True, tracking=True)
    kod = fields.Char("Kodi", required=True, copy=False,
                      help="Agent shu kod bilan murojaat qiladi.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', "Korxona", required=True,
                                 default=lambda s: s.env.company)
    turi = fields.Selection([
        ('avto', "Avtomobil tarozisi"),
        ('platforma', "Platforma tarozisi"),
        ('qadoq', "Qadoqlash tarozisi"),
        ('bunker', "Dozalash / bunker tarozisi"),
    ], "Turi", required=True, default='avto', tracking=True)
    protokol = fields.Selection([
        ('rs232', "RS-232"),
        ('rs485', "RS-485"),
        ('tcp', "Ethernet / TCP-IP"),
        ('http', "HTTP agent"),
        ('qolda', "Integratsiyasiz (qo'lda)"),
    ], "Ulanish", required=True, default='tcp', tracking=True)
    manzil = fields.Char("IP / port", help="Agent sozlamasi uchun ma'lumot.")
    joy = fields.Char("Joylashuvi", help="Masalan: kirish darvozasi, qadoqlash liniyasi.")
    max_vazn_kg = fields.Float("Maksimal yuk (kg)", default=60000)
    aniqlik_kg = fields.Float("Bo'lim qiymati (kg)", default=20,
                              help="Tarozining aniqligi. Tafovut chegaralarini "
                                   "belgilashda hisobga olinadi.")
    token = fields.Char("Agent kaliti", copy=False, groups='base.group_system',
                        default=lambda s: secrets.token_urlsafe(24))

    oxirgi_vazn = fields.Float("Oxirgi vazn (kg)", readonly=True, digits=(16, 1))
    oxirgi_vaqt = fields.Datetime("Oxirgi o'qish", readonly=True)
    oxirgi_barqaror = fields.Boolean("Barqaror", readonly=True)
    holat = fields.Selection([
        ('onlayn', "Onlayn"), ('oflayn', "Oflayn"), ('qolda', "Qo'lda"),
    ], "Holati", compute='_compute_holat')
    oqish_ids = fields.One2many('agronova.tarozi.oqish', 'tarozi_id', "O'qishlar")
    tortish_count = fields.Integer(compute='_compute_tortish_count')

    _kod_uniq = models.Constraint('unique(kod, company_id)',
                                  "Tarozi kodi korxona ichida takrorlanmasin.")

    def _compute_holat(self):
        chegara = fields.Datetime.now() - timedelta(seconds=YANGI_SONIYA)
        for t in self:
            if t.protokol == 'qolda':
                t.holat = 'qolda'
            elif t.oxirgi_vaqt and t.oxirgi_vaqt >= chegara:
                t.holat = 'onlayn'
            else:
                t.holat = 'oflayn'

    def _compute_tortish_count(self):
        data = self.env['agronova.tarozi.tortish']._read_group(
            [('tarozi_id', 'in', self.ids)], ['tarozi_id'], ['__count'])
        counts = {t.id: c for t, c in data}
        for t in self:
            t.tortish_count = counts.get(t.id, 0)

    # ------------------------------------------------------------ ko'rsatkich
    def vazn_qabul(self, vazn, barqaror=True):
        """Agentdan kelgan ko'rsatkichni yozadi (controller shu metodni chaqiradi)."""
        self.ensure_one()
        vazn = float(vazn or 0.0)
        if vazn < 0 or (self.max_vazn_kg and vazn > self.max_vazn_kg * 1.2):
            raise UserError(_("Tarozi ko'rsatkichi chegaradan tashqari: %s kg", vazn))
        now = fields.Datetime.now()
        self.sudo().write({
            'oxirgi_vazn': vazn,
            'oxirgi_vaqt': now,
            'oxirgi_barqaror': bool(barqaror),
        })
        self.env['agronova.tarozi.oqish'].sudo().create({
            'tarozi_id': self.id, 'vazn': vazn, 'barqaror': bool(barqaror), 'vaqt': now,
        })
        return True

    def joriy_vazn(self):
        """Tortish uchun yaroqli vazn — barqaror va yangi bo'lishi shart."""
        self.ensure_one()
        if self.protokol == 'qolda':
            raise UserError(_("«%s» integratsiyasiz tarozi — vazn qo'lda kiritiladi.", self.name))
        if not self.oxirgi_vaqt or \
                self.oxirgi_vaqt < fields.Datetime.now() - timedelta(seconds=YANGI_SONIYA):
            raise UserError(_(
                "«%s» tarozisidan yangi ko'rsatkich kelmagan. Agent ishlayotganini "
                "va mashina tarozida turganini tekshiring.", self.name))
        if not self.oxirgi_barqaror:
            raise UserError(_("Vazn hali barqarorlashmagan — bir necha soniya kuting."))
        return self.oxirgi_vazn

    def action_kalit_yangilash(self):
        for t in self:
            t.sudo().token = secrets.token_urlsafe(24)

    def action_tortishlar(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'agronova_tarozi.action_agronova_tarozi_tortish')
        action['domain'] = [('tarozi_id', '=', self.id)]
        action['context'] = {'default_tarozi_id': self.id}
        return action

    # Agentsiz sinov: taqdimot va o'qitishda tarozi ko'rsatkichini qo'lda
    # «yuborish». Faqat tizim administratoriga ko'rinadi.
    sinov_vazn = fields.Float("Sinov ko'rsatkichi (kg)", groups='base.group_system')

    def action_sinov_yuborish(self):
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise UserError(_("Sinov ko'rsatkichini faqat administrator yuboradi."))
        self.vazn_qabul(self.sinov_vazn, barqaror=True)
        return True

    @api.autovacuum
    def _gc_oqishlar(self):
        """Ko'rsatkichlar jurnali faqat 30 kun saqlanadi."""
        chegara = fields.Datetime.now() - timedelta(days=30)
        self.env['agronova.tarozi.oqish'].sudo().search(
            [('vaqt', '<', chegara)]).unlink()


class AgroNovaTaroziOqish(models.Model):
    _name = 'agronova.tarozi.oqish'
    _description = "Tarozi ko'rsatkichi"
    _order = 'vaqt desc, id desc'

    tarozi_id = fields.Many2one('agronova.tarozi', required=True, ondelete='cascade', index=True)
    vaqt = fields.Datetime("Vaqt", required=True, default=fields.Datetime.now)
    vazn = fields.Float("Vazn (kg)", digits=(16, 1))
    barqaror = fields.Boolean("Barqaror")
