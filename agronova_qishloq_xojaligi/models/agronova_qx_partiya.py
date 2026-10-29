# -*- coding: utf-8 -*-
"""Ekin yetishtirish partiyasi (TZ 3-band).

Yerda yangi ekin boshlanganda ochiladi va butun sikli ifodalaydi: urug'dan
hosilgacha. Barcha xarajat shunga yig'iladi, tannarx shundan chiqadi:

    1 kg tannarxi = partiyaning jami xarajati / olingan hosil (kg)

Ona Tovuqdan farqi — **mavsumiylik**. Tovuq har kuni tuxum beradi, ekin esa
yiliga bir-ikki marta hosil beradi. Shuning uchun kunlik jurnal yo'q: yozuv
faqat ish bo'lganda kiritiladi (ekish, o'g'itlash, sug'orish, o'rim).
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AgroNovaQxPartiya(models.Model):
    _name = 'agronova.qx.partiya'
    _description = "Qishloq xo'jaligi — ekin partiyasi"
    _inherit = ['agronova.analitik.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'ekish_sana desc, id desc'
    _rec_names_search = ['name', 'yer_id.name', 'ekin_id.name']

    _agronova_analytic_plan_name = "Ekin partiyasi"

    name = fields.Char(
        "Partiya raqami", default=lambda self: _("Yangi"),
        copy=False, readonly=True, index=True)
    yer_id = fields.Many2one(
        'agronova.qx.yer', string="Yer maydoni", required=True, tracking=True,
        ondelete='restrict', index=True)
    ekin_id = fields.Many2one(
        'agronova.qx.ekin', string="Ekin turi", required=True, tracking=True,
        ondelete='restrict')
    maydoni_ga = fields.Float(
        "Ekilgan maydon (gektar)", digits=(12, 2), tracking=True,
        help="Bo'sh qoldirilsa yerning to'liq maydoni olinadi.")
    ekish_sana = fields.Date(
        "Ekilgan sana", required=True, tracking=True,
        default=fields.Date.context_today)
    yopilish_sana = fields.Date("Yopilgan sana", readonly=True, copy=False)
    reja_hosil_kg = fields.Float(
        "Rejalashtirilgan hosil (kg)", tracking=True, digits='Product Unit')
    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True, readonly=True,
        store=True, precompute=True, compute='_compute_company_id',
        help="Yer qaysi korxonada bo'lsa — partiya ham o'shanda.")
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)
    holat = fields.Selection(
        [('draft', "Qoralama"), ('active', "Yetishtirilmoqda"),
         ('closed', "Yopilgan")],
        string="Holati", default='draft', required=True, tracking=True,
        copy=False)

    ish_ids = fields.One2many(
        'agronova.qx.ish', 'partiya_id', string="Dalada bajarilgan ishlar")
    hosil_ids = fields.One2many(
        'agronova.qx.hosil', 'partiya_id', string="Olingan hosil")
    berish_ids = fields.One2many(
        'agronova.qx.ichki_berish', 'partiya_id', string="Ichki berishlar")
    # Alohida compute metodi: qolgan hosil maydonlari `store=True`, bu esa
    # saqlanmaydi. Bitta metodda turishsa Odoo registri ogohlantiradi —
    # saqlanmagan maydonni o'qish saqlanganlarini qayta hisoblab yuboradi.
    ish_soni = fields.Integer("Ish yozuvlari", compute='_compute_ish_soni')

    olingan_hosil_kg = fields.Float(
        "Olingan hosil (kg)", compute='_compute_hosil', store=True,
        digits='Product Unit')
    berilgan_kg = fields.Float(
        "Berilgan / sotilgan (kg)", compute='_compute_hosil', store=True,
        digits='Product Unit',
        help="Ichki berish hujjatlari bo'yicha chiqib ketgan miqdor.")
    qoldiq_kg = fields.Float(
        "Qoldiq (kg)", compute='_compute_hosil', store=True,
        digits='Product Unit',
        help="Olingan hosil minus berilgan miqdor.")
    hosildorlik = fields.Float(
        "Hosildorlik (kg/ga)", compute='_compute_hosil', store=True)
    reja_bajarilishi = fields.Float(
        "Reja bajarilishi (%)", compute='_compute_hosil', store=True)

    jami_xarajat = fields.Monetary("Jami xarajat", compute='_compute_moliya')
    jami_daromad = fields.Monetary("Jami daromad", compute='_compute_moliya')
    foyda = fields.Monetary("Foyda / zarar", compute='_compute_moliya')
    rentabellik = fields.Float("Rentabellik (%)", compute='_compute_moliya')
    tannarx_1_kg = fields.Monetary(
        "1 kg tannarxi", compute='_compute_moliya', readonly=True,
        help="Jami xarajat / olingan hosil. Qo'lda kiritilmaydi.")
    tannarx_qotgan = fields.Monetary(
        "Yopilishdagi 1 kg tannarxi", readonly=True, copy=False,
        help="Partiya yopilganda qotadi va keyin o'zgarmaydi.")

    izoh = fields.Text("Izoh")

    # ------------------------------------------------------------- compute
    @api.depends('yer_id')
    def _compute_company_id(self):
        for p in self:
            p.company_id = p.yer_id.company_id or self.env.company

    @api.depends('hosil_ids.miqdor_kg', 'hosil_ids.holat',
                 'maydoni_ga', 'yer_id.maydoni_ga', 'reja_hosil_kg',
                 'berish_ids.miqdor_kg', 'berish_ids.holat')
    def _compute_hosil(self):
        for p in self:
            hosil = p.hosil_ids.filtered(lambda h: h.holat == 'done')
            p.olingan_hosil_kg = sum(hosil.mapped('miqdor_kg'))
            berilgan = p.berish_ids.filtered(lambda b: b.holat == 'done')
            p.berilgan_kg = sum(berilgan.mapped('miqdor_kg'))
            p.qoldiq_kg = p.olingan_hosil_kg - p.berilgan_kg
            maydon = p.maydoni_ga or p.yer_id.maydoni_ga
            p.hosildorlik = (p.olingan_hosil_kg / maydon) if maydon else 0.0
            p.reja_bajarilishi = (
                p.olingan_hosil_kg / p.reja_hosil_kg * 100.0
                if p.reja_hosil_kg else 0.0)

    @api.depends('ish_ids')
    def _compute_ish_soni(self):
        for p in self:
            p.ish_soni = len(p.ish_ids)

    def _compute_moliya(self):
        for p in self:
            xarajat = p._agronova_analytic_amount(sign='cost')
            daromad = p._agronova_analytic_amount(sign='income')
            p.jami_xarajat = xarajat
            p.jami_daromad = daromad
            p.foyda = daromad - xarajat
            p.rentabellik = (p.foyda / daromad * 100.0) if daromad else 0.0
            # Tannarx faqat ishlab chiqarish xarajatidan: ichki berishda
            # yozilgan tannarx chiqimi bu bazaga kirmaydi.
            ishlab_chiqarish = p._agronova_analytic_amount(
                sign='cost', faqat_tannarx=True)
            p.tannarx_1_kg = (ishlab_chiqarish / p.olingan_hosil_kg
                              if p.olingan_hosil_kg else 0.0)

    def _agronova_analytic_vals(self):
        vals = super()._agronova_analytic_vals()
        vals['name'] = self.name if self.name != _("Yangi") else self.display_name
        return vals

    @api.depends('name', 'yer_id', 'ekin_id')
    def _compute_display_name(self):
        for p in self:
            qism = [p.name or ""]
            if p.ekin_id:
                qism.append(p.ekin_id.name)
            if p.yer_id:
                qism.append(p.yer_id.name)
            p.display_name = " · ".join(x for x in qism if x)

    # ------------------------------------------------------------- yaratish
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _("Yangi"):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'agronova.qx.partiya') or _("Yangi")
        return super().create(vals_list)

    # --------------------------------------------------------------- qulf
    def _tekshir_ochiq(self, amal=None):
        """Yopilgan partiyaga yozuv qo'shishni taqiqlaydi."""
        for p in self:
            if p.holat == 'closed':
                raise UserError(_(
                    "«%(nom)s» partiyasi yopilgan — unga yangi yozuv "
                    "qo'shilmaydi.%(amal)s",
                    nom=p.name, amal=(_(" (%s)", amal) if amal else "")))
        return True

    def _agronova_post_analytic(self, *args, **kwargs):
        """Yopilgan partiyada TANNARX o'zgarmaydi, lekin SOTUV davom etadi.

        Hosil yig'ilgach partiya yopiladi va 1 kg tannarxi qotadi. Ammo don
        omborda turaveradi va oylar davomida bo'limlarga beriladi yoki
        sotiladi — bu normal holat. Shuning uchun faqat tannarx bazasiga
        kiradigan **xarajat** bloklanadi; daromad va sotilgan mahsulot
        tannarxi (`tannarxga=False`) yopilgandan keyin ham yoziladi.
        """
        amount = kwargs.get('amount')
        if amount is None and len(args) >= 2:
            amount = args[1]
        if kwargs.get('tannarxga', True) and (amount or 0.0) < 0:
            self._tekshir_ochiq()
        return super()._agronova_post_analytic(*args, **kwargs)

    # -------------------------------------------------------------- holatlar
    def action_faollashtirish(self):
        for p in self:
            if p.holat != 'draft':
                raise UserError(_("Faqat qoralama partiya faollashtiriladi."))
            band = p.yer_id.partiya_ids.filtered(
                lambda x, p=p: x.holat == 'active' and x.id != p.id)
            if band:
                raise UserError(_(
                    "«%(yer)s» yerida «%(p)s» partiyasi hali yopilmagan — "
                    "bitta yerda bir vaqtda bitta ekin yetishtiriladi.",
                    yer=p.yer_id.name, p=band[0].name))
            if not p.maydoni_ga:
                p.maydoni_ga = p.yer_id.maydoni_ga
            p.holat = 'active'
        return True

    def action_close(self):
        """Sikl tugadi — tannarxni qotiradi."""
        for p in self:
            if p.holat != 'active':
                raise UserError(_("Faqat yetishtirilayotgan partiya yopiladi."))
            qoralama = p.hosil_ids.filtered(lambda h: h.holat == 'draft')
            if qoralama:
                raise UserError(_(
                    "«%s» partiyasida omborga kirim qilinmagan hosil hujjati "
                    "bor — avval uni yakunlang.", p.name))
            p.tannarx_qotgan = p.tannarx_1_kg
            p.yopilish_sana = fields.Date.context_today(p)
            p.holat = 'closed'
            p.message_post(body=_(
                "Partiya yopildi. Olingan hosil: %(h).0f kg, "
                "1 kg tannarxi: %(t).2f",
                h=p.olingan_hosil_kg, t=p.tannarx_qotgan))
        return True

    def action_qayta_ochish(self):
        for p in self:
            if p.holat != 'closed':
                raise UserError(_("Faqat yopilgan partiya qayta ochiladi."))
            p.holat = 'active'
            p.tannarx_qotgan = 0.0
            p.yopilish_sana = False
        return True
