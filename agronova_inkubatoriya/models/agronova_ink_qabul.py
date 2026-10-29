# -*- coding: utf-8 -*-
"""Tuxum qabuli (TZ 3-band).

Zanjirning birinchi bo'g'ini: tuxum qayerdan keldi, qancha keldi va
qancha turadi. Shu uch narsa keyin jo'ja tannarxining asosini tashkil
qiladi.

## Tuxum jismonan qachon ko'chadi

Ona tovuqning ichki sotuv hujjati tasdiqlanganda tuxum **o'sha zahoti**
Inkubatoriya omboriga ko'chadi (`agronova.ona_tovuq.ichki_sotuv._kirim`).
Shuning uchun bu hujjat ombor harakati yaratmaydi — aks holda tuxum ikki
marta kirim bo'lib qolardi.

Bu hujjatning vazifasi boshqa: tuxumning **kelib chiqishini va qiymatini**
inkubatsiya partiyasiga bog'lash. Tasdiqlanganda qiymat partiyaning
analitik hisobiga xarajat bo'lib tushadi — jo'ja tannarxining birinchi va
eng katta tarkibiy qismi.

Tashqi ta'minotchidan sotib olingan tuxum uchun ham shu hujjat
ishlatiladi, faqat unda ombor kirimini Purchase qiladi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

MANBA = [
    ('ichki', "Ona tovuq filialidan"),
    ('tashqi', "Tashqi ta'minotchidan"),
]


class AgroNovaInkQabul(models.Model):
    _name = 'agronova.ink.qabul'
    _description = "Inkubatoriya — tuxum qabuli"
    # Tannarx qulfi qo'yilmaydi: `qiymat` bu yerda hisoblanadigan tannarx
    # emas, tashqaridan keladigan **ma'lumot** — ichki manbada Ona tovuq
    # hujjatidan, tashqi manbada xarid narxidan. Tasdiqlangandan keyin
    # o'zgarmasligini holat readonly'si ta'minlaydi.
    _inherit = ['mail.thread', 'agronova.mahsulot.filtr.mixin']
    _order = 'date desc, id desc'

    name = fields.Char("Hujjat", default=lambda s: _("Yangi"), copy=False,
                       readonly=True, index=True)
    date = fields.Date("Qabul sanasi", required=True,
                       default=fields.Date.context_today, tracking=True)
    manba = fields.Selection(MANBA, string="Kelib chiqishi", required=True,
                             default='ichki', tracking=True)
    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)

    # --- kelib chiqishi
    ot_ichki_sotuv_id = fields.Many2one(
        'agronova.ona_tovuq.ichki_sotuv', string="Ona tovuq hujjati (arxiv)",
        readonly=True, copy=False, ondelete='set null',
        help="Eski oqimdagi ichki sotuv hujjati. Yangi qabullarda "
             "to'ldirilmaydi — o'rniga Xarid/qabul hujjati ko'rsatiladi.")
    # Yangi zanjir: sotuv (jo'natuvchi bo'lim) -> xarid -> qabul -> shu
    # hujjat -> inkubatsiya partiyasi. Tashqi ta'minotchidan olishda ham
    # xuddi shu maydonlar to'ladi — ikkala manba bir xil ishlaydi.
    picking_id = fields.Many2one(
        'stock.picking', string="Qabul hujjati", readonly=True, copy=False,
        ondelete='set null', index=True,
        help="Tuxum jismonan qaysi ombor hujjati bilan kirgan.")
    purchase_id = fields.Many2one(
        'purchase.order', string="Xarid", related='picking_id.purchase_id',
        readonly=True, store=True)
    ot_partiya_id = fields.Many2one(
        'agronova.ona_tovuq.partiya.tuxum', string="Tuxum partiyasi",
        readonly=True, copy=False,
        help="Tuxum qaysi ona tovuq partiyasidan olingan.")
    ot_company_id = fields.Many2one(
        'res.company', string="Jo'natuvchi filial", readonly=True,
        help="Tuxum qaysi ona tovuq filialidan kelgan.")
    partner_id = fields.Many2one(
        'res.partner', string="Ta'minotchi",
        help="Tashqi manbada to'ldiriladi.")

    # --- miqdor va qiymat
    product_id = fields.Many2one(
        'product.product', string="Tuxum mahsuloti", required=True)
    # Hujjatda faqat tuxum ko'rinsin: 190 dan ortiq nomenklatura ichidan
    # dori yoki yem tanlab yuborilmasin. Qamrovi «Mahsulot guruhlari»
    # ma'lumotnomasida sozlanadi.
    product_domain = fields.Binary(compute='_compute_product_domain')

    def _compute_product_domain(self):
        domain = self._agronova_mahsulot_domain(
            'tuxum', [('is_storable', '=', True)])
        for q in self:
            q.product_domain = domain
    dona = fields.Integer("Tuxum miqdori (dona)", required=True, tracking=True)
    qiymat = fields.Monetary(
        "Qiymati", tracking=True,
        help="Ichki manbada Ona tovuq hujjatidan avtomat keladi. "
             "Tashqi manbada xarid narxi yoziladi.")
    narx_1_dona = fields.Monetary("1 dona narxi", compute='_compute_narx',
                                  store=True)

    partiya_id = fields.Many2one(
        'agronova.ink.partiya', string="Inkubatsiya partiyasi",
        ondelete='restrict', tracking=True,
        domain="[('holat', '=', 'draft'), ('company_id', '=', company_id)]",
        help="Tuxum qaysi partiyaga qo'yiladi. Partiya inkubatsiyaga "
             "qo'yilgunga qadar o'zgartirilishi mumkin.")

    holat = fields.Selection([
        ('draft', "Qoralama"),
        ('done', "Qabul qilindi"),
        ('cancel', "Bekor qilindi"),
    ], string="Holati", default='draft', required=True, tracking=True,
        copy=False)
    analytic_line_id = fields.Many2one(
        'account.analytic.line', string="Analitik qator", readonly=True,
        copy=False)
    izoh = fields.Text("Izoh")

    _dona_musbat = models.Constraint(
        'CHECK (dona > 0)', "Tuxum miqdori noldan katta bo'lishi kerak.")

    # ------------------------------------------------------------- compute
    @api.depends('qiymat', 'dona')
    def _compute_narx(self):
        for q in self:
            q.narx_1_dona = q.qiymat / q.dona if q.dona else 0.0

    @api.depends('name', 'ot_company_id', 'partner_id', 'dona')
    def _compute_display_name(self):
        for q in self:
            manba = (q.ot_company_id.name or q.partner_id.name
                     or dict(MANBA).get(q.manba, ""))
            q.display_name = "%s · %s · %s dona" % (q.name or "", manba, q.dona)

    # ------------------------------------------------------------ yaratish
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _("Yangi"):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'agronova.ink.qabul') or _("Yangi")
        return super().create(vals_list)

    # -------------------------------------------------------------- amallar
    def action_qabul(self):
        """Qabulni tasdiqlaydi va qiymatni partiya xarajatiga yozadi."""
        for q in self:
            if q.holat != 'draft':
                raise UserError(_("Faqat qoralama hujjat tasdiqlanadi."))
            if not q.partiya_id:
                raise UserError(_(
                    "«%s» hujjatida inkubatsiya partiyasi tanlanmagan.",
                    q.name))
            if q.partiya_id.holat != 'draft':
                raise UserError(_(
                    "«%(p)s» partiyasi allaqachon inkubatsiyaga qo'yilgan — "
                    "unga yangi tuxum qo'shilmaydi.", p=q.partiya_id.name))
            if not q.qiymat:
                # Qiymatsiz tuxum tannarxni buzadi: jo'ja bepul chiqqandek
                # ko'rinadi. Ichki manbada qiymat Ona tovuqdan keladi.
                raise UserError(_(
                    "«%s» hujjatida tuxum qiymati nol — jo'ja tannarxi "
                    "noto'g'ri chiqadi.", q.name))
            q.holat = 'done'
            q._analitik_yozish()
            q.partiya_id.message_post(body=_(
                "%(dona)s dona tuxum qabul qilindi (%(hujjat)s).",
                dona=q.dona, hujjat=q.name))
        return True

    def action_bekor(self):
        for q in self:
            if q.partiya_id.holat not in ('draft',):
                raise UserError(_(
                    "«%s» partiyasi inkubatsiyaga qo'yilgan — qabulni bekor "
                    "qilib bo'lmaydi.", q.partiya_id.name))
            if q.analytic_line_id:
                q.analytic_line_id.sudo().unlink()
            q.holat = 'cancel'
        return True

    def action_draft(self):
        for q in self:
            if q.holat != 'cancel':
                raise UserError(_("Faqat bekor qilingan hujjat qaytariladi."))
            q.holat = 'draft'
        return True

    def _analitik_yozish(self):
        self.ensure_one()
        line = self.partiya_id._agronova_post_analytic(
            name=_("Tuxum qabuli: %(dona)s dona", dona=self.dona),
            amount=-self.qiymat,
            date=self.date,
            unit_amount=self.dona,
            product=self.product_id,
            extra={'company_id': self.company_id.id},
        )
        self.analytic_line_id = line
        return line
