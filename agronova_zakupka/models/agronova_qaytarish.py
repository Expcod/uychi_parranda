# -*- coding: utf-8 -*-
"""Tovarni qaytarish (TZ 7-bo'lim).

Buzuq yoki nosoz chiqqan tovar qaytariladi — dori-darmonda bu majburiy yo'l.
Qaytarish hujjati **tovarni ham, qarzni ham teskari yozadi**: kirim
hujjati tahrirlanmaydi (TZ 21.6), uning o'rniga qarama-qarshi hujjat
rasmiylashtiriladi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

QAYTARISH_SABABI = [
    ('buzuq', "Buzuq / nosoz"),
    ('sifatsiz', "Sifat talabga mos emas"),
    ('muddat', "Yaroqlilik muddati yaqin yoki o'tgan"),
    ('ortiqcha', "Ortiqcha keltirilgan"),
    ('boshqa', "Boshqa sabab"),
]


class AgroNovaQaytarish(models.Model):
    _name = 'agronova.qaytarish'
    _description = "Xarid tovarini qaytarish"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sana desc, id desc'

    name = fields.Char(
        "Hujjat raqami", default=lambda self: _("Yangi"),
        copy=False, readonly=True, index=True)
    kirim_id = fields.Many2one(
        'agronova.kirim', string="Kirim hujjati", required=True,
        ondelete='restrict', index=True, tracking=True)
    kontragent_id = fields.Many2one(
        'res.partner', related='kirim_id.kontragent_id', store=True,
        readonly=True, string="Kontragent")
    company_id = fields.Many2one(
        'res.company', related='kirim_id.company_id', store=True, readonly=True)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)
    sana = fields.Date(
        "Qaytarish sanasi", required=True, tracking=True,
        default=fields.Date.context_today)
    sabab = fields.Selection(
        QAYTARISH_SABABI, string="Sabab", required=True, tracking=True)
    izoh = fields.Text("Izoh")
    qator_ids = fields.One2many(
        'agronova.qaytarish.qatori', 'qaytarish_id', string="Qatorlar")
    summa = fields.Monetary("Summa", compute='_compute_summa', store=True)

    holat = fields.Selection(
        [('draft', "Qoralama"),
         ('tasdiqlangan', "Tasdiqlangan")],
        string="Holati", default='draft', required=True, tracking=True, copy=False)
    picking_id = fields.Many2one(
        'stock.picking', string="Qaytarish harakati", readonly=True, copy=False)
    kredit_nota_id = fields.Many2one(
        'account.move', string="Kredit-nota", readonly=True, copy=False,
        help="Qarzni teskari yozadigan moliyaviy hujjat.")

    @api.depends('qator_ids.summa')
    def _compute_summa(self):
        for rec in self:
            rec.summa = sum(rec.qator_ids.mapped('summa'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _("Yangi")) == _("Yangi"):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'agronova.qaytarish') or _("Yangi")
        return super().create(vals_list)

    def action_qatorlarni_toldirish(self):
        """Kirim qatorlarini nusxalab oladi — qo'lda kamaytiriladi."""
        self.ensure_one()
        self.qator_ids.unlink()
        self.qator_ids = [(0, 0, {
            'kirim_qatori_id': q.id,
            'product_id': q.product_id.id,
            'miqdor': q.qabul_miqdor or q.miqdor,
            'narx': q.narx,
        }) for q in self.kirim_id.qator_ids]
        return True

    def action_tasdiqlash(self):
        for rec in self:
            if rec.holat != 'draft':
                raise UserError(_("Faqat qoralama qaytarish tasdiqlanadi."))
            if not rec.qator_ids:
                raise UserError(_("Qaytariladigan qator ko'rsatilmagan."))
            rec.picking_id = rec._agronova_qaytarish_picking()
            rec.kredit_nota_id = rec._agronova_kredit_nota()
            rec.holat = 'tasdiqlangan'
            rec.kirim_id.message_post(body=_(
                "Qaytarish rasmiylashtirildi: %(hujjat)s, %(summa)s.",
                hujjat=rec.name, summa=rec.summa))
        return True

    def _agronova_qaytarish_picking(self):
        """Tovar omborchi qabul qilgan bo'lsa ombordan, aks holda tranzitdan."""
        self.ensure_one()
        kirim = self.kirim_id
        manba = (kirim.maqsad_ombor_id.lot_stock_id
                 if kirim.holat == 'qabul_qilindi' else kirim.tranzit_id)
        maqsad = (kirim.kontragent_id.property_stock_supplier
                  or self.env.ref('stock.stock_location_suppliers'))
        tur = kirim.maqsad_ombor_id.out_type_id
        if not tur:
            raise UserError(_(
                "«%s» omborida chiqim operatsiya turi sozlanmagan.",
                kirim.maqsad_ombor_id.display_name))
        picking = self.env['stock.picking'].sudo().create({
            'picking_type_id': tur.id,
            'partner_id': kirim.kontragent_id.id or False,
            'location_id': manba.id,
            'location_dest_id': maqsad.id,
            'origin': _("%(qaytarish)s (%(kirim)s)",
                        qaytarish=self.name, kirim=kirim.name),
            'company_id': self.company_id.id,
            'scheduled_date': fields.Datetime.now(),
        })
        miqdorlar = {}
        for qator in self.qator_ids:
            move = self.env['stock.move'].sudo().create({
                'description_picking': qator.product_id.display_name,
                'product_id': qator.product_id.id,
                'product_uom_qty': qator.miqdor,
                'product_uom': qator.product_id.uom_id.id,
                'location_id': manba.id,
                'location_dest_id': maqsad.id,
                'picking_id': picking.id,
                'company_id': self.company_id.id,
                'price_unit': qator.narx,
            })
            miqdorlar[move] = (qator.miqdor, qator.kirim_qatori_id)
        return kirim._agronova_pickingni_yakunlash(picking, miqdorlar)

    def _agronova_kredit_nota(self):
        """Qarzni teskari yozadi — kirim fakturasi tahrirlanmaydi."""
        self.ensure_one()
        kirim = self.kirim_id
        if not kirim.faktura_id:
            return self.env['account.move']
        qatorlar = [(0, 0, {
            'product_id': q.product_id.id,
            'name': q.product_id.display_name,
            'quantity': q.miqdor,
            'product_uom_id': q.product_id.uom_id.id,
            'price_unit': q.narx,
        }) for q in self.qator_ids]
        nota = self.env['account.move'].sudo().create({
            'move_type': 'in_refund',
            'partner_id': kirim.faktura_id.partner_id.id,
            'invoice_date': self.sana,
            'date': self.sana,
            'journal_id': kirim.faktura_id.journal_id.id,
            'company_id': self.company_id.id,
            'ref': _("Qaytarish %(qaytarish)s -> %(kirim)s",
                     qaytarish=self.name, kirim=kirim.name),
            'invoice_line_ids': qatorlar,
        })
        nota.action_post()
        return nota

    def unlink(self):
        if any(rec.holat != 'draft' for rec in self):
            raise UserError(_(
                "Tasdiqlangan qaytarish hujjati o'chirilmaydi."))
        return super().unlink()


