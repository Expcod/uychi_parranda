# -*- coding: utf-8 -*-
"""Sex (bino) — ona tovuqlar boqiladigan obyekt.

Arxitektura qarori (2-bo'lim): Boquvdagi **holat** mexanizmi (Dizinfeksiya /
Aktiv / No aktiv) bu yerda YO'Q. Sex doim band deb hisoblanadi, doimiy
xarajat filtersiz barcha sexlarga m² bo'yicha taqsimlanadi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AgroNovaOnaTovuqSex(models.Model):
    _name = 'agronova.ona_tovuq.sex'
    _description = "Ona tovuq sexi"
    _inherit = ['agronova.analitik.mixin', 'mail.thread']
    _order = 'code, name'

    # Sex analitik hisobi loyihada allaqachon ishlatilayotgan «Bino (seh)»
    # rejasiga tushadi — Boquv bilan bir xil kesim bo'lishi uchun.
    _agronova_analytic_plan_name = "Bino (seh)"

    name = fields.Char("Sex nomi", required=True, tracking=True)
    code = fields.Char("Kod", required=True, tracking=True)
    maydoni = fields.Float(
        "Maydoni (m²)", required=True, tracking=True,
        help="Doimiy xarajatlar shu maydon nisbatida taqsimlanadi — "
             "shuning uchun majburiy.")
    sigimi = fields.Integer(
        "Sig'imi (bosh)", tracking=True,
        help="Sexga sig'adigan maksimal bosh soni.")
    mas_ul_xodim_id = fields.Many2one(
        'hr.employee', string="Mas'ul xodim (operator)", tracking=True,
        help="Shu sexga biriktirilgan operator. Uning ish haqi to'g'ridan-"
             "to'g'ri shu sexning aktiv partiyasiga yoziladi.")
    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)
    warehouse_id = fields.Many2one(
        'stock.warehouse', string="Ombor",
        domain="[('company_id', '=', company_id)]",
        help="Sex lokatsiyasi shu ombor ostida ochiladi.")
    location_id = fields.Many2one(
        'stock.location', string="Ombor lokatsiyasi", readonly=True, copy=False,
        help="Sex yaratilganda avtomat ochiladi. Yem, dori va vaksina shu "
             "joydan hisobdan chiqadi.")
    active = fields.Boolean("Faol", default=True)

    # --- bog'liq yozuvlar
    ostirish_partiya_ids = fields.One2many(
        'agronova.ona_tovuq.partiya.ostirish', 'sex_id', string="Jo'ja o'stirish partiyalari")
    tuxum_partiya_ids = fields.One2many(
        'agronova.ona_tovuq.partiya.tuxum', 'sex_id', string="Ona tovuq partiyalari")
    aktiv_partiya_id = fields.Many2one(
        'agronova.ona_tovuq.partiya.tuxum', string="Aktiv ona tovuq partiyasi",
        compute='_compute_aktiv', store=True)
    aktiv_ostirish_id = fields.Many2one(
        'agronova.ona_tovuq.partiya.ostirish', string="Aktiv jo'ja o'stirish partiyasi",
        compute='_compute_aktiv', store=True)
    joriy_son = fields.Integer(
        "Joriy bosh soni", compute='_compute_aktiv', store=True,
        help="Sexdagi aktiv partiyalarning jami bosh soni.")

    # --- ko'rsatkichlar
    jami_xarajat = fields.Monetary(
        "Jami xarajat", compute='_compute_moliya',
        help="Sexning o'z analitik hisobi va undagi partiyalar xarajati.")
    jami_daromad = fields.Monetary("Jami daromad", compute='_compute_moliya')
    foyda = fields.Monetary("Foyda / zarar", compute='_compute_moliya')
    rentabellik = fields.Float("Rentabellik (%)", compute='_compute_moliya')

    _code_uniq = models.Constraint(
        'UNIQUE(code, company_id)', "Bu kodli sex allaqachon mavjud.")
    _maydoni_musbat = models.Constraint(
        'CHECK (maydoni > 0)', "Sex maydoni (m²) noldan katta bo'lishi kerak.")

    # ------------------------------------------------------------- compute
    @api.depends('ostirish_partiya_ids.holat', 'ostirish_partiya_ids.joriy_son',
                 'tuxum_partiya_ids.holat', 'tuxum_partiya_ids.joriy_son')
    def _compute_aktiv(self):
        for sex in self:
            tuxum = sex.tuxum_partiya_ids.filtered(lambda p: p.holat == 'active')
            ostirish = sex.ostirish_partiya_ids.filtered(lambda p: p.holat == 'active')
            sex.aktiv_partiya_id = tuxum[:1]
            sex.aktiv_ostirish_id = ostirish[:1]
            sex.joriy_son = sum(tuxum.mapped('joriy_son')) + sum(ostirish.mapped('joriy_son'))

    def _compute_moliya(self):
        for sex in self:
            # O'stirish va tuxum partiyalari — alohida modellar, `|` bilan
            # birlashtirib bo'lmaydi; ketma-ket aylanamiz.
            xarajat = sex._agronova_analytic_amount(sign='cost')
            daromad = sex._agronova_analytic_amount(sign='income')
            for partiyalar in (sex.ostirish_partiya_ids, sex.tuxum_partiya_ids):
                for p in partiyalar:
                    xarajat += p._agronova_analytic_amount(sign='cost')
                    daromad += p._agronova_analytic_amount(sign='income')
            sex.jami_xarajat = xarajat
            sex.jami_daromad = daromad
            sex.foyda = daromad - xarajat
            sex.rentabellik = (sex.foyda / daromad * 100.0) if daromad else 0.0

    # ------------------------------------------------------------- yaratish
    def _agronova_analytic_vals(self):
        vals = super()._agronova_analytic_vals()
        vals['name'] = _("Ona tovuq — %s", self.name)
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        sexlar = super().create(vals_list)
        sexlar._ensure_location()
        return sexlar

    def _ensure_location(self):
        """Har sexga ombor lokatsiyasi ochadi (bo'lsa — mavjudini bog'laydi).

        Bazada sexlar allaqachon `OTOV/Zaxira/Sex/1-sex` ko'rinishida
        yaratilgan bo'lishi mumkin — shuning uchun avval nom bo'yicha
        qidiriladi, faqat topilmasa yangisi ochiladi.
        """
        Location = self.env['stock.location'].sudo()
        for sex in self.filtered(lambda s: not s.location_id):
            warehouse = sex.warehouse_id or self.env['stock.warehouse'].search(
                [('company_id', '=', sex.company_id.id)], limit=1)
            if not warehouse:
                continue
            if not sex.warehouse_id:
                sex.warehouse_id = warehouse
            parent = Location.search([
                ('location_id', 'child_of', warehouse.lot_stock_id.id),
                ('name', '=ilike', 'Sex'),
                ('usage', '=', 'internal'),
            ], limit=1) or warehouse.lot_stock_id
            mavjud = Location.search([
                ('location_id', '=', parent.id),
                ('name', '=ilike', sex.name),
            ], limit=1)
            sex.location_id = mavjud or Location.create({
                'name': sex.name,
                'location_id': parent.id,
                'usage': 'internal',
                'company_id': sex.company_id.id,
            })

    @api.constrains('sigimi', 'joriy_son')
    def _check_sigimi(self):
        for sex in self:
            if sex.sigimi and sex.joriy_son > sex.sigimi:
                raise ValidationError(_(
                    "«%(sex)s» sexining sig'imi %(sigim)s bosh, hozir esa "
                    "%(joriy)s bosh joylashtirilgan.",
                    sex=sex.name, sigim=sex.sigimi, joriy=sex.joriy_son))

    # ------------------------------------------------------------ yordamchi
    def _production_location(self):
        """Sarf hisobdan chiqadigan virtual «ishlab chiqarish» joyi."""
        self.ensure_one()
        loc = self.env['stock.location'].sudo().search([
            ('usage', '=', 'production'),
            ('company_id', 'in', [self.company_id.id, False]),
        ], limit=1)
        if not loc:
            loc = self.env['stock.location'].sudo().create({
                'name': _("Ona tovuq ishlab chiqarish"),
                'usage': 'production',
                'company_id': self.company_id.id,
            })
        return loc

    def _tuxum_ombori(self):
        """Yig'ilgan tuxum tushadigan lokatsiya."""
        self.ensure_one()
        warehouse = self.warehouse_id
        if not warehouse:
            return self.env['stock.location'].browse()
        loc = self.env['stock.location'].sudo().search([
            ('location_id', 'child_of', warehouse.lot_stock_id.id),
            ('name', 'ilike', 'Tuxum'),
            ('usage', '=', 'internal'),
        ], limit=1)
        return loc or warehouse.lot_stock_id
