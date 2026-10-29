# -*- coding: utf-8 -*-
"""Dalada bajarilgan ish (TZ 5, 6-band).

Ona Tovuqdagi kunlik jurnalning analogi, lekin **kunlik emas** — ekinda
har kun yozadigan narsa yo'q. Yozuv faqat ish bajarilganda kiritiladi:
ekish, o'g'itlash, sug'orish, dorilash, o'rim, boshqa.

Tasdiqlanganda:
* sarflangan urug'/o'g'it/yoqilg'i **ombordan hisobdan chiqadi**;
* FIFO qiymati partiyaning analitik hisobiga xarajat bo'lib tushadi.

Shu sababli tasdiqlangan yozuv tahrirlanmaydi — tannarx undan hisoblanadi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

ISH_TURI = [
    ('shudgor', "Shudgor / yer tayyorlash"),
    ('ekish', "Ekish"),
    ('ogitlash', "O'g'itlash"),
    ('sugorish', "Sug'orish"),
    ('dorilash', "Dorilash / kimyoviy ishlov"),
    ('orim', "O'rim / hosil yig'ish"),
    ('boshqa', "Boshqa ish"),
]


class AgroNovaQxIshSarf(models.Model):
    """Ishda sarflangan resurs qatori."""
    _name = 'agronova.qx.ish.sarf'
    _description = "Qishloq xo'jaligi — sarf qatori"

    ish_id = fields.Many2one(
        'agronova.qx.ish', string="Ish", required=True, ondelete='cascade',
        index=True)
    product_id = fields.Many2one(
        'product.product', string="Mahsulot", required=True,
        domain="[('is_storable', '=', True)]")
    miqdor = fields.Float("Miqdor", required=True, digits='Product Unit')
    uom_id = fields.Many2one(
        'uom.uom', string="Birlik", required=True,
        compute='_compute_uom', store=True, readonly=False)
    move_id = fields.Many2one(
        'stock.move', string="Ombor harakati", readonly=True, copy=False)
    qiymat = fields.Monetary(
        "Qiymati", readonly=True, copy=False,
        help="FIFO bo'yicha hisobdan chiqqan qiymat. Qo'lda kiritilmaydi.")
    currency_id = fields.Many2one(
        'res.currency', related='ish_id.currency_id', readonly=True)

    _miqdor_musbat = models.Constraint(
        'CHECK (miqdor > 0)', "Sarf miqdori noldan katta bo'lishi kerak.")

    @api.depends('product_id')
    def _compute_uom(self):
        for line in self:
            line.uom_id = line.product_id.uom_id


class AgroNovaQxIsh(models.Model):
    _name = 'agronova.qx.ish'
    _description = "Qishloq xo'jaligi — dalada bajarilgan ish"
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    name = fields.Char("Tavsif", compute='_compute_name', store=True)
    date = fields.Date(
        "Sana", required=True, default=fields.Date.context_today,
        tracking=True, index=True)
    tur = fields.Selection(
        ISH_TURI, string="Ish turi", required=True, tracking=True,
        default='boshqa')
    partiya_id = fields.Many2one(
        'agronova.qx.partiya', string="Ekin partiyasi", required=True,
        ondelete='cascade', index=True,
        domain="[('holat', '=', 'active')]",
        help="Faqat yetishtirilayotgan partiyalar.")
    yer_id = fields.Many2one(
        related='partiya_id.yer_id', string="Yer", store=True, readonly=True)
    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True, readonly=True,
        store=True, precompute=True, compute='_compute_company_id')
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)
    holat = fields.Selection(
        [('draft', "Qoralama"), ('posted', "Tasdiqlangan")],
        string="Holati", default='draft', required=True, tracking=True,
        copy=False)

    maydoni_ga = fields.Float(
        "Ishlov berilgan maydon (ga)", digits=(12, 2),
        help="Qismiy ishlov berilgan bo'lsa ko'rsatiladi — hisobot uchun.")
    texnika_soat = fields.Float(
        "Texnika ishlagan vaqt (soat)",
        help="Traktor, kombayn va boshqa texnika. Xarajati alohida xarajat "
             "hujjati bilan kiritiladi.")
    xodim_ids = fields.Many2many('hr.employee', string="Ishchilar")
    sarf_ids = fields.One2many(
        'agronova.qx.ish.sarf', 'ish_id', string="Sarflangan resurslar")
    sarf_qiymat = fields.Monetary(
        "Sarf qiymati", compute='_compute_sarf_qiymat', store=True)
    izoh = fields.Text("Izoh")

    # ------------------------------------------------------------- compute
    @api.depends('partiya_id')
    def _compute_company_id(self):
        for ish in self:
            ish.company_id = ish.partiya_id.company_id or self.env.company

    @api.depends('sarf_ids.qiymat')
    def _compute_sarf_qiymat(self):
        for ish in self:
            ish.sarf_qiymat = sum(ish.sarf_ids.mapped('qiymat'))

    @api.depends('tur', 'date', 'partiya_id')
    def _compute_name(self):
        turlar = dict(ISH_TURI)
        for ish in self:
            ish.name = "%s / %s" % (turlar.get(ish.tur, ""), ish.date or "")

    # ---------------------------------------------------------------- yozish
    @api.model_create_multi
    def create(self, vals_list):
        ishlar = super().create(vals_list)
        for ish in ishlar:
            ish.partiya_id._tekshir_ochiq(_("dalada bajarilgan ish"))
        return ishlar

    def write(self, vals):
        if not self.env.context.get('agronova_qx_post'):
            for ish in self:
                if ish.holat == 'posted' and set(vals) - {
                        'izoh', 'message_ids', 'message_follower_ids'}:
                    raise UserError(_(
                        "«%s» yozuvi tasdiqlangan — tahrirlanmaydi. "
                        "Tuzatish uchun storno qiling.", ish.display_name))
        return super().write(vals)

    def unlink(self):
        for ish in self:
            if ish.holat == 'posted':
                raise UserError(_(
                    "Tasdiqlangan yozuvni o'chirib bo'lmaydi (%s).", ish.date))
        return super().unlink()

    @api.constrains('date')
    def _check_kelajak(self):
        bugun = fields.Date.context_today(self)
        for ish in self:
            if ish.date > bugun:
                raise ValidationError(_("Kelajakdagi sana bilan yozuv ochilmaydi."))

    # ----------------------------------------------------------- tasdiqlash
    def action_tasdiqlash(self):
        for ish in self:
            if ish.holat == 'posted':
                continue
            ish.partiya_id._tekshir_ochiq(_("ishni tasdiqlash"))
            ish._sarfni_chiqarish()
            ish.with_context(agronova_qx_post=True).holat = 'posted'
        return True

    def _sarfni_chiqarish(self):
        """Sarflangan resursni ombordan chiqaradi va analitikaga yozadi."""
        self.ensure_one()
        yer = self.partiya_id.yer_id
        if not yer.location_id:
            if self.sarf_ids:
                raise UserError(_(
                    "«%s» yerida ombor lokatsiyasi yo'q — sarfni hisobdan "
                    "chiqarib bo'lmaydi.", yer.display_name or "?"))
            return
        src = yer.location_id
        dest = yer._production_location()
        turlar = dict(ISH_TURI)
        for line in self.sarf_ids.filtered(lambda l: not l.move_id):
            move = self.env['stock.move'].sudo().create({
                'product_id': line.product_id.id,
                'product_uom_qty': line.miqdor,
                'product_uom': line.uom_id.id,
                'location_id': src.id,
                'location_dest_id': dest.id,
                'company_id': self.company_id.id,
                'origin': "%s / %s" % (self.partiya_id.name, self.date),
            })
            move._action_confirm()
            move._action_assign()
            move.quantity = line.miqdor
            move.picked = True
            move._action_done()
            line.move_id = move
            # Odoo 19 da qiymat to'g'ridan-to'g'ri `stock.move.value` da.
            qiymat = abs(move.value or 0.0)
            if not qiymat:
                qiymat = abs(line.product_id.standard_price * line.miqdor)
            line.qiymat = qiymat
            if qiymat:
                self.partiya_id._agronova_post_analytic(
                    name=_("%(ish)s: %(mahsulot)s",
                           ish=turlar.get(self.tur, ""),
                           mahsulot=line.product_id.display_name),
                    amount=-qiymat,
                    date=self.date,
                    unit_amount=line.miqdor,
                    product=line.product_id,
                    extra={'company_id': self.company_id.id},
                )

    def action_qoralamaga(self):
        """Storno: sarfni ombordagi joyiga qaytaradi, analitikani teskarilaydi."""
        for ish in self:
            if ish.holat != 'posted':
                continue
            yer = ish.partiya_id.yer_id
            for line in ish.sarf_ids.filtered(lambda l: l.move_id):
                qaytish = self.env['stock.move'].sudo().create({
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.miqdor,
                    'product_uom': line.uom_id.id,
                    'location_id': yer._production_location().id,
                    'location_dest_id': yer.location_id.id,
                    'company_id': ish.company_id.id,
                    'origin': _("STORNO: %s", ish.display_name),
                })
                qaytish._action_confirm()
                qaytish._action_assign()
                qaytish.quantity = line.miqdor
                qaytish.picked = True
                qaytish._action_done()
                if line.qiymat:
                    ish.partiya_id._agronova_post_analytic(
                        name=_("STORNO: %s", line.product_id.display_name),
                        amount=abs(line.qiymat),
                        date=fields.Date.context_today(ish),
                        extra={'company_id': ish.company_id.id},
                    )
                line.write({'move_id': False, 'qiymat': 0.0})
            ish.with_context(agronova_qx_post=True).holat = 'draft'
        return True