class AgroNovaQaytarishQatori(models.Model):
    _name = 'agronova.qaytarish.qatori'
    _description = "Qaytarish qatori"
    _order = 'qaytarish_id, id'

    qaytarish_id = fields.Many2one(
        'agronova.qaytarish', string="Qaytarish", required=True,
        ondelete='cascade', index=True)
    kirim_qatori_id = fields.Many2one(
        'agronova.kirim.qatori', string="Kirim qatori", required=True,
        ondelete='restrict')
    product_id = fields.Many2one(
        'product.product', string="Tovar", required=True)
    miqdor = fields.Float("Qaytariladigan miqdor", required=True)
    narx = fields.Monetary("Narx")
    summa = fields.Monetary("Summa", compute='_compute_summa', store=True)
    currency_id = fields.Many2one(
        'res.currency', related='qaytarish_id.currency_id', readonly=True)

    @api.depends('miqdor', 'narx')
    def _compute_summa(self):
        for qator in self:
            qator.summa = qator.miqdor * qator.narx

    @api.constrains('miqdor', 'kirim_qatori_id')
    def _check_miqdor(self):
        for qator in self:
            if qator.miqdor <= 0:
                raise ValidationError(_(
                    "Qaytariladigan miqdor noldan katta bo'lishi kerak."))
            olingan = qator.kirim_qatori_id.qabul_miqdor or \
                qator.kirim_qatori_id.miqdor
            if qator.miqdor > olingan:
                raise ValidationError(_(
                    "«%(tovar)s»: %(miqdor)s qaytarib bo'lmaydi — jami "
                    "%(olingan)s olingan.",
                    tovar=qator.product_id.display_name,
                    miqdor=qator.miqdor, olingan=olingan))
