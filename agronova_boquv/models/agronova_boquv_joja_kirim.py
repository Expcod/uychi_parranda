# -*- coding: utf-8 -*-
"""Jo'ja kirimi — partiyaning birinchi va eng katta xarajati (TZ 4-band).

Ikki manba bo'ladi (yakuniy TZ, «Juja kirimi»):

* **ichki** — Inkubatoriya filialidan, bozor narxida. Haqdorlik
  shakllanmaydi, faqat bo'lim daromadi/xarajati yoziladi. TZ 4-band shuni
  ta'kidlaydi: bu oddiy ichki ko'chirish **emas**, ichki sotuv/xarid
  operatsiyasi — jo'janing inkubatsiya va boquv bosqichidagi tannarxini
  alohida ko'rish uchun;
* **tashqi** — kontragentdan xarid, **haqdorlik shakllanadi**.

Inkubatoriya moduli hali yozilmagan, shuning uchun ichki kirimda manba
hujjat maydoni bo'sh qoladi — modul kelganda shu maydonga ulanadi.

Kirim tasdiqlanganda: bosh soni partiyaga yoziladi, qiymat analitik hisobga
xarajat bo'lib tushadi, `joja_sana` to'ldiriladi va partiya faollashadi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

MANBA = [
    ('ichki', "Ichki — Inkubatoriya"),
    ('tashqi', "Tashqi — xarid"),
]


class AgroNovaBoquvJojaKirim(models.Model):
    _name = 'agronova.boquv.joja.kirim'
    _description = "Boquv — jo'ja kirimi"
    _inherit = ['mail.thread']
    _order = 'sana desc, id desc'

    name = fields.Char(
        "Hujjat raqami", default=lambda self: _("Yangi"),
        copy=False, readonly=True, index=True)
    sana = fields.Date(
        "Kirim sanasi", required=True, default=fields.Date.context_today,
        tracking=True, index=True)
    partiya_id = fields.Many2one(
        'agronova.boquv.partiya', string="Partiya", required=True, tracking=True,
        ondelete='restrict', index=True,
        domain="[('holat', 'in', ['draft', 'kutilmoqda', 'active'])]")
    bino_id = fields.Many2one(
        related='partiya_id.bino_id', string="Bino", store=True, readonly=True)
    filial_id = fields.Many2one(
        related='partiya_id.filial_id', string="Filial", store=True, readonly=True)
    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True, readonly=True,
        store=True, precompute=True, compute='_compute_company_id')
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)

    # --- manba
    manba = fields.Selection(
        MANBA, string="Manba", required=True, default='ichki', tracking=True,
        help="Ichki — Inkubatoriyadan (haqdorlik shakllanmaydi). "
             "Tashqi — kontragentdan xarid (haqdorlik shakllanadi).")
    kontragent_id = fields.Many2one(
        'res.partner', string="Kontragent", tracking=True,
        help="Tashqi xaridda majburiy. Ichki kirimda Inkubatoriya moduli "
             "ishga tushgach to'ldiriladi.")
    manba_hujjat = fields.Char(
        "Manba hujjati", tracking=True,
        help="Inkubatoriyaning ichki sotuv hujjati yoki ta'minotchi "
             "fakturasi raqami.")

    # --- miqdor va narx
    product_id = fields.Many2one(
        'product.product', string="Mahsulot",
        domain="[('is_storable', '=', True)]",
        help="«Kunlik jo'ja» mahsuloti. Ombor harakati shu bo'yicha yoziladi.")
    dona = fields.Integer("Bosh soni", required=True, tracking=True)
    ortacha_vazn = fields.Float(
        "O'rtacha boshlang'ich vazn (kg)", digits='Product Unit',
        help="TZ 3-band: «boshlang'ich vazn, agar mavjud bo'lsa».")
    birlik_narx = fields.Monetary("1 bosh narxi", required=True, tracking=True)
    summa = fields.Monetary("Jami summa", compute='_compute_summa', store=True)

    holat = fields.Selection(
        [('draft', "Qoralama"), ('done', "Tasdiqlangan")],
        string="Holati", default='draft', required=True, tracking=True, copy=False)
    move_id = fields.Many2one(
        'stock.move', string="Ombor harakati", readonly=True, copy=False)
    izoh = fields.Text("Izoh")

    _dona_musbat = models.Constraint(
        'CHECK (dona > 0)', "Bosh soni noldan katta bo'lishi kerak.")
    _narx_musbat = models.Constraint(
        'CHECK (birlik_narx >= 0)', "Narx manfiy bo'lmaydi.")

    # ------------------------------------------------------------- compute
    @api.depends('partiya_id')
    def _compute_company_id(self):
        for k in self:
            k.company_id = k.partiya_id.company_id or self.env.company

    @api.depends('dona', 'birlik_narx')
    def _compute_summa(self):
        for k in self:
            k.summa = k.dona * k.birlik_narx

    # ----------------------------------------------------------- validatsiya
    @api.constrains('manba', 'kontragent_id')
    def _check_kontragent(self):
        for k in self:
            if k.manba == 'tashqi' and not k.kontragent_id:
                raise ValidationError(_(
                    "Tashqi xaridda kontragent majburiy — haqdorlik shu "
                    "kontragent bo'yicha shakllanadi («%s»).", k.name))

    # ------------------------------------------------------------ yaratish
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _("Yangi"):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'agronova.boquv.joja.kirim') or _("Yangi")
        return super().create(vals_list)

    # ----------------------------------------------------------- tasdiqlash
    def action_tasdiqlash(self):
        """Kirimni tasdiqlaydi: bosh soni, xarajat va partiya faollashuvi."""
        for k in self:
            if k.holat != 'draft':
                raise UserError(_("Faqat qoralama kirim tasdiqlanadi."))
            partiya = k.partiya_id
            partiya._tekshir_ochiq(_("jo'ja kirimi"))

            k._omborga_kirim()

            # Bosh sonini partiyaga qo'shamiz (bir partiyaga bir necha kirim
            # bo'lishi mumkin — masalan ikki mashinada kelgan).
            partiya.boshlangich_son += k.dona
            if not partiya.joja_sana:
                partiya.joja_sana = k.sana
            if k.ortacha_vazn and not partiya.boshlangich_vazn:
                partiya.boshlangich_vazn = k.ortacha_vazn

            # Jo'ja qiymati — partiyaning birinchi xarajati (TZ 14-band, 1-punkt).
            if k.summa:
                partiya._agronova_post_analytic(
                    name=_("Jo'ja kirimi: %(dona)s bosh (%(manba)s)",
                           dona=k.dona, manba=dict(MANBA)[k.manba]),
                    amount=-abs(k.summa),
                    date=k.sana,
                    unit_amount=k.dona,
                    product=k.product_id or None,
                    extra={'partner_id': k.kontragent_id.id or False},
                )

            k.holat = 'done'
            if partiya.holat in ('draft', 'kutilmoqda'):
                partiya.action_faollashtirish()
        return True

    def _omborga_kirim(self):
        """Jo'jani bino lokatsiyasiga kiritadi.

        Mahsulot ko'rsatilmagan bo'lsa ombor harakati yaratilmaydi — faqat
        moliyaviy hisob yuritiladi.
        """
        self.ensure_one()
        if not self.product_id:
            return
        bino = self.bino_id
        if not bino.location_id:
            bino._ensure_location()
        dest = bino.location_id
        if not dest:
            raise UserError(_(
                "«%s» binosida ombor lokatsiyasi yo'q.", bino.display_name))
        src = self.env.ref('stock.stock_location_suppliers',
                           raise_if_not_found=False)
        if not src:
            raise UserError(_("«Ta'minotchilar» lokatsiyasi topilmadi."))

        # Odoo 19 da `stock.move.name` yo'q — manba hujjat `origin` da.
        move = self.env['stock.move'].sudo().create({
            'origin': _("Jo'ja kirimi: %s", self.name),
            'date': fields.Datetime.to_datetime(self.sana),
            'product_id': self.product_id.id,
            'product_uom_qty': self.dona,
            'product_uom': self.product_id.uom_id.id,
            'location_id': src.id,
            'location_dest_id': dest.id,
            'company_id': self.company_id.id,
            'price_unit': self.birlik_narx,
            'partner_id': self.kontragent_id.id or False,
        })
        move._action_confirm()
        move._action_assign()
        move.quantity = self.dona
        move.picked = True
        move._action_done()
        self.move_id = move

    def action_storno(self):
        for k in self:
            if k.holat != 'done':
                raise UserError(_("Faqat tasdiqlangan kirim storno qilinadi."))
            partiya = k.partiya_id
            partiya.boshlangich_son -= k.dona
            if k.summa:
                partiya._agronova_post_analytic(
                    name=_("STORNO: jo'ja kirimi %s", k.name),
                    amount=abs(k.summa),
                    date=fields.Date.context_today(k),
                    tannarxga=True,
                )
            k.holat = 'draft'
            k.message_post(body=_("Kirim storno qilindi."))
        return True

    def write(self, vals):
        holat_ozgarish = set(vals) <= {
            'holat', 'move_id', 'message_follower_ids', 'message_ids',
        }
        if not holat_ozgarish:
            for k in self:
                if k.holat == 'done':
                    raise UserError(_(
                        "«%s» kirimi tasdiqlangan — tahrirlanmaydi. "
                        "Storno qiling.", k.display_name))
        return super().write(vals)

    def unlink(self):
        if any(k.holat == 'done' for k in self):
            raise UserError(_("Tasdiqlangan kirim o'chirilmaydi — storno qiling."))
        return super().unlink()
