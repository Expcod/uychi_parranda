# -*- coding: utf-8 -*-
"""Jo'jani Boquvga berish (TZ 8-band).

⚠️ TZ da bu **ichki xarid** deb ko'rsatilgan, oddiy ko'chirish emas.
Sababi: inkubatsiya va boquv bosqichlarining tannarxi alohida ko'rinishi
kerak. Oddiy ko'chirishda jo'ja Boquvga o'z tannarxida o'tib ketardi va
Inkubatoriyaning natijasi hech qachon shakllanmasdi — bo'lim ishlaganmi
yoki zarar qilganmi bilib bo'lmasdi.

Shuning uchun bu hujjat ikki narsani birga qiladi:

* **boshqaruv hisobi** — Inkubatoriyada kelishilgan narxda daromad,
  jo'janing tannarxi esa chiqim (`tannarxga=False`, ya'ni birlik
  tannarxini oshirmaydi);
* **ombor harakati** — jo'ja Inkubatoriya omboridan korxonalararo transit
  orqali Boquv omboriga o'tadi va u yerda **ichki narxda** turadi.

QQS hisob-fakturasi rasmiylashtirilmaydi: bu tashqi sotuv emas.

Ichki marja realizatsiya qilinmagan bo'lsa (jo'ja hali sotilmagan)
konsolidatsiyada `agronova.ink.elminatsiya` orqali chiqarib tashlanadi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AgroNovaInkIchkiSotuv(models.Model):
    _name = 'agronova.ink.ichki_sotuv'
    _description = "Inkubatoriya — jo'jani ichki berish"
    _inherit = ['mail.thread', 'agronova.tannarx.qulf.mixin',
                'agronova.otkazma.mixin', 'agronova.mahsulot.filtr.mixin']
    _agronova_tannarx_fields = ('tannarx_summa',)
    _order = 'date desc, id desc'

    @api.model_create_multi
    def create(self, vals_list):
        # Jo'jani Boquvga berish endi standart Sotuv (sale.order) orqali
        # qilinadi (`agronova_ink_ichki_otkazma.py`) — tovar harakati va
        # boshqaruv hisobi bitta zanjirda yuradi. Bu hujjat yangi yozuv
        # ochmaydi; eski yozuvlar tarix uchun joyida qoladi.
        raise UserError(_(
            "Jo'jani Boquvga berish endi oddiy Sotuv (sale.order) orqali "
            "qilinadi — mijoz qilib Boquv korxonasini tanlang va qatorda "
            "inkubatsiya partiyasini ko'rsating."))

    name = fields.Char("Hujjat", default=lambda s: _("Yangi"), copy=False,
                       readonly=True, index=True)
    date = fields.Date("Sana", required=True, default=fields.Date.context_today,
                       tracking=True)
    partiya_id = fields.Many2one(
        'agronova.ink.partiya', string="Inkubatsiya partiyasi", required=True,
        ondelete='restrict', index=True, tracking=True,
        domain="[('holat', 'in', ['inkubatsiyada', 'done'])]")
    company_id = fields.Many2one(
        'res.company', string="Korxona", related='partiya_id.company_id',
        store=True, readonly=True)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)
    qabul_company_id = fields.Many2one(
        'res.company', string="Qabul qiluvchi bo'lim", required=True,
        tracking=True, help="Odatda Boquv korxonasi.")
    qabul_warehouse_id = fields.Many2one(
        'stock.warehouse', string="Qabul qiluvchi ombor", tracking=True,
        domain="[('company_id', '=', qabul_company_id)]",
        help="Jo'ja qaysi filial omboriga tushadi. Boquvda yettita filial "
             "bor — qaysi biriga yuborilayotgani shu yerda ko'rsatiladi.")
    qabul_ombor_soni = fields.Integer(
        "Qabul qiluvchidagi ombor soni", compute='_compute_qabul_ombor_soni')
    product_id = fields.Many2one(
        'product.product', string="Jo'ja mahsuloti", required=True)
    product_domain = fields.Binary(compute='_compute_product_domain')

    def _compute_product_domain(self):
        domain = self._agronova_mahsulot_domain(
            'joja', [('is_storable', '=', True)])
        for s_ in self:
            s_.product_domain = domain

    dona = fields.Integer("Miqdori (dona)", required=True, tracking=True)
    birlik_narx = fields.Monetary("Ichki narx (1 dona)", required=True,
                                  tracking=True)
    summa = fields.Monetary("Summa", compute='_compute_summa', store=True)
    tannarx_summa = fields.Monetary(
        "Tannarx summasi", readonly=True, copy=False,
        help="Partiyaning 1 dona jo'ja tannarxi × miqdor. "
             "Qo'lda kiritilmaydi.")
    marja = fields.Monetary("Ichki marja", compute='_compute_summa', store=True)

    holat = fields.Selection([
        ('draft', "Qoralama"),
        ('done', "Berildi"),
    ], string="Holati", default='draft', required=True, tracking=True,
        copy=False)

    move_id = fields.Many2one('stock.move', string="Chiqim harakati",
                              readonly=True, copy=False)
    move_kirim_id = fields.Many2one('stock.move', string="Kirim harakati",
                                    readonly=True, copy=False)
    lot_id = fields.Many2one('stock.lot', string="Lot", readonly=True,
                             copy=False)
    izoh = fields.Text("Izoh")

    _dona_musbat = models.Constraint(
        'CHECK (dona > 0)', "Miqdor noldan katta bo'lishi kerak.")

    # ------------------------------------------------------------- compute
    @api.depends('dona', 'birlik_narx', 'tannarx_summa')
    def _compute_summa(self):
        for s in self:
            s.summa = s.dona * s.birlik_narx
            s.marja = s.summa - s.tannarx_summa

    @api.depends('name', 'qabul_company_id', 'dona')
    def _compute_display_name(self):
        for s in self:
            s.display_name = "%s · %s · %s dona" % (
                s.name or "", s.qabul_company_id.name or "", s.dona)

    @api.depends('qabul_company_id')
    def _compute_qabul_ombor_soni(self):
        Wh = self.env['stock.warehouse'].sudo()
        for rec in self:
            rec.qabul_ombor_soni = Wh.search_count(
                [('company_id', '=', rec.qabul_company_id.id)]
            ) if rec.qabul_company_id else 0

    @api.onchange('qabul_company_id')
    def _onchange_qabul_company(self):
        """Bitta ombor bo'lsa o'zi tanlanadi, ko'p bo'lsa tanlash qoladi."""
        self.qabul_warehouse_id = False
        if not self.qabul_company_id:
            return
        omborlar = self.env['stock.warehouse'].sudo().search(
            [('company_id', '=', self.qabul_company_id.id)])
        if len(omborlar) == 1:
            self.qabul_warehouse_id = omborlar

    @api.onchange('birlik_narx', 'partiya_id')
    def _onchange_narx(self):
        """Tannarxdan past ichki narx — ogohlantirish."""
        if (self.partiya_id.tannarx_1_joja and self.birlik_narx
                and self.birlik_narx < self.partiya_id.tannarx_1_joja):
            return {'warning': {
                'title': _("Narx tannarxdan past"),
                'message': _(
                    "Ichki narx %(n).2f, 1 dona jo'ja tannarxi esa "
                    "%(t).2f so'm. Bo'lim zarar bilan beryapti.",
                    n=self.birlik_narx, t=self.partiya_id.tannarx_1_joja),
            }}

    # ------------------------------------------------------------ yaratish
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _("Yangi"):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'agronova.ink.ichki_sotuv') or _("Yangi")
        return super().create(vals_list)

    # -------------------------------------------------------------- amallar
    def action_berish(self):
        for s in self:
            if s.holat != 'draft':
                raise UserError(_("Faqat qoralama hujjat o'tkaziladi."))
            s._tekshir_miqdor()
            s._tekshir_ombor()
            s._tannarxni_hisoblash()
            s._ombor_harakati()
            s._analitik_yozish()
            s.holat = 'done'
            s.partiya_id.message_post(body=_(
                "%(dona)s dona jo'ja «%(qabul)s» bo'limiga berildi "
                "(%(summa).2f so'm).",
                dona=s.dona,
                qabul=(s.qabul_warehouse_id.display_name
                       or s.qabul_company_id.name),
                summa=s.summa))
        return True

    def _tekshir_miqdor(self):
        self.ensure_one()
        qoldiq = self.partiya_id.qoldiq_joja
        if self.dona > qoldiq:
            raise UserError(_(
                "«%(p)s» partiyasida %(qoldiq)s dona jo'ja qolgan, "
                "%(kerak)s dona berib bo'lmaydi.",
                p=self.partiya_id.name, qoldiq=qoldiq, kerak=self.dona))
        return True

    def _tekshir_ombor(self):
        """Bir necha filial bo'lsa, qaysi biriga tushishi aytilishi shart.

        Aks holda jo'ja doim birinchi filialga tushib qolardi va keyin
        qaysi filialda nechta bosh borligi noto'g'ri chiqardi.
        """
        self.ensure_one()
        if self.qabul_warehouse_id:
            return True
        omborlar = self.env['stock.warehouse'].sudo().search(
            [('company_id', '=', self.qabul_company_id.id)])
        if len(omborlar) > 1:
            raise UserError(_(
                "«%(korxona)s» da %(soni)s ta filial-ombor bor — jo'ja "
                "qaysi biriga tushishini ko'rsating.",
                korxona=self.qabul_company_id.display_name,
                soni=len(omborlar)))
        return True

    def _tannarxni_hisoblash(self):
        self.ensure_one()
        self._tannarx_yozish().tannarx_summa = (
            self.partiya_id.tannarx_1_joja * self.dona)
        return True

    def _tannarx_1_birlik(self):
        self.ensure_one()
        return self.tannarx_summa / self.dona if self.dona else 0.0

    def _manba_location(self):
        """Jo'ja Inkubatoriya omborida qoldiqda turadi."""
        self.ensure_one()
        wh = self.env['stock.warehouse'].sudo().search(
            [('company_id', '=', self.company_id.id)], limit=1)
        if not wh:
            raise UserError(_("Inkubatoriya korxonasida ombor topilmadi."))
        return wh.lot_stock_id

    def _ombor_harakati(self):
        self.ensure_one()
        transit = self._transit_location()
        out = self._chiqim(self._manba_location(), transit)
        self.move_id = out
        # Chiqimda qaysi lotlardan olingan bo'lsa, kirimda ham o'shalar —
        # jo'ja qaysi inkubatsiya partiyasidan kelgani Boquvda ham ko'rinadi.
        taqsimot = [(ml.lot_id.name, ml.quantity)
                    for ml in out.move_line_ids if ml.quantity]
        if not taqsimot:
            taqsimot = [("%s/%s" % (self.partiya_id.name, self.date),
                         self.dona)]
        move_in, lot = self._kirim(transit, self._qabul_location(), taqsimot)
        self.move_kirim_id = move_in
        self.lot_id = lot
        return True

    def _analitik_yozish(self):
        """Bo'lim daromadi va tannarx chiqimini analitik hisobga yozadi."""
        self.ensure_one()
        partiya = self.partiya_id
        partiya._agronova_post_analytic(
            name=_("Ichki sotuv: jo'ja (%s dona)", self.dona),
            amount=self.summa, date=self.date, unit_amount=self.dona,
            product=self.product_id,
            extra={'company_id': self.company_id.id})
        if self.tannarx_summa:
            partiya._agronova_post_analytic(
                name=_("Ichki sotuv tannarxi (%s dona)", self.dona),
                amount=-self.tannarx_summa, date=self.date,
                # Sotilgan jo'janing tannarxi birlik tannarxini
                # oshirmaydi — aks holda har berishda tannarx o'sib ketardi.
                tannarxga=False,
                extra={'company_id': self.company_id.id})
        return True
