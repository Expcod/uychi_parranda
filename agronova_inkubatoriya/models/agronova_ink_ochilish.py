# -*- coding: utf-8 -*-
"""Jo'ja ochilishi (TZ 5 va 6-band).

Inkubatsiya yakunida natija shu hujjat bilan kiritiladi:

    qo'yilgan tuxum = ochilgan jo'ja + ochilmagan tuxum

Ochilgan jo'janing bir qismi nobud yoki brak bo'lishi mumkin — omborga
faqat **yaroqli** jo'ja kiradi.

Tasdiqlanganda ikki ombor harakati bo'ladi:

* tuxum ombordan **hisobdan chiqadi** (inkubatsiya sarfi);
* yaroqli jo'ja **jo'ja omboriga kiradi**, qiymati partiyaning shu
  paytgacha yig'ilgan xarajatidan olinadi.

Jo'jaga **lot** beriladi: partiya raqami va ochilish sanasi. Shu orqali
«bu jo'jalar qaysi tuxumdan, qaysi ona tovuq filialidan?» degan savolga
javob beriladi (TZ 6-band).
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class AgroNovaInkOchilish(models.Model):
    _name = 'agronova.ink.ochilish'
    _description = "Inkubatoriya — jo'ja ochilishi"
    _inherit = ['mail.thread', 'agronova.mahsulot.filtr.mixin']
    _order = 'sana desc, id desc'

    name = fields.Char("Hujjat", default=lambda s: _("Yangi"), copy=False,
                       readonly=True, index=True)
    partiya_id = fields.Many2one(
        'agronova.ink.partiya', string="Inkubatsiya partiyasi", required=True,
        ondelete='restrict', index=True, tracking=True,
        domain="[('holat', '=', 'inkubatsiyada')]")
    sana = fields.Date("Ochilish sanasi", required=True,
                       default=fields.Date.context_today, tracking=True)
    company_id = fields.Many2one(
        'res.company', string="Korxona", related='partiya_id.company_id',
        store=True, readonly=True)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)

    product_id = fields.Many2one(
        'product.product', string="Jo'ja mahsuloti", required=True,
        help="Omborga kiradigan kunlik jo'ja.")
    product_domain = fields.Binary(compute='_compute_product_domain')

    def _compute_product_domain(self):
        domain = self._agronova_mahsulot_domain(
            'joja', [('is_storable', '=', True)])
        for o in self:
            o.product_domain = domain

    # --- natija
    ochilgan_joja = fields.Integer("Ochilgan jo'ja (dona)", required=True,
                                   tracking=True)
    ochilmagan_tuxum = fields.Integer("Ochilmagan tuxum (dona)", tracking=True)
    nobud_son = fields.Integer("Nobud jo'ja (dona)", tracking=True)
    brak_son = fields.Integer("Brak jo'ja (dona)", tracking=True)
    sof_joja = fields.Integer("Omborga kiradigan jo'ja (dona)",
                              compute='_compute_sof', store=True)

    holat = fields.Selection([
        ('draft', "Qoralama"),
        ('done', "Tasdiqlangan"),
    ], string="Holati", default='draft', required=True, tracking=True,
        copy=False)

    # --- ombor
    tuxum_move_id = fields.Many2one('stock.move', string="Tuxum sarfi",
                                    readonly=True, copy=False)
    joja_move_id = fields.Many2one('stock.move', string="Jo'ja kirimi",
                                   readonly=True, copy=False)
    lot_id = fields.Many2one('stock.lot', string="Jo'ja loti", readonly=True,
                             copy=False)
    joja_qiymat = fields.Monetary("Jo'jalarning qiymati", readonly=True,
                                  copy=False)
    izoh = fields.Text("Izoh")

    _ochilgan_musbat = models.Constraint(
        'CHECK (ochilgan_joja >= 0 AND ochilmagan_tuxum >= 0 '
        'AND nobud_son >= 0 AND brak_son >= 0)',
        "Miqdorlar manfiy bo'lishi mumkin emas.")

    # ------------------------------------------------------------- compute
    @api.depends('ochilgan_joja', 'nobud_son', 'brak_son')
    def _compute_sof(self):
        for o in self:
            o.sof_joja = o.ochilgan_joja - o.nobud_son - o.brak_son

    @api.depends('name', 'partiya_id', 'sana')
    def _compute_display_name(self):
        for o in self:
            o.display_name = "%s · %s" % (o.name or "",
                                          o.partiya_id.name or "")

    @api.constrains('ochilgan_joja', 'ochilmagan_tuxum', 'nobud_son',
                    'brak_son', 'partiya_id')
    def _check_miqdor(self):
        for o in self:
            if o.nobud_son + o.brak_son > o.ochilgan_joja:
                raise ValidationError(_(
                    "Nobud va brak jo'ja soni ochilgan jo'jadan ko'p "
                    "bo'lishi mumkin emas."))
            # Boshqa hujjatlar bilan birga qo'yilgan tuxumdan oshmasin.
            boshqa = o.partiya_id.ochilish_ids.filtered(
                lambda x: x.id != o.id and x.holat == 'done')
            jami = (sum(boshqa.mapped('ochilgan_joja'))
                    + sum(boshqa.mapped('ochilmagan_tuxum'))
                    + o.ochilgan_joja + o.ochilmagan_tuxum)
            if o.partiya_id.tuxum_dona and jami > o.partiya_id.tuxum_dona:
                raise ValidationError(_(
                    "«%(p)s» partiyasiga %(tuxum)s dona tuxum qo'yilgan, "
                    "natija esa %(jami)s dona — ochilgan va ochilmagan "
                    "tuxum yig'indisi qo'yilganidan oshmasligi kerak.",
                    p=o.partiya_id.name, tuxum=o.partiya_id.tuxum_dona,
                    jami=jami))

    # ------------------------------------------------------------ yaratish
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _("Yangi"):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'agronova.ink.ochilish') or _("Yangi")
        return super().create(vals_list)

    # -------------------------------------------------------------- amallar
    def action_tasdiqlash(self):
        for o in self:
            if o.holat != 'draft':
                raise UserError(_("Faqat qoralama hujjat tasdiqlanadi."))
            if o.partiya_id.holat != 'inkubatsiyada':
                raise UserError(_(
                    "«%s» partiyasi inkubatsiyada emas.", o.partiya_id.name))
            o._tuxumni_chiqarish()
            o._jojani_kirim_qilish()
            o.holat = 'done'
            o.partiya_id._tannarxni_hisoblash()
            o.partiya_id.message_post(body=_(
                "Ochilish natijasi: %(och)s jo'ja, %(yoq)s ochilmagan tuxum, "
                "%(nob)s nobud, %(brak)s brak.",
                och=o.ochilgan_joja, yoq=o.ochilmagan_tuxum,
                nob=o.nobud_son, brak=o.brak_son))
        return True

    def action_bekor(self):
        """Tasdiqni bekor qiladi — ombor harakatlari qaytariladi."""
        for o in self:
            if o.holat != 'done':
                raise UserError(_("Faqat tasdiqlangan hujjat bekor qilinadi."))
            if o.partiya_id.holat == 'done':
                raise UserError(_(
                    "«%s» partiyasi yakunlangan — avval uni qayta oching.",
                    o.partiya_id.name))
            for move in (o.joja_move_id, o.tuxum_move_id):
                if move and move.state == 'done':
                    o._qaytarish(move)
            o.write({'holat': 'draft', 'tuxum_move_id': False,
                     'joja_move_id': False, 'joja_qiymat': 0.0})
        return True

    # ---------------------------------------------------------------- ombor
    def _ombor(self):
        self.ensure_one()
        wh = self.env['stock.warehouse'].sudo().search(
            [('company_id', '=', self.company_id.id)], limit=1)
        if not wh:
            raise UserError(_("Inkubatoriya korxonasida ombor topilmadi."))
        return wh

    def _ishlab_chiqarish_joyi(self):
        self.ensure_one()
        loc = self.env['stock.location'].sudo().search([
            ('usage', '=', 'production'),
            ('company_id', 'in', [self.company_id.id, False]),
        ], limit=1)
        if not loc:
            loc = self.env['stock.location'].sudo().create({
                'name': _("Inkubatsiya"), 'usage': 'production',
                'company_id': self.company_id.id})
        return loc

    def _tuxumni_chiqarish(self):
        """Inkubatsiyaga ketgan tuxumni ombordan hisobdan chiqaradi.

        Analitik qator yozilmaydi: tuxum qiymati partiyaga qabul
        hujjatida allaqachon xarajat bo'lib tushgan. Ikki marta yozilsa
        jo'ja tannarxi ikki barobar oshib ketardi.
        """
        self.ensure_one()
        product = self.qabul_product()
        if not product:
            return False
        dona = self.ochilgan_joja + self.ochilmagan_tuxum
        if not dona:
            return False
        wh = self._ombor()
        move = self.env['stock.move'].sudo().create({
            'product_id': product.id,
            'product_uom_qty': dona,
            'product_uom': product.uom_id.id,
            'location_id': wh.lot_stock_id.id,
            'location_dest_id': self._ishlab_chiqarish_joyi().id,
            'company_id': self.company_id.id,
            'origin': self.display_name,
        })
        move._action_confirm()
        move._action_assign()
        move.quantity = dona
        move.picked = True
        move._action_done()
        self.tuxum_move_id = move.id
        return True

    def qabul_product(self):
        """Partiyaga qaysi tuxum mahsuloti qabul qilingan."""
        self.ensure_one()
        qabul = self.partiya_id.qabul_ids.filtered(lambda q: q.holat == 'done')
        return qabul[:1].product_id

    def _joja_lot(self):
        """Kuzatuv uchun lot: partiya raqami va ochilish sanasi.

        Mavjud bo'lsa qayta ishlatiladi — hujjat bekor qilinib qayta
        tasdiqlansa bir xil nomli lot ikkinchi marta yaratilmaydi.
        """
        self.ensure_one()
        if self.product_id.tracking == 'none':
            return False
        nom = "%s/%s" % (self.partiya_id.name, self.sana)
        Lot = self.env['stock.lot'].sudo()
        lot = Lot.search([
            ('name', '=', nom),
            ('product_id', '=', self.product_id.id),
            ('company_id', 'in', [self.company_id.id, False]),
        ], limit=1)
        if not lot:
            lot = Lot.create({'name': nom, 'product_id': self.product_id.id,
                              'company_id': self.company_id.id})
        return lot

    def _jojani_kirim_qilish(self):
        """Yaroqli jo'jani omborga kirim qiladi.

        Qiymat partiyaning shu paytgacha yig'ilgan ishlab chiqarish
        xarajatidan olinadi. Bir partiyada bir necha ochilish hujjati
        bo'lsa, avvalgilarida allaqachon kirim qilingan qiymat chiqarib
        tashlanadi — aks holda xarajat har hujjatda qaytadan sanalardi.
        """
        self.ensure_one()
        if not self.sof_joja:
            return False
        partiya = self.partiya_id
        xarajat = partiya._agronova_analytic_amount(sign='cost',
                                                faqat_tannarx=True)
        avval = sum(partiya.ochilish_ids.filtered(
            lambda o: o.id != self.id and o.holat == 'done'
        ).mapped('joja_qiymat'))
        qiymat = max(xarajat - avval, 0.0)
        narx = qiymat / self.sof_joja

        wh = self._ombor()
        lot = self._joja_lot()
        move = self.env['stock.move'].sudo().create({
            'product_id': self.product_id.id,
            'product_uom_qty': self.sof_joja,
            'product_uom': self.product_id.uom_id.id,
            'location_id': self._ishlab_chiqarish_joyi().id,
            'location_dest_id': wh.lot_stock_id.id,
            'company_id': self.company_id.id,
            'price_unit': narx,
            'origin': self.display_name,
        })
        move._action_confirm()
        move._action_assign()
        move.quantity = self.sof_joja
        if lot:
            move.move_line_ids.write({'lot_id': lot.id})
        move.picked = True
        move._action_done()
        self.write({'joja_move_id': move.id, 'joja_qiymat': qiymat,
                    'lot_id': lot and lot.id})
        # Jo'janing standart narxi qabul qiluvchi bo'lim uchun ham to'g'ri
        # bo'lishi kerak — Boquvga berilganda shundan hisoblanadi.
        if narx:
            self.product_id.with_company(self.company_id).sudo() \
                .standard_price = narx
        return True

    def _qaytarish(self, move):
        """Ombor harakatini teskari yo'nalishda qaytaradi."""
        self.ensure_one()
        qaytish = self.env['stock.move'].sudo().create({
            'product_id': move.product_id.id,
            'product_uom_qty': move.quantity,
            'product_uom': move.product_uom.id,
            'location_id': move.location_dest_id.id,
            'location_dest_id': move.location_id.id,
            'company_id': move.company_id.id,
            'origin': _("Bekor: %s", self.display_name),
        })
        qaytish._action_confirm()
        qaytish._action_assign()
        qaytish.quantity = move.quantity
        qaytish.picked = True
        qaytish._action_done()
        return qaytish
