# -*- coding: utf-8 -*-
"""Liniya to'xtashlari (TZ 3.4, 13.4)."""
from odoo import _, api, fields, models

SABABLAR = [
    ('uskuna', "Uskuna nosozligi"),
    ('elektr', "Elektr uzilishi"),
    ('xomashyo', "Xomashyo yo'q"),
    ('qadoq', "Qadoq materiali yo'q"),
    ('rejali', "Rejali ta'mir / tozalash"),
    ('xodim', "Xodim yetishmasligi"),
    ('sifat', "Sifat muammosi"),
    ('boshqa', "Boshqa"),
]


class AgroNovaYemToxtash(models.Model):
    _name = 'agronova.yem.toxtash'
    _description = "Yem zavodi — liniya to'xtashi"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'agronova.yem.smena.qulf.mixin']
    _order = 'boshlanish desc'

    name = fields.Char("Nomi", compute='_compute_name', store=True)
    company_id = fields.Many2one('res.company', "Korxona", required=True, default=lambda s: s.env.company)
    liniya_id = fields.Many2one('agronova.yem.liniya', "Liniya", required=True, tracking=True)
    smena_id = fields.Many2one('agronova.yem.smena', "Smena", index='btree_not_null',
                               domain="[('liniya_id', '=', liniya_id)]")
    production_id = fields.Many2one('mrp.production', "Buyurtma")
    boshlanish = fields.Datetime("Boshlandi", required=True, default=fields.Datetime.now, tracking=True)
    tugash = fields.Datetime("Tugadi", tracking=True)
    davomiylik_min = fields.Float("Davomiyligi (daq.)", compute='_compute_davomiylik', store=True,
                                  digits=(16, 0))
    davom_etmoqda = fields.Boolean("Davom etmoqda", compute='_compute_davomiylik', store=True)
    sabab = fields.Selection(SABABLAR, "Sabab", required=True, default='uskuna', tracking=True)
    uskuna = fields.Char("Uskuna / qism", help="Masalan: granulyator, tegirmon, elevator, qadoqlash mashinasi.")
    izoh = fields.Text("Izoh")
    masul_id = fields.Many2one('hr.employee', "Mas'ul")

    @api.depends('liniya_id', 'sabab', 'boshlanish')
    def _compute_name(self):
        sab = dict(SABABLAR)
        for t in self:
            t.name = "%s · %s" % (t.liniya_id.name or '', sab.get(t.sabab, ''))

    @api.depends('boshlanish', 'tugash')
    def _compute_davomiylik(self):
        for t in self:
            if t.boshlanish and t.tugash:
                t.davomiylik_min = max((t.tugash - t.boshlanish).total_seconds() / 60.0, 0.0)
                t.davom_etmoqda = False
            else:
                t.davomiylik_min = 0.0
                t.davom_etmoqda = bool(t.boshlanish)

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._smena_qulf_tekshir()
        recs._smenaga_bogla()
        for t in recs.filtered('davom_etmoqda'):
            t._ogohlantir()
        return recs

    def _smenaga_bogla(self):
        Smena = self.env['agronova.yem.smena']
        for t in self.filtered(lambda r: not r.smena_id):
            sana = fields.Datetime.context_timestamp(t, t.boshlanish).date()
            smena = Smena.search([('liniya_id', '=', t.liniya_id.id), ('sana', '=', sana),
                                  ('state', '=', 'draft')], limit=1)
            if smena:
                t.smena_id = smena

    def _ogohlantir(self):
        guruh = self.env.ref('agronova_yem_zavodi.group_yem_boshliq', raise_if_not_found=False)
        for u in (guruh.user_ids[:3] if guruh else []):
            self.activity_schedule('mail.mail_activity_data_todo', user_id=u.id,
                                   summary=_("Liniya to'xtadi: %s", self.name))

    def action_tugatish(self):
        self.filtered(lambda t: not t.tugash).write({'tugash': fields.Datetime.now()})
        return True
