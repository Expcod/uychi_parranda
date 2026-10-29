# -*- coding: utf-8 -*-
"""Hosilni qabul qilish (TZ 7, 8-band).

O'rim vaqtida olingan hosil omborga kirim qilinadi. Qiymati **partiyaning
joriy tannarxidan** olinadi: `jami xarajat / olingan hosil`. Ya'ni birinchi
kirimda tannarx yuqori bo'ladi (xarajat bo'lgan, hosil hali kam), keyingi
kirimlarda pasayib boradi — bu normal, chunki partiya yopilganda yakuniy
tannarx qotadi.

Hosilga lot beriladi: `partiya/sana` — TZ 12-bandidagi kuzatuv shu orqali.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AgroNovaQxHosil(models.Model):
    _name = 'agronova.qx.hosil'
    _description = "Qishloq xo'jaligi — hosil kirimi"
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    name = fields.Char("Hujjat", compute='_compute_name', store=True)
    date = fields.Date(
        "Olingan sana", required=True, default=fields.Date.context_today,
        tracking=True, index=True)
    partiya_id = fields.Many2one(
        'agronova.qx.partiya', string="Ekin partiyasi", required=True,
        ondelete='restrict', index=True,
        domain="[('holat', '=', 'active')]")
    yer_id = fields.Many2one(
        related='partiya_id.yer_id', string="Yer", store=True, readonly=True)
    ekin_id = fields.Many2one(
        related='partiya_id.ekin_id', string="Ekin", store=True, readonly=True)
    product_id = fields.Many2one(
        'product.product', string="Mahsulot",
        compute='_compute_product', store=True, readonly=False,
        domain="[('is_storable', '=', True)]")
    miqdor_kg = fields.Float(
        "Miqdor (kg)", required=True, digits='Product Unit')
    uom_id = fields.Many2one(
        'uom.uom', string="Birlik", compute='_compute_product', store=True,
        readonly=False)
    lot_id = fields.Many2one('stock.lot', string="Lot", readonly=True, copy=False)
    move_id = fields.Many2one(
        'stock.move', string="Ombor harakati", readonly=True, copy=False)
    tannarx_1_kg = fields.Monetary(
        "1 kg tannarxi", readonly=True, copy=False,
        help="Kirim vaqtidagi partiya tannarxi. Qo'lda kiritilmaydi.")
    qiymat = fields.Monetary("Jami qiymat", readonly=True, copy=False)
    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True, readonly=True,
        store=True, precompute=True, compute='_compute_company_id')
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)
    holat = fields.Selection(
        [('draft', "Qoralama"), ('done', "Omborga kirildi")],
        string="Holati", default='draft', required=True, tracking=True,
        copy=False)
    izoh = fields.Text("Izoh")

    _miqdor_musbat = models.Constraint(
        'CHECK (miqdor_kg > 0)', "Hosil miqdori noldan katta bo'lishi kerak.")

    # ------------------------------------------------------------- compute
    @api.depends('partiya_id')
    def _compute_company_id(self):
        for h in self:
            h.company_id = h.partiya_id.company_id or self.env.company

    @api.depends('partiya_id')
    def _compute_product(self):
        for h in self:
            product = h.partiya_id.ekin_id.product_id
            if product:
                h.product_id = product
                h.uom_id = product.uom_id
            elif not h.uom_id:
                h.uom_id = self.env.ref('uom.product_uom_kgm',
                                        raise_if_not_found=False)

    @api.depends('partiya_id', 'date')
    def _compute_name(self):
        for h in self:
            h.name = "%s / %s" % (h.partiya_id.name or "?", h.date or "")

    # ---------------------------------------------------------------- yozish
    @api.model_create_multi
    def create(self, vals_list):
        yozuvlar = super().create(vals_list)
        for h in yozuvlar:
            h.partiya_id._tekshir_ochiq(_("hosil kirimi"))
        return yozuvlar

    def write(self, vals):
        if not self.env.context.get('agronova_qx_post'):
            for h in self:
                if h.holat == 'done' and set(vals) - {
                        'izoh', 'message_ids', 'message_follower_ids'}:
                    raise UserError(_(
                        "«%s» kirimi bajarilgan — tahrirlanmaydi.",
                        h.display_name))
        return super().write(vals)

    def unlink(self):
        for h in self:
            if h.holat == 'done':
                raise UserError(_(
                    "Omborga kirim qilingan hosil hujjati o'chirilmaydi."))
        return super().unlink()

    # -------------------------------------------------------------- kirim
    def action_kirim(self):
        """Hosilni omborga kirim qiladi, lot beradi, qiymatini yozadi."""
        for h in self:
            if h.holat == 'done':
                continue
            if not h.product_id:
                raise UserError(_(
                    "«%s» hujjatida mahsulot ko'rsatilmagan. Ekin turiga "
                    "hosil mahsulotini bog'lang yoki qo'lda tanlang.",
                    h.display_name))
            yer = h.partiya_id.yer_id
            dest = yer._hosil_ombori()
            if not dest:
                raise UserError(_(
                    "«%s» yeriga ombor biriktirilmagan — hosilni kirim "
                    "qilib bo'lmaydi.", yer.name))

            # Kirim vaqtidagi tannarx: partiyaning shu paytgacha yig'ilgan
            # xarajati, kirilayotgan hosil bilan birga hisoblanadi.
            xarajat = h.partiya_id.jami_xarajat
            jami_hosil = h.partiya_id.olingan_hosil_kg + h.miqdor_kg
            tannarx = (xarajat / jami_hosil) if jami_hosil else 0.0

            lot = self.env['stock.lot'].sudo().create({
                'name': "%s/%s" % (h.partiya_id.name, h.date),
                'product_id': h.product_id.id,
                'company_id': h.company_id.id,
            }) if h.product_id.tracking != 'none' else False

            move = self.env['stock.move'].sudo().create({
                'product_id': h.product_id.id,
                'product_uom_qty': h.miqdor_kg,
                'product_uom': (h.uom_id or h.product_id.uom_id).id,
                'location_id': yer._production_location().id,
                'location_dest_id': dest.id,
                'company_id': h.company_id.id,
                'price_unit': tannarx,
                'origin': h.display_name,
            })
            move._action_confirm()
            move._action_assign()
            move.quantity = h.miqdor_kg
            if lot:
                move.move_line_ids.write({'lot_id': lot.id})
            move.picked = True
            move._action_done()

            h.with_context(agronova_qx_post=True).write({
                'move_id': move.id,
                'lot_id': lot and lot.id,
                'tannarx_1_kg': tannarx,
                'qiymat': tannarx * h.miqdor_kg,
                'holat': 'done',
            })
        return True
