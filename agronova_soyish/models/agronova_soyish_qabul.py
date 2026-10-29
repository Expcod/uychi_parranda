# -*- coding: utf-8 -*-
"""Tovuqlarni qabul qilish va tortish (TZ 3-band).

So'yish sexiga tovuq kelganda birinchi hujjat shu. Tarozida tortiladi va
tizim o'zi hisoblaydi:

    Netto = Brutto - Tara
    O'rtacha 1 dona vazni = Netto / tovuq soni

Tovuq **donada** sanaladi, lekin **kilogrammda** tortiladi. Odooda bitta
mahsulotning bitta o'lchov birligi bo'ladi, shuning uchun tirik tovuq
donada yuritiladi, vazn esa shu hujjatda alohida maydonlarda saqlanadi.
Chiqim foizi (tushka kg / tirik kg) aynan shu vazndan hisoblanadi.

Ikki manba (TZ 2-band):
* **ichki boquv** — o'z fermamizdan kelgan, tannarxi bilan;
* **tashqi mijoz** — davvalchilikka kelgan, mulki mijozniki bo'lib qoladi,
  bizga faqat so'yish xizmati haqi tegadi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

MANBA = [
    ('ichki', "Ichki boquvdan"),
    ('tashqi', "Tashqi mijozdan"),
]


class AgroNovaSoyishQabul(models.Model):
    _name = 'agronova.soyish.qabul'
    _description = "So'yish — qabul qilish va tortish"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sana desc, id desc'

    name = fields.Char(
        "Hujjat", default=lambda self: _("Yangi"), copy=False, readonly=True,
        index=True)
    sana = fields.Datetime(
        "Kelgan sana va vaqt", required=True, tracking=True,
        default=fields.Datetime.now)
    manba = fields.Selection(
        MANBA, string="Tovuq kelib chiqishi", required=True, default='ichki',
        tracking=True)
    partner_id = fields.Many2one(
        'res.partner', string="Mijoz / ferma", tracking=True,
        help="Tashqi manbada majburiy — mahsulot kimning mulki ekani "
             "shundan aniqlanadi.")
    product_id = fields.Many2one(
        'product.product', string="Tirik tovuq mahsuloti", required=True,
        domain="[('is_storable', '=', True)]",
        help="Ombor hisobida qaysi mahsulot sifatida yuritiladi.")

    transport = fields.Char("Transport", tracking=True)
    haydovchi = fields.Char("Haydovchi", tracking=True)

    # --- tortish
    tovuq_soni = fields.Integer("Tovuq soni (dona)", required=True, tracking=True)
    brutto_kg = fields.Float(
        "Brutto og'irlik (kg)", required=True, tracking=True,
        digits='Product Unit', help="Transport bilan birga tortilgan vazn.")
    tara_kg = fields.Float(
        "Tara og'irligi (kg)", tracking=True, digits='Product Unit',
        help="Bo'sh transport va qafaslar vazni.")
    netto_kg = fields.Float(
        "Netto og'irlik (kg)", compute='_compute_tortish', store=True,
        digits='Product Unit')
    ortacha_vazn_kg = fields.Float(
        "1 dona o'rtacha vazni (kg)", compute='_compute_tortish', store=True,
        digits='Product Unit')

    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)
    holat = fields.Selection(
        [('draft', "Qoralama"), ('done', "Qabul qilingan")],
        string="Holati", default='draft', required=True, tracking=True,
        copy=False)
    partiya_id = fields.Many2one(
        'agronova.soyish.partiya', string="Partiya", readonly=True, copy=False)
    izoh = fields.Text("Izoh")

    _tovuq_musbat = models.Constraint(
        'CHECK (tovuq_soni > 0)', "Tovuq soni noldan katta bo'lishi kerak.")
    _brutto_musbat = models.Constraint(
        'CHECK (brutto_kg > 0)', "Brutto og'irlik noldan katta bo'lishi kerak.")

    # ------------------------------------------------------------- compute
    @api.depends('brutto_kg', 'tara_kg', 'tovuq_soni')
    def _compute_tortish(self):
        for q in self:
            q.netto_kg = max(q.brutto_kg - q.tara_kg, 0.0)
            q.ortacha_vazn_kg = (q.netto_kg / q.tovuq_soni
                                 if q.tovuq_soni else 0.0)

    @api.constrains('brutto_kg', 'tara_kg')
    def _check_tara(self):
        for q in self:
            if q.tara_kg >= q.brutto_kg:
                raise ValidationError(_(
                    "Tara og'irligi brutto og'irlikdan kam bo'lishi kerak "
                    "(brutto %(b).1f, tara %(t).1f).",
                    b=q.brutto_kg, t=q.tara_kg))

    @api.constrains('manba', 'partner_id')
    def _check_partner(self):
        for q in self:
            if q.manba == 'tashqi' and not q.partner_id:
                raise ValidationError(_(
                    "Tashqi mijozdan kelgan tovuqda mijoz ko'rsatilishi "
                    "shart — mahsulot uning mulki bo'lib qoladi."))

    # ------------------------------------------------------------- yaratish
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _("Yangi"):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'agronova.soyish.qabul') or _("Yangi")
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('agronova_soyish_post'):
            for q in self:
                if q.holat == 'done' and set(vals) - {
                        'izoh', 'message_ids', 'message_follower_ids'}:
                    raise UserError(_(
                        "«%s» qabul hujjati yakunlangan — tahrirlanmaydi. "
                        "Tortish ma'lumoti tannarx va chiqim foiziga "
                        "ta'sir qiladi.", q.name))
        return super().write(vals)

    def unlink(self):
        for q in self:
            if q.holat == 'done':
                raise UserError(_(
                    "Qabul qilingan hujjat o'chirilmaydi (%s).", q.name))
        return super().unlink()

    # -------------------------------------------------------------- qabul
    def action_qabul(self):
        """Qabulni yakunlaydi va so'yish partiyasini ochadi."""
        for q in self:
            if q.holat == 'done':
                continue
            partiya = self.env['agronova.soyish.partiya'].create({
                'qabul_id': q.id,
                'manba': q.manba,
                'partner_id': q.partner_id.id,
                'product_id': q.product_id.id,
                'tirik_son': q.tovuq_soni,
                'tirik_vazn_kg': q.netto_kg,
                'sana': fields.Date.context_today(q),
            })
            q.with_context(agronova_soyish_post=True).write({
                'partiya_id': partiya.id, 'holat': 'done'})
            q.message_post(body=_(
                "Qabul qilindi: %(son)s dona, netto %(kg).1f kg, "
                "o'rtacha %(o).2f kg. Partiya: %(p)s",
                son=q.tovuq_soni, kg=q.netto_kg, o=q.ortacha_vazn_kg,
                p=partiya.name))
        return True

    def action_open_partiya(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'agronova.soyish.partiya',
            'res_id': self.partiya_id.id,
            'view_mode': 'form',
        }
