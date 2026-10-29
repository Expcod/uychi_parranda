# -*- coding: utf-8 -*-
"""Kunlik obxod — brigaderning bino aylanishi (TZ 10, 11-band).

Brigader kuniga **kamida 3 marta** obxod qiladi. Har obxod alohida yozuv:
sana-vaqt, harorat, jo'jalar holati, yem va suv holati, aniqlangan muammo,
ko'rilgan chora.

Alohida model qilingani sababli «kamida 3 marta» nazorati tabiiy chiqadi
va kuniga 4-5 marta yozish ham cheklanmaydi.

Harorat me'yordan chetlashsa ogohlantirish beriladi (TZ 11-band) — me'yor
`agronova.boquv.normativ` dan olinadi. Normativ kiritilmagan bo'lsa tekshiruv
o'tkazilmaydi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

HOLAT_BAHOSI = [
    ('yaxshi', "Yaxshi"),
    ('qoniqarli', "Qoniqarli"),
    ('yomon', "Yomon"),
]


class AgroNovaBoquvObxod(models.Model):
    _name = 'agronova.boquv.obxod'
    _description = "Boquv — kunlik obxod"
    _inherit = ['mail.thread']
    _order = 'vaqt desc, id desc'

    name = fields.Char("Obxod", compute='_compute_name', store=True)
    vaqt = fields.Datetime(
        "Sana va vaqt", required=True, default=fields.Datetime.now,
        tracking=True, index=True)
    partiya_id = fields.Many2one(
        'agronova.boquv.partiya', string="Partiya", required=True, tracking=True,
        ondelete='cascade', index=True,
        domain="[('holat', '=', 'active')]")
    bino_id = fields.Many2one(
        related='partiya_id.bino_id', string="Bino", store=True, readonly=True)
    filial_id = fields.Many2one(
        related='partiya_id.filial_id', string="Filial", store=True, readonly=True)
    brigadir_id = fields.Many2one(
        'hr.employee', string="Brigader", required=True, tracking=True)
    company_id = fields.Many2one(
        related='partiya_id.company_id', string="Korxona",
        store=True, readonly=True)

    # --- o'lchov va holat
    harorat = fields.Float("Harorat (°C)", digits=(12, 1), tracking=True)
    harorat_holati = fields.Selection(
        [('past', "Me'yordan past"),
         ('normal', "Me'yorda"),
         ('yuqori', "Me'yordan yuqori")],
        string="Harorat baholari", compute='_compute_harorat_holati', store=True,
        help="Normativdagi me'yor bilan solishtiriladi. Normativ "
             "kiritilmagan bo'lsa bo'sh qoladi.")
    namlik = fields.Float("Namlik (%)", digits=(12, 1))
    jojalar_holati = fields.Selection(
        HOLAT_BAHOSI, string="Jo'jalar holati", default='yaxshi', required=True)
    yem_holati = fields.Selection(
        HOLAT_BAHOSI, string="Yem holati", default='yaxshi', required=True)
    suv_holati = fields.Selection(
        HOLAT_BAHOSI, string="Suv holati", default='yaxshi', required=True)
    olgan_joja = fields.Integer(
        "Obxodda aniqlangan o'lik jo'ja",
        help="Ma'lumot uchun. Kunlik jurnaldagi nobud soni rasmiy hisob "
             "hisoblanadi — ikki marta ayrilib ketmasligi uchun.")

    muammo = fields.Text("Aniqlangan muammo")
    chora = fields.Text("Ko'rilgan chora")

    _harorat_oqilona = models.Constraint(
        'CHECK (harorat > -50 AND harorat < 80)',
        "Harorat qiymati oqilona chegarada bo'lsin (−50…+80 °C).")

    # ------------------------------------------------------------- compute
    @api.depends('partiya_id', 'vaqt')
    def _compute_name(self):
        for o in self:
            if o.partiya_id and o.vaqt:
                o.name = "%s / %s" % (
                    o.partiya_id.name,
                    fields.Datetime.context_timestamp(o, o.vaqt).strftime(
                        '%Y-%m-%d %H:%M'))
            else:
                o.name = _("Yangi")

    @api.depends('harorat', 'partiya_id.yosh_kun')
    def _compute_harorat_holati(self):
        Normativ = self.env['agronova.boquv.normativ']
        for o in self:
            yosh = o.partiya_id.yosh_kun
            hmin = Normativ.qiymat('harorat_min', yosh_kun=yosh)
            hmax = Normativ.qiymat('harorat_max', yosh_kun=yosh)
            if not o.harorat or not (hmin or hmax):
                o.harorat_holati = False
            elif hmin and o.harorat < hmin:
                o.harorat_holati = 'past'
            elif hmax and o.harorat > hmax:
                o.harorat_holati = 'yuqori'
            else:
                o.harorat_holati = 'normal'

    @api.onchange('partiya_id')
    def _onchange_partiya(self):
        if self.partiya_id and not self.brigadir_id:
            self.brigadir_id = self.partiya_id.brigadir_id

    @api.constrains('vaqt')
    def _check_vaqt(self):
        for o in self:
            if o.vaqt and o.vaqt > fields.Datetime.now():
                raise ValidationError(_(
                    "Kelajakdagi vaqt bilan obxod qayd etilmaydi."))

    @api.model_create_multi
    def create(self, vals_list):
        obxodlar = super().create(vals_list)
        for o in obxodlar:
            # Me'yordan chetlashish yoki muammo bo'lsa partiyaga xabar.
            if o.harorat_holati in ('past', 'yuqori') or o.muammo:
                o.partiya_id.message_post(body=_(
                    "Obxod (%(vaqt)s): harorat %(harorat)s °C — %(holat)s. "
                    "%(muammo)s",
                    vaqt=o.name,
                    harorat=o.harorat,
                    holat=dict(o._fields['harorat_holati'].selection).get(
                        o.harorat_holati, _("baholanmadi")),
                    muammo=o.muammo or ''))
        return obxodlar
