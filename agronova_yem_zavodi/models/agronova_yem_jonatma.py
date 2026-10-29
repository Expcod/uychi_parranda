# -*- coding: utf-8 -*-
"""Jo'natma — tashqi sotuv va ichki iste'mol (TZ 8.2, 8.3, 4.3).

Ichki iste'mol (ona tovuq, boquv) **sotuv emas**: sotuv buyurtmasi va
faktura yaratilmaydi, yem ichki ko'chirish bilan qabul qiluvchi omborga
o'tadi. Tashqi sotuvda esa sotuv buyurtmasi ochiladi — faktura, qarzdorlik
va to'lov Odoo'ning odatiy sotuv zanjiridan o'tadi.

Bosqichlar: loyiha → tasdiqlandi (ombor hujjati tayyor) → tarozida
tortildi → jo'natildi. Tarozi tafovuti «tasdiq kerak» yoki «kritik»
bo'lsa, mas'ul tasdiqlamaguncha jo'natma yopilmaydi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

TURLAR = [
    ('sotuv', "Tashqi mijozga sotuv"),
    ('ona_tovuq', "Ona tovuq xo'jaligiga"),
    ('boquv', "Parranda boqish bo'limiga"),
    ('ichki', "Boshqa ichki xo'jalikka"),
    ('kochirish', "Boshqa omborga ko'chirish"),
    ('qaytarish', "Mijozdan qaytarish"),
]
ICHKI = ('ona_tovuq', 'boquv', 'ichki', 'kochirish')


class AgroNovaYemJonatma(models.Model):
    _name = 'agronova.yem.jonatma'
    _description = "Yem zavodi — jo'natma"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sana desc, id desc'

    name = fields.Char("Raqam", required=True, copy=False, readonly=True, default=lambda s: _("Yangi"))
    company_id = fields.Many2one('res.company', "Korxona", required=True, default=lambda s: s.env.company)
    sana = fields.Datetime("Sana", required=True, default=fields.Datetime.now, tracking=True)
    turi = fields.Selection(TURLAR, "Jo'natma turi", required=True, default='sotuv', tracking=True)
    ichki = fields.Boolean(compute='_compute_ichki', store=True)
    state = fields.Selection([
        ('draft', "Loyiha"), ('tasdiqlangan', "Tasdiqlandi"), ('tortildi', "Tarozida tortildi"),
        ('jonatildi', "Jo'natildi"), ('bekor', "Bekor"),
    ], "Holat", default='draft', required=True, tracking=True, copy=False)

    warehouse_id = fields.Many2one('stock.warehouse', "Ombor", required=True,
                                   default=lambda s: s.env['stock.warehouse'].search(
                                       [('company_id', '=', s.env.company.id)], limit=1))
    partner_id = fields.Many2one('res.partner', "Mijoz / qabul qiluvchi", tracking=True)
    sale_id = fields.Many2one('sale.order', "Sotuv buyurtmasi", copy=False, tracking=True)
    qabul_location_id = fields.Many2one('stock.location', "Qabul qiluvchi ombor",
                                        domain="[('usage', '=', 'internal')]", tracking=True)
    qabul_qiluvchi = fields.Char("Qabul qilgan shaxs")
    masul_id = fields.Many2one('res.users', "Mas'ul", default=lambda s: s.env.user)
    avto_raqam = fields.Char("Avtomobil raqami")
    haydovchi = fields.Char("Haydovchi")
    qator_ids = fields.One2many('agronova.yem.jonatma.qator', 'jonatma_id', "Mahsulotlar", copy=True)
    picking_id = fields.Many2one('stock.picking', "Ombor hujjati", copy=False, readonly=True)
    tortish_id = fields.Many2one('agronova.tarozi.tortish', "Tarozi varaqasi", copy=False, readonly=True)

    hujjat_kg = fields.Float("Hujjat bo'yicha (kg)", compute='_compute_jami', store=True, digits=(16, 1))
    qop_soni = fields.Integer("Qoplar", compute='_compute_jami', store=True)
    haqiqiy_kg = fields.Float("Tarozi netto (kg)", related='tortish_id.netto', store=True)
    farq_kg = fields.Float("Farq (kg)", related='tortish_id.farq_kg', store=True)
    farq_pct = fields.Float("Farq (%)", related='tortish_id.farq_pct', store=True)
    tafovut = fields.Selection(related='tortish_id.tafovut', store=True, string="Tafovut")
    summa = fields.Monetary("Summa", compute='_compute_jami', store=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    izoh = fields.Text("Izoh")

    @api.model_create_multi
    def create(self, vals_list):
        for v in vals_list:
            if v.get('name', _("Yangi")) == _("Yangi"):
                v['name'] = self.env['ir.sequence'].next_by_code('agronova.yem.jonatma') or _("Yangi")
        return super().create(vals_list)

    @api.depends('turi')
    def _compute_ichki(self):
        for j in self:
            j.ichki = j.turi in ICHKI

    @api.depends('qator_ids.miqdor_kg', 'qator_ids.qop_soni', 'qator_ids.summa')
    def _compute_jami(self):
        for j in self:
            j.hujjat_kg = sum(j.qator_ids.mapped('miqdor_kg'))
            j.qop_soni = sum(j.qator_ids.mapped('qop_soni'))
            j.summa = sum(j.qator_ids.mapped('summa'))

    @api.onchange('turi')
    def _onchange_turi(self):
        loc_id = int(self.env['ir.config_parameter'].sudo().get_param(
            'agronova_yem.%s_location_id' % self.turi, 0) or 0)
        if self.turi in ICHKI and loc_id:
            self.qabul_location_id = self.env['stock.location'].browse(loc_id).exists()

    # ----------------------------------------------------------------- amallar
    def action_tasdiqlash(self):
        """Ombor hujjatini tayyorlaydi: sotuvda — sotuv buyurtmasi orqali,
        ichki jo'natmada — ichki ko'chirish."""
        for j in self:
            if j.state != 'draft':
                continue
            if not j.qator_ids:
                raise UserError(_("Jo'natmada mahsulot yo'q."))
            if j.turi in ('sotuv', 'qaytarish') and not j.partner_id:
                raise UserError(_("Mijozni tanlang."))
            if j.turi in ICHKI and not j.qabul_location_id:
                raise UserError(_("Qabul qiluvchi omborni tanlang (Sozlamalar → Yem zavodi da "
                                  "ona tovuq va boquv omborlarini bir marta belgilab qo'ysa bo'ladi)."))
            if j.turi == 'sotuv':
                j._sotuv_orqali()
            else:
                j._ombor_hujjati()
            j.state = 'tasdiqlangan'
        return True

    def _sotuv_orqali(self):
        self.ensure_one()
        P = self.env['product.product']
        so = self.sale_id
        if not so:
            so = self.env['sale.order'].create({
                'partner_id': self.partner_id.id,
                'company_id': self.company_id.id,
                'warehouse_id': self.warehouse_id.id,
                'origin': self.name,
                'order_line': [(0, 0, q._sotuv_qatori()) for q in self.qator_ids],
            })
            self.sale_id = so
        if so.state in ('draft', 'sent'):
            so.action_confirm()
        picking = so.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel'))[:1]
        if not picking:
            raise UserError(_("Sotuv buyurtmasida jo'natiladigan ombor hujjati yo'q."))
        self.picking_id = picking

    def _ombor_hujjati(self):
        self.ensure_one()
        P = self.env['product.product']
        wh = self.warehouse_id
        if self.turi == 'qaytarish':
            ptype = wh.in_type_id
            src = self.env.ref('stock.stock_location_customers')
            dest = wh.lot_stock_id
        else:
            ptype = wh.int_type_id
            src = wh.lot_stock_id
            dest = self.qabul_location_id
        picking = self.env['stock.picking'].create({
            'picking_type_id': ptype.id,
            'location_id': src.id,
            'location_dest_id': dest.id,
            'partner_id': self.partner_id.id,
            'origin': self.name,
            'company_id': self.company_id.id,
            'move_ids': [(0, 0, {
                'product_id': q.product_id.id,
                'product_uom_qty': P._agronova_kg_dan(q.miqdor_kg, q.product_id.uom_id),
                'product_uom': q.product_id.uom_id.id,
                'location_id': src.id,
                'location_dest_id': dest.id,
                'description_picking': dict(TURLAR)[self.turi],
            }) for q in self.qator_ids],
        })
        picking.action_confirm()
        picking.action_assign()
        self.picking_id = picking

    def action_tortish(self):
        """Chiqim tortish varaqasini ochadi (yoki mavjudini)."""
        self.ensure_one()
        if self.state not in ('tasdiqlangan', 'tortildi'):
            raise UserError(_("Avval jo'natmani tasdiqlang."))
        if not self.tortish_id:
            self.tortish_id = self.env['agronova.tarozi.tortish'].create({
                'yonalish': 'kirim' if self.turi == 'qaytarish' else 'chiqim',
                'picking_id': self.picking_id.id,
                'partner_id': self.partner_id.id,
                'product_id': self.qator_ids[:1].product_id.id if len(self.qator_ids) == 1 else False,
                'hujjat_netto': self.hujjat_kg,
                'avto_raqam': self.avto_raqam,
                'haydovchi': self.haydovchi,
                'company_id': self.company_id.id,
            })
        return {
            'type': 'ir.actions.act_window', 'res_model': 'agronova.tarozi.tortish',
            'res_id': self.tortish_id.id, 'view_mode': 'form', 'target': 'current',
        }

    def _tortish_majburiy(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            'agronova_yem.tortish_majburiy', 'True') not in ('False', '0', '')

    def action_jonatish(self):
        """Ombor hujjatini o'tkazadi. Hujjatdagi miqdor qoldiriladi —
        tarozi farqi alohida tasdiqlanadi va yo'qotish sifatida
        avtomatik yozilmaydi."""
        for j in self:
            if j.state not in ('tasdiqlangan', 'tortildi'):
                continue
            if j._tortish_majburiy():
                if not j.tortish_id or j.tortish_id.state != 'done':
                    raise UserError(_("Jo'natma tarozida tortilmagan — avval tortish varaqasini yakunlang."))
            p = j.picking_id
            if p and p.state not in ('done', 'cancel'):
                if p.state in ('confirmed', 'waiting'):
                    p.action_assign()
                for m in p.move_ids.filtered(lambda x: x.state not in ('done', 'cancel')):
                    m.quantity = m.product_uom_qty
                    m.picked = True
                res = p.with_context(skip_backorder=True, picking_ids_not_to_backorder=p.ids,
                                     skip_sms=True).button_validate()
                if isinstance(res, dict) and p.state != 'done':
                    raise UserError(_("Ombor hujjati %s o'tkazilmadi — omborda tekshiring.", p.name))
            j.state = 'jonatildi'
        return True

    def action_bekor(self):
        for j in self:
            if j.state == 'jonatildi':
                raise UserError(_("Jo'natilgan hujjatni bekor qilib bo'lmaydi — qaytarish hujjatini oching."))
            if j.picking_id and j.picking_id.state not in ('done', 'cancel'):
                j.picking_id.action_cancel()
            j.state = 'bekor'
        return True

    def action_picking(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': 'stock.picking',
                'res_id': self.picking_id.id, 'view_mode': 'form'}

    def action_sale(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': 'sale.order',
                'res_id': self.sale_id.id, 'view_mode': 'form'}


class AgroNovaYemJonatmaQator(models.Model):
    _name = 'agronova.yem.jonatma.qator'
    _description = "Jo'natma qatori"

    jonatma_id = fields.Many2one('agronova.yem.jonatma', required=True, ondelete='cascade', index=True)
    product_id = fields.Many2one('product.product', "Yem", required=True,
                                 domain="[('agronova_yem_turi', '=', 'yem')]")
    qop_soni = fields.Integer("Qoplar")
    qop_sigim_kg = fields.Float(related='product_id.agronova_qop_sigim_kg', string="Qopdagi (kg)")
    miqdor_kg = fields.Float("Miqdor (kg)", digits=(16, 1), required=True)
    narx_kg = fields.Float("Narx (1 kg)", digits='Product Price')
    summa = fields.Float("Summa", compute='_compute_summa', store=True)

    @api.onchange('qop_soni', 'product_id')
    def _onchange_qop(self):
        if self.qop_soni and self.product_id.agronova_qop_sigim_kg:
            self.miqdor_kg = self.qop_soni * self.product_id.agronova_qop_sigim_kg
        if self.product_id and not self.narx_kg:
            P = self.env['product.product']
            kg1 = P._agronova_kg(1.0, self.product_id.uom_id) or 1.0
            self.narx_kg = self.product_id.lst_price / kg1

    def _sotuv_qatori(self):
        """Sotuv buyurtmasi qatori: miqdor va narx mahsulot birligida."""
        P = self.env['product.product']
        uom = self.product_id.uom_id
        vals = {'product_id': self.product_id.id,
                'product_uom_qty': P._agronova_kg_dan(self.miqdor_kg, uom)}
        if self.narx_kg:
            vals['price_unit'] = self.narx_kg * (P._agronova_kg(1.0, uom) or 1.0)
        return vals

    @api.depends('miqdor_kg', 'narx_kg')
    def _compute_summa(self):
        for q in self:
            q.summa = q.miqdor_kg * q.narx_kg


class AgroNovaTaroziTortish(models.Model):
    _inherit = 'agronova.tarozi.tortish'

    def action_yakunlash(self):
        res = super().action_yakunlash()
        jonatmalar = self.env['agronova.yem.jonatma'].search([
            ('tortish_id', 'in', self.filtered(lambda t: t.state == 'done').ids),
            ('state', '=', 'tasdiqlangan'),
        ])
        jonatmalar.write({'state': 'tortildi'})
        return res
