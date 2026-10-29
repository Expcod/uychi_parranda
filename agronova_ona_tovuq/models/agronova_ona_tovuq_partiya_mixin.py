# -*- coding: utf-8 -*-
"""O'stirish va tuxum partiyalari uchun umumiy skelet.

Ikkalasi ham alohida model (2-bo'lim qarori), lekin bosh soni hisobi,
analitik hisob, xarajat yig'ish va yopilgandan keyingi qulf bir xil —
shu yerda bir marta yozilgan.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AgroNovaOnaTovuqPartiyaMixin(models.AbstractModel):
    _name = 'agronova.ona_tovuq.partiya.mixin'
    _description = "Ona tovuq partiyasi — umumiy skelet"
    _inherit = ['agronova.analitik.mixin', 'agronova.tannarx.qulf.mixin',
                'mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    _agronova_analytic_plan_xmlid = 'agronova_ona_tovuq.analytic_plan_ot_partiya'
    _agronova_analytic_plan_name = "Ona tovuq partiyasi"

    # Partiya raqamining o'zi qaysi sex ekanini bildirmaydi — jurnal
    # to'ldirayotgan operator ro'yxatdan tanlay olmaydi. Shuning uchun
    # ko'rinadigan nomga sex qo'shiladi va sex nomi bo'yicha ham qidiriladi.
    _rec_names_search = ['name', 'sex_id.name']

    name = fields.Char(
        "Partiya raqami", default=lambda self: _("Yangi"),
        copy=False, readonly=True, index=True)
    sex_id = fields.Many2one(
        'agronova.ona_tovuq.sex', string="Sex", required=True, tracking=True,
        ondelete='restrict', index=True)
    zot_id = fields.Many2one(
        'agronova.ona_tovuq.zot', string="Zot", tracking=True, ondelete='restrict')
    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True, readonly=True,
        store=True, precompute=True, compute='_compute_company_id',
        help="Sex qaysi korxonada bo'lsa — partiya ham o'shanda. "
             "Foydalanuvchining joriy korxonasiga bog'liq emas: bosh ofisdan "
             "filial sexiga yozuv kiritilganda ham to'g'ri qoladi.")
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)

    boshlangich_son = fields.Integer("Boshlang'ich bosh soni", tracking=True)
    nobud_son = fields.Integer(
        "Nobud bo'lgan", compute='_compute_son', store=True,
        help="Kunlik jurnaldan yig'iladi.")
    brak_son = fields.Integer(
        "Brak qilingan", compute='_compute_son', store=True)
    chiqim_son = fields.Integer(
        "Chiqib ketgan (sotuv/o'tkazma)", default=0, readonly=True, copy=False,
        help="Ichki sotuv yoki so'yishga o'tkazishda kamaygan bosh soni.")
    joriy_son = fields.Integer(
        "Joriy bosh soni", compute='_compute_son', store=True, tracking=True)
    yashovchanlik = fields.Float(
        "Yashovchanlik (%)", compute='_compute_son', store=True)

    yem_product_id = fields.Many2one(
        'product.product', string="Asosiy yem",
        domain="[('is_storable', '=', True)]",
        help="Kunlik jurnalda kiritilgan yem sarfi shu mahsulotdan hisobdan "
             "chiqadi.")

    # --- moliya (analitik qatorlardan)
    jami_xarajat = fields.Monetary("Jami xarajat", compute='_compute_moliya')
    jami_daromad = fields.Monetary("Jami daromad", compute='_compute_moliya')
    foyda = fields.Monetary("Foyda / zarar", compute='_compute_moliya')
    rentabellik = fields.Float("Rentabellik (%)", compute='_compute_moliya')

    izoh = fields.Text("Izoh")

    # ------------------------------------------------------------- compute
    @api.depends('name', 'sex_id')
    def _compute_display_name(self):
        for p in self:
            p.display_name = ("%s · %s" % (p.name, p.sex_id.name)
                              if p.sex_id else p.name)

    @api.depends('sex_id')
    def _compute_company_id(self):
        for p in self:
            p.company_id = p.sex_id.company_id or self.env.company

    def _jurnal_records(self):
        """Meros oluvchi model o'z kunlik jurnalini qaytaradi."""
        self.ensure_one()
        return self.jurnal_ids

    # Diqqat: `jurnal_ids` abstrakt modelda yo'q (o'stirish va tuxum
    # jurnallari alohida modellar), shuning uchun bog'liqlik ro'yxati
    # meros oluvchi modelda to'ldiriladi.
    @api.depends('boshlangich_son', 'chiqim_son')
    def _compute_son(self):
        for p in self:
            jurnal = p._jurnal_records()
            p.nobud_son = sum(jurnal.mapped('nobud_son'))
            p.brak_son = sum(jurnal.mapped('brak_son'))
            p.joriy_son = (p.boshlangich_son - p.nobud_son
                           - p.brak_son - p.chiqim_son)
            p.yashovchanlik = (
                (p.boshlangich_son - p.nobud_son) / p.boshlangich_son * 100.0
                if p.boshlangich_son else 0.0)

    def _compute_moliya(self):
        for p in self:
            xarajat = p._agronova_analytic_amount(sign='cost')
            daromad = p._agronova_analytic_amount(sign='income')
            p.jami_xarajat = xarajat
            p.jami_daromad = daromad
            p.foyda = daromad - xarajat
            p.rentabellik = (p.foyda / daromad * 100.0) if daromad else 0.0

    def _agronova_analytic_vals(self):
        vals = super()._agronova_analytic_vals()
        vals['name'] = self.name if self.name != _("Yangi") else self.display_name
        return vals

    # --------------------------------------------------------------- qulf
    def _tekshir_ochiq(self, amal=None):
        """Yopilgan partiyaga yozuv qo'shishni taqiqlaydi (TZ talabi)."""
        for p in self:
            if p.holat == 'closed':
                raise UserError(_(
                    "«%(nom)s» partiyasi yopilgan — unga yangi yozuv "
                    "qo'shilmaydi. Tuzatish joriy davr hisobiga o'tkaziladi.%(amal)s",
                    nom=p.name, amal=(_(" (%s)", amal) if amal else "")))
        return True

    def _agronova_post_analytic(self, *args, **kwargs):
        # Yopilgan partiyaga xarajat tushishining oldini oladi — tannarx
        # qotgandan keyin o'zgarmasligi kerak.
        self._tekshir_ochiq()
        return super()._agronova_post_analytic(*args, **kwargs)
