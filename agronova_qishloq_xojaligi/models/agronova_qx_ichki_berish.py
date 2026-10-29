# -*- coding: utf-8 -*-
"""Ichki tranzaksiya — hosilni boshqa bo'limga berish (TZ 9.2, 10-band).

Asosiy yo'nalish: **Qishloq xo'jaligi → Yem zavodi**. Bu tashqi sotuv emas,
shuning uchun QQS hisob-fakturasi rasmiylashtirilmaydi. Ammo boshqaruv
hisobida ikki tomonlama yozuv bo'lishi kerak:

* qishloq xo'jaligi partiyasiga **daromad**;
* o'sha partiyadan **tannarx chiqimi**.

Shunda yerning rentabelligi to'g'ri chiqadi: hosil yem zavodiga ketgan
bo'lsa ham, u tekinga ketmaydi.

Mahsulotning fizik harakati Odoo omborida alohida o'tkazma bilan
rasmiylashtiriladi (filiallar orasida — intercompany).
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AgroNovaQxIchkiBerish(models.Model):
    _name = 'agronova.qx.ichki_berish'
    _description = "Qishloq xo'jaligi — ichki berish"
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    name = fields.Char(
        "Hujjat", default=lambda self: _("Yangi"), copy=False, readonly=True,
        index=True)
    date = fields.Date(
        "Sana", required=True, default=fields.Date.context_today, tracking=True)
    partiya_id = fields.Many2one(
        'agronova.qx.partiya', string="Ekin partiyasi", required=True,
        ondelete='restrict', index=True)
    yer_id = fields.Many2one(
        related='partiya_id.yer_id', string="Yer", store=True, readonly=True)
    qabul_qiluvchi = fields.Selection(
        [('yem_zavod', "Yem zavodi"),
         ('qx_ichki', "Qishloq xo'jaligi ichida"),
         ('boshqa', "Boshqa bo'lim")],
        string="Qabul qiluvchi", required=True, default='yem_zavod',
        tracking=True)
    product_id = fields.Many2one(
        'product.product', string="Mahsulot", required=True,
        compute='_compute_product', store=True, precompute=True,
        readonly=False,
        domain="[('is_storable', '=', True)]",
        help="Partiya ekinining hosil mahsuloti avtomat qo'yiladi.")
    miqdor_kg = fields.Float(
        "Miqdor (kg)", required=True, digits='Product Unit')
    birlik_narx = fields.Monetary(
        "1 kg ichki narxi", required=True,
        help="Bo'limlar o'rtasida kelishilgan narx. Tannarxdan past bo'lsa "
             "ogohlantirish chiqadi.")

    # Partiyaning holati — qoralama paytida ham ko'rinishi kerak, aks holda
    # narxni qanday belgilashni bilib bo'lmaydi.
    partiya_tannarx_1_kg = fields.Monetary(
        "Partiya tannarxi (1 kg)", related='partiya_id.tannarx_1_kg',
        readonly=True,
        help="Hosil olinmagan partiyada 0 bo'ladi — tannarx hosilga "
             "bo'linadi, hosil yo'q bo'lsa bo'luvchi ham yo'q.")
    partiya_hosil_kg = fields.Float(
        "Partiyadan olingan hosil (kg)", related='partiya_id.olingan_hosil_kg',
        readonly=True)
    partiya_qoldiq_kg = fields.Float(
        "Partiya qoldig'i (kg)", related='partiya_id.qoldiq_kg', readonly=True,
        help="Shu partiyadan yana qancha berish mumkin.")
    partiya_xarajat = fields.Monetary(
        "Partiyaning jami xarajati", related='partiya_id.jami_xarajat',
        readonly=True)

    summa = fields.Monetary("Daromad summasi", compute='_compute_summa',
                            store=True)
    tannarx_qotgan = fields.Monetary(
        "O'tkazishdagi tannarx", readonly=True, copy=False,
        help="Hujjat o'tkazilganda qotadi va keyin o'zgarmaydi. "
             "Hisobotlarda shu maydon ishlatiladi.")
    # SAQLANMAYDI: partiyaning `tannarx_1_kg` maydoni ham saqlanmaydi
    # (u analitik qatorlardan hisoblanadi), shuning uchun undan o'zgarish
    # signali kelmaydi. Saqlansa qoralamadagi qiymat eskirib qolardi —
    # o'qish paytida hisoblanadi.
    tannarx_summa = fields.Monetary(
        "Tannarx summasi", compute='_compute_tannarx',
        help="Qoralamada — partiyaning joriy tannarxi bo'yicha taxmin. "
             "O'tkazilgandan keyin qotgan qiymat ko'rsatiladi.")
    ichki_foyda = fields.Monetary("Marja", compute='_compute_tannarx')
    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True, readonly=True,
        store=True, precompute=True, compute='_compute_company_id')
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)
    holat = fields.Selection(
        [('draft', "Qoralama"), ('done', "O'tkazilgan")],
        string="Holati", default='draft', required=True, tracking=True,
        copy=False)
    izoh = fields.Text("Izoh")

    _miqdor_musbat = models.Constraint(
        'CHECK (miqdor_kg > 0)', "Miqdor noldan katta bo'lishi kerak.")

    @api.depends('partiya_id')
    def _compute_company_id(self):
        for r in self:
            r.company_id = r.partiya_id.company_id or self.env.company

    @api.depends('partiya_id')
    def _compute_product(self):
        for r in self:
            if not r.product_id and r.partiya_id.ekin_id.product_id:
                r.product_id = r.partiya_id.ekin_id.product_id

    def _compute_tannarx(self):
        for r in self:
            if r.holat == 'done':
                r.tannarx_summa = r.tannarx_qotgan
            else:
                r.tannarx_summa = r.miqdor_kg * r.partiya_id.tannarx_1_kg
            r.ichki_foyda = r.summa - r.tannarx_summa

    @api.depends('miqdor_kg', 'birlik_narx')
    def _compute_summa(self):
        for r in self:
            r.summa = r.miqdor_kg * r.birlik_narx

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Yem zavodiga berish endi standart Sotuv (sale.order) orqali
            # ishlaydi (`agronova_qx_ichki_otkazma.py`) — u yerda tovar
            # harakati va pul yozuvi bitta zanjirda yuradi. Bu hujjat
            # o'sha yo'nalish uchun yangi yozuv ochmaydi; eski yozuvlar
            # tarixiy hisobot uchun joyida qoladi.
            raise UserError(_(
                "Ichki berish endi oddiy Sotuv (sale.order) orqali "
                "qilinadi — mijoz qilib qabul qiluvchi korxonani "
                "tanlang va qatorda ekin partiyasini ko'rsating."))
            if not vals.get('name') or vals['name'] == _("Yangi"):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'agronova.qx.ichki_berish') or _("Yangi")
        return super().create(vals_list)

    def action_otkazish(self):
        for r in self:
            if r.holat == 'done':
                continue
            # Qoldiq — olingan hosil minus ilgari berilgani. Faqat
            # «olingan hosil» ga solishtirish yetarli emas: bir partiyadan
            # bir necha marta berilsa, jami hosildan oshib ketardi.
            if r.miqdor_kg > r.partiya_id.qoldiq_kg:
                raise UserError(_(
                    "«%(p)s» partiyasida %(qoldiq).0f kg qoldiq bor "
                    "(%(hosil).0f kg olingan, %(berilgan).0f kg berilgan), "
                    "%(kerak).0f kg berib bo'lmaydi.",
                    p=r.partiya_id.name, qoldiq=r.partiya_id.qoldiq_kg,
                    hosil=r.partiya_id.olingan_hosil_kg,
                    berilgan=r.partiya_id.berilgan_kg, kerak=r.miqdor_kg))
            tannarx = r.partiya_id.tannarx_1_kg * r.miqdor_kg
            r.tannarx_qotgan = tannarx

            qabul = dict(r._fields['qabul_qiluvchi'].selection)
            r.partiya_id._agronova_post_analytic(
                name=_("Ichki berish: %(qabul)s (%(kg).0f kg)",
                       qabul=qabul.get(r.qabul_qiluvchi, ""), kg=r.miqdor_kg),
                amount=r.summa,                  # daromad — musbat
                date=r.date,
                unit_amount=r.miqdor_kg,
                product=r.product_id,
                extra={'company_id': r.company_id.id},
            )
            if tannarx:
                r.partiya_id._agronova_post_analytic(
                    name=_("Ichki berish tannarxi (%(kg).0f kg)",
                           kg=r.miqdor_kg),
                    amount=-tannarx,             # tannarx chiqimi — manfiy
                    date=r.date,
                    tannarxga=False,             # birlik tannarxini oshirmaydi
                    extra={'company_id': r.company_id.id},
                )
            if r.birlik_narx < r.partiya_id.tannarx_1_kg:
                r.message_post(body=_(
                    "DIQQAT: ichki narx (%(n).2f) 1 kg tannarxidan "
                    "(%(t).2f) past.",
                    n=r.birlik_narx, t=r.partiya_id.tannarx_1_kg))
            r.holat = 'done'
        return True
