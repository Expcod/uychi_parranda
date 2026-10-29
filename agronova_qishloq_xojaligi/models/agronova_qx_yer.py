# -*- coding: utf-8 -*-
"""Yer maydoni — qishloq xo'jaligining asosiy obyekti (TZ 2-band).

Ona Tovuqdagi **sex** ning aynan analogi: doimiy obyekt, o'z analitik
hisobi va ombor lokatsiyasi bor, ustida partiyalar ketma-ket almashadi.
Farqi — o'lchov m² emas, **gektar**, va bitta yerda bir yilda bir necha
ekin yetishtirilishi mumkin (TZ 13-band).
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AgroNovaQxYer(models.Model):
    _name = 'agronova.qx.yer'
    _description = "Qishloq xo'jaligi — yer maydoni"
    _inherit = ['agronova.analitik.mixin', 'mail.thread']
    _order = 'code, name'

    _agronova_analytic_plan_name = "Yer maydoni"

    name = fields.Char("Yer nomi / raqami", required=True, tracking=True)
    # Kodni mijoz bermaydi — bo'sh qoldirilsa avtomat beriladi (Y01, Y02...).
    # Hisobot va ro'yxatlarda qisqa belgi sifatida kerak, lekin uni
    # to'ldirishni foydalanuvchidan talab qilish ortiqcha.
    code = fields.Char("Kod", tracking=True, copy=False, index=True,
                       help="Bo'sh qoldirilsa avtomat beriladi.")
    maydoni_ga = fields.Float(
        "Maydoni (gektar)", required=True, tracking=True, digits=(12, 2),
        help="Sug'orish, elektr va texnika xarajatlari shu maydon nisbatida "
             "taqsimlanadi — shuning uchun majburiy.")
    joylashuvi = fields.Char("Joylashuvi", tracking=True)
    mas_ul_xodim_id = fields.Many2one(
        'hr.employee', string="Mas'ul xodim (agronom)", tracking=True)
    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)
    warehouse_id = fields.Many2one(
        'stock.warehouse', string="Ombor",
        domain="[('company_id', '=', company_id)]",
        help="Yer lokatsiyasi shu ombor ostida ochiladi. Urug', o'g'it va "
             "yoqilg'i shu joydan hisobdan chiqadi.")
    location_id = fields.Many2one(
        'stock.location', string="Ombor lokatsiyasi", readonly=True, copy=False)
    active = fields.Boolean("Faol", default=True)
    izoh = fields.Text("Izoh")

    # --- partiyalar
    partiya_ids = fields.One2many(
        'agronova.qx.partiya', 'yer_id', string="Ekin partiyalari")
    aktiv_partiya_id = fields.Many2one(
        'agronova.qx.partiya', string="Faol partiya",
        compute='_compute_aktiv', store=True)
    joriy_ekin_id = fields.Many2one(
        'agronova.qx.ekin', string="Joriy ekin",
        compute='_compute_aktiv', store=True)
    holat = fields.Selection(
        [('bosh', "Bo'sh"), ('ekilgan', "Yetishtirilmoqda")],
        string="Foydalanish holati", compute='_compute_aktiv', store=True)
    partiya_soni = fields.Integer(
        "Partiyalar soni", compute='_compute_aktiv', store=True,
        help="Shu yerda bugungacha yetishtirilgan ekin sikllari.")

    # --- moliya (barcha partiyalar bo'yicha jami)
    jami_xarajat = fields.Monetary("Jami xarajat", compute='_compute_moliya')
    jami_daromad = fields.Monetary("Jami daromad", compute='_compute_moliya')
    foyda = fields.Monetary("Foyda / zarar", compute='_compute_moliya')
    rentabellik = fields.Float("Rentabellik (%)", compute='_compute_moliya')

    _code_uniq = models.Constraint(
        'UNIQUE(code, company_id)', "Bu kodli yer allaqachon mavjud.")
    _maydoni_musbat = models.Constraint(
        'CHECK (maydoni_ga > 0)',
        "Yer maydoni (gektar) noldan katta bo'lishi kerak.")

    # ------------------------------------------------------------- compute
    @api.depends('partiya_ids.holat', 'partiya_ids.ekin_id')
    def _compute_aktiv(self):
        for yer in self:
            aktiv = yer.partiya_ids.filtered(lambda p: p.holat == 'active')
            yer.aktiv_partiya_id = aktiv[:1]
            yer.joriy_ekin_id = aktiv[:1].ekin_id
            yer.holat = 'ekilgan' if aktiv else 'bosh'
            yer.partiya_soni = len(yer.partiya_ids)

    def _compute_moliya(self):
        for yer in self:
            xarajat = yer._agronova_analytic_amount(sign='cost')
            daromad = yer._agronova_analytic_amount(sign='income')
            for p in yer.partiya_ids:
                xarajat += p._agronova_analytic_amount(sign='cost')
                daromad += p._agronova_analytic_amount(sign='income')
            yer.jami_xarajat = xarajat
            yer.jami_daromad = daromad
            yer.foyda = daromad - xarajat
            yer.rentabellik = (yer.foyda / daromad * 100.0) if daromad else 0.0

    # ------------------------------------------------------------- yaratish
    def _agronova_analytic_vals(self):
        vals = super()._agronova_analytic_vals()
        vals['name'] = _("Yer — %s", self.name)
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("code"):
                vals["code"] = self.env["ir.sequence"].next_by_code(
                    "agronova.qx.yer") or False
        yerlar = super().create(vals_list)
        yerlar._ensure_location()
        return yerlar

    def _ensure_location(self):
        """Har yerga ombor lokatsiyasi ochadi (bo'lsa — mavjudini bog'laydi)."""
        Location = self.env['stock.location'].sudo()
        for yer in self.filtered(lambda y: not y.location_id):
            warehouse = yer.warehouse_id or self.env['stock.warehouse'].search(
                [('company_id', '=', yer.company_id.id)], limit=1)
            if not warehouse:
                continue
            if not yer.warehouse_id:
                yer.warehouse_id = warehouse
            parent = Location.search([
                ('location_id', 'child_of', warehouse.lot_stock_id.id),
                ('name', '=ilike', 'Yer'),
                ('usage', '=', 'internal'),
            ], limit=1) or warehouse.lot_stock_id
            mavjud = Location.search([
                ('location_id', '=', parent.id),
                ('name', '=ilike', yer.name),
            ], limit=1)
            yer.location_id = mavjud or Location.create({
                'name': yer.name,
                'location_id': parent.id,
                'usage': 'internal',
                'company_id': yer.company_id.id,
            })

    @api.constrains('maydoni_ga')
    def _check_maydoni(self):
        for yer in self:
            if yer.maydoni_ga <= 0:
                raise ValidationError(_(
                    "«%s» yerining maydoni ko'rsatilishi kerak.", yer.name))

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
                'name': _("Qishloq xo'jaligi ishlab chiqarish"),
                'usage': 'production',
                'company_id': self.company_id.id,
            })
        return loc

    def _hosil_ombori(self):
        """Olingan hosil tushadigan lokatsiya."""
        self.ensure_one()
        if not self.warehouse_id:
            return self.env['stock.location'].browse()
        loc = self.env['stock.location'].sudo().search([
            ('location_id', 'child_of', self.warehouse_id.lot_stock_id.id),
            ('name', 'ilike', 'Hosil'),
            ('usage', '=', 'internal'),
        ], limit=1)
        return loc or self.warehouse_id.lot_stock_id

    def action_open_partiyalar(self):
        """Yer kartasidagi tarix (TZ 13-band)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("«%s» yeri partiyalari", self.name),
            'res_model': 'agronova.qx.partiya',
            'view_mode': 'list,form',
            'domain': [('yer_id', '=', self.id)],
            'context': {'default_yer_id': self.id},
        }
