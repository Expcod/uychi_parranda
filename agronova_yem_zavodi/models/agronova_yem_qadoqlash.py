# -*- coding: utf-8 -*-
"""Qadoqlash va qop og'irligi (TZ 4.2).

    Brutto (tarozida)       1 040 kg
    Bo'sh qoplar  40 × 1,0     40 kg
    ─────────────────────────────────
    Netto (sof yem)         1 000 kg
    Nominal  20 qop × 50   1 000 kg   → to'ldirish farqi 0 kg

Qop og'irligi ikki usulda: **standart** (qoplar soni × tasdiqlangan bitta
qop og'irligi) yoki **haqiqiy** (bo'sh qoplar alohida tortilgan).
Tasdiqlanganda qoplar qadoq omboridan ishlab chiqarishga hisobdan
chiqariladi — qop qiymati buyurtma tannarxiga qo'shiladi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AgroNovaYemQadoqlash(models.Model):
    _name = 'agronova.yem.qadoqlash'
    _description = "Yem zavodi — qadoqlash"
    _inherit = ['mail.thread', 'agronova.yem.smena.qulf.mixin']
    _order = 'sana desc, id desc'

    name = fields.Char("Raqam", required=True, copy=False, readonly=True, default=lambda s: _("Yangi"))
    company_id = fields.Many2one('res.company', "Korxona", required=True, default=lambda s: s.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    sana = fields.Datetime("Sana", required=True, default=fields.Datetime.now)
    smena_id = fields.Many2one('agronova.yem.smena', "Smena hisoboti", index='btree_not_null')
    liniya_id = fields.Many2one('agronova.yem.liniya', "Liniya")
    production_id = fields.Many2one('mrp.production', "Ishlab chiqarish buyurtmasi",
                                    domain="[('agronova_yem', '=', True), ('state', '!=', 'cancel')]",
                                    index='btree_not_null')
    product_id = fields.Many2one('product.product', "Yem", required=True,
                                 domain="[('agronova_yem_turi', '=', 'yem')]")
    lot_id = fields.Many2one('stock.lot', "Partiya", domain="[('product_id', '=', product_id)]")
    state = fields.Selection([('draft', "Loyiha"), ('tasdiqlangan', "Tasdiqlangan"), ('bekor', "Bekor")],
                             "Holat", default='draft', required=True, tracking=True)

    qop_product_id = fields.Many2one('product.product', "Qop", domain="[('agronova_yem_turi', '=', 'qadoq')]")
    qop_soni = fields.Integer("Qoplar soni", tracking=True)
    qop_sigim_kg = fields.Float("Qopdagi yem — nominal (kg)", digits=(16, 2))
    qop_vazn_kg = fields.Float("Bo'sh qop vazni (kg)", digits=(16, 3))
    qop_usul = fields.Selection([('standart', "Standart (soni × bitta qop)"),
                                 ('haqiqiy', "Haqiqiy (bo'sh qoplar tortilgan)")],
                                "Qop og'irligi usuli", required=True,
                                default=lambda s: s.env['ir.config_parameter'].sudo().get_param(
                                    'agronova_yem.qop_usul', 'standart'))
    haqiqiy_qoplar_kg = fields.Float("Bo'sh qoplar tortildi (kg)", digits=(16, 2))
    tarozi_id = fields.Many2one('agronova.tarozi', "Tarozi", domain="[('turi', 'in', ('qadoq', 'platforma'))]")
    brutto_kg = fields.Float("Brutto (kg)", digits=(16, 2), tracking=True)
    brutto_manba = fields.Selection([('tarozi', "Tarozidan"), ('qolda', "Qo'lda")], "Manba", readonly=True)

    qoplar_kg = fields.Float("Qoplar og'irligi (kg)", compute='_compute_netto', store=True, digits=(16, 2))
    netto_kg = fields.Float("Netto — sof yem (kg)", compute='_compute_netto', store=True, digits=(16, 2))
    nominal_kg = fields.Float("Nominal (kg)", compute='_compute_netto', store=True, digits=(16, 2))
    toldirish_farq_kg = fields.Float("To'ldirish farqi (kg)", compute='_compute_netto', store=True,
                                     digits=(16, 2))
    toldirish_pct = fields.Float("To'ldirish farqi (%)", compute='_compute_netto', store=True, digits=(16, 2))
    toldirish_holat = fields.Selection([('normal', "Me'yorda"), ('kam', "Kam to'ldirilgan"),
                                        ('ortiqcha', "Ortiqcha to'ldirilgan")], "To'ldirish",
                                       compute='_compute_netto', store=True)
    qop_qiymat = fields.Monetary("Qoplar qiymati", readonly=True, copy=False)
    qop_move_id = fields.Many2one('stock.move', "Qop sarfi", readonly=True, copy=False)
    izoh = fields.Text("Izoh")

    @api.model_create_multi
    def create(self, vals_list):
        for v in vals_list:
            if v.get('name', _("Yangi")) == _("Yangi"):
                v['name'] = self.env['ir.sequence'].next_by_code('agronova.yem.qadoqlash') or _("Yangi")
        recs = super().create(vals_list)
        recs._smena_qulf_tekshir()
        return recs

    @api.onchange('production_id')
    def _onchange_production(self):
        mo = self.production_id
        if mo:
            self.product_id = mo.product_id
            self.liniya_id = mo.agronova_liniya_id
            self.smena_id = mo.agronova_smena_id
            self.lot_id = mo.lot_producing_ids[:1] if 'lot_producing_ids' in mo._fields else False

    @api.onchange('product_id')
    def _onchange_product(self):
        t = self.product_id.product_tmpl_id
        if t:
            self.qop_sigim_kg = t.agronova_qop_sigim_kg or self.qop_sigim_kg
            self.qop_product_id = t.agronova_qop_product_id or self.qop_product_id
            if t.agronova_qop_product_id:
                self.qop_vazn_kg = t.agronova_qop_product_id.agronova_qop_vazn_kg

    @api.onchange('qop_product_id')
    def _onchange_qop(self):
        if self.qop_product_id:
            self.qop_vazn_kg = self.qop_product_id.agronova_qop_vazn_kg

    @api.onchange('liniya_id')
    def _onchange_liniya(self):
        if self.liniya_id.tarozi_id:
            self.tarozi_id = self.liniya_id.tarozi_id

    @api.model
    def _tolerans(self):
        return float(self.env['ir.config_parameter'].sudo().get_param(
            'agronova_yem.toldirish_tolerans_pct', 0.5) or 0.5)

    @api.depends('qop_soni', 'qop_sigim_kg', 'qop_vazn_kg', 'qop_usul', 'haqiqiy_qoplar_kg', 'brutto_kg')
    def _compute_netto(self):
        tol = self._tolerans()
        for r in self:
            qoplar = r.haqiqiy_qoplar_kg if r.qop_usul == 'haqiqiy' else (r.qop_soni or 0) * (r.qop_vazn_kg or 0.0)
            r.qoplar_kg = qoplar
            r.netto_kg = max((r.brutto_kg or 0.0) - qoplar, 0.0) if r.brutto_kg else 0.0
            r.nominal_kg = (r.qop_soni or 0) * (r.qop_sigim_kg or 0.0)
            farq = r.netto_kg - r.nominal_kg if r.brutto_kg and r.nominal_kg else 0.0
            r.toldirish_farq_kg = farq
            r.toldirish_pct = (farq / r.nominal_kg * 100.0) if r.nominal_kg else 0.0
            if not r.brutto_kg or abs(r.toldirish_pct) <= tol:
                r.toldirish_holat = 'normal'
            else:
                r.toldirish_holat = 'ortiqcha' if farq > 0 else 'kam'

    # ----------------------------------------------------------------- amallar
    def action_tarozidan(self):
        for r in self:
            if not r.tarozi_id:
                raise UserError(_("Qadoqlash tarozisini tanlang."))
            r.write({'brutto_kg': r.tarozi_id.joriy_vazn(), 'brutto_manba': 'tarozi'})
        return True

    def action_tasdiqlash(self):
        for r in self:
            if r.state != 'draft':
                continue
            if not (r.qop_soni and r.brutto_kg):
                raise UserError(_("Qoplar soni va brutto og'irligini kiriting."))
            if r.qop_usul == 'haqiqiy' and not r.haqiqiy_qoplar_kg:
                raise UserError(_("Haqiqiy usulda bo'sh qoplar og'irligini kiriting."))
            r._qop_sarfi()
            r.state = 'tasdiqlangan'
            if r.toldirish_holat != 'normal':
                r.message_post(body=_("%(h)s: %(f)s kg (%(p)s%%)",
                                      h=dict(r._fields['toldirish_holat'].selection)[r.toldirish_holat],
                                      f=round(r.toldirish_farq_kg, 2), p=round(r.toldirish_pct, 2)))
        return True

    def action_bekor(self):
        for r in self:
            if r.qop_move_id and r.qop_move_id.state == 'done':
                raise UserError(_("Qop sarfi omborda o'tkazilgan — bekor qilish uchun qoplarni "
                                  "ombor orqali qaytaring."))
            r.state = 'bekor'
        return True

    def _qop_sarfi(self):
        """Qoplarni qadoq omboridan ishlab chiqarish hisobiga chiqaradi."""
        self.ensure_one()
        if not self.qop_product_id or not self.qop_soni or not self.qop_product_id.is_storable:
            return
        icp = self.env['ir.config_parameter'].sudo()
        loc_id = int(icp.get_param('agronova_yem.qadoq_location_id', 0) or 0)
        src = self.env['stock.location'].browse(loc_id).exists() or \
            self.env['stock.warehouse'].search([('company_id', '=', self.company_id.id)], limit=1).lot_stock_id
        dest = self.env['stock.location'].search([('usage', '=', 'production'),
                                                  ('company_id', 'in', [False, self.company_id.id])], limit=1)
        if not src or not dest:
            return
        qop = self.qop_product_id
        move = self.env['stock.move'].create({
            'product_id': qop.id,
            'product_uom_qty': self.qop_soni,
            'product_uom': qop.uom_id.id,
            'location_id': src.id,
            'location_dest_id': dest.id,
            'company_id': self.company_id.id,
            'origin': "%s / %s" % (self.name, self.production_id.name or ''),
            'description_picking': _("Qadoqlash: %s", self.product_id.display_name),
        })
        move._action_confirm()
        move._action_assign()
        move.quantity = self.qop_soni
        move.picked = True
        move._action_done()
        self.write({
            'qop_move_id': move.id,
            'qop_qiymat': abs(move.value or 0.0) or qop.standard_price * self.qop_soni,
        })
