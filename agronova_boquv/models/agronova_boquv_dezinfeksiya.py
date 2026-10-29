# -*- coding: utf-8 -*-
"""Dezinfeksiya hujjati (TZ 8-band).

Yangi partiya boshlanishidan oldin bino to'liq dezinfeksiya qilinadi.
Xarajat: dezinfeksiya vositalari + ishchilar mehnati.

**Vaqt bo'yicha ziddiyat va uning yechimi.** Dezinfeksiya partiyadan
*oldin* bo'ladi, lekin TZ uning xarajatini *keyingi partiyaga* biriktirishni
talab qiladi:

    «3-seh dezinfeksiya qilindi → 2026-001 partiya boshlanadi →
     dezinfeksiya xarajati ushbu partiyaga biriktiriladi.»

Shuning uchun hujjat ikki bosqichda ishlaydi:

1. **Tasdiqlash** — vosita ombordan chiqadi va xarajat *binoning* analitik
   hisobiga yoziladi (partiya hali yo'q);
2. **Partiyaga biriktirish** — partiya ochilgandan keyin xarajat binodan
   partiyaga ko'chiriladi (binoda teskari, partiyada to'g'ri qator).

Ikkinchi bosqich qo'lda ham, partiya ochilganda avtomat ham bajariladi:
`agronova.boquv.partiya.action_ochish()` shu binoda biriktirilmagan
dezinfeksiya hujjatlarini topib o'ziga tortadi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AgroNovaBoquvDezinfeksiyaSarf(models.Model):
    """Dezinfeksiyada ishlatilgan vosita."""
    _name = 'agronova.boquv.dezinfeksiya.sarf'
    _description = "Boquv — dezinfeksiya sarfi"

    dezinfeksiya_id = fields.Many2one(
        'agronova.boquv.dezinfeksiya', string="Hujjat", required=True,
        ondelete='cascade', index=True)
    product_id = fields.Many2one(
        'product.product', string="Vosita", required=True,
        domain="[('is_storable', '=', True)]")
    miqdor = fields.Float("Miqdor", required=True, digits='Product Unit')
    uom_id = fields.Many2one(
        'uom.uom', string="Birlik", required=True,
        compute='_compute_uom', store=True, readonly=False, precompute=True)
    move_id = fields.Many2one(
        'stock.move', string="Ombor harakati", readonly=True, copy=False)
    qiymat = fields.Monetary(
        "Qiymati", readonly=True, copy=False,
        help="FIFO bo'yicha hisobdan chiqqan qiymat.")
    currency_id = fields.Many2one(
        'res.currency', related='dezinfeksiya_id.currency_id', readonly=True)

    _miqdor_musbat = models.Constraint(
        'CHECK (miqdor > 0)', "Sarf miqdori noldan katta bo'lishi kerak.")

    @api.depends('product_id')
    def _compute_uom(self):
        for line in self:
            line.uom_id = line.product_id.uom_id


class AgroNovaBoquvDezinfeksiya(models.Model):
    _name = 'agronova.boquv.dezinfeksiya'
    _description = "Boquv — dezinfeksiya"
    _inherit = ['mail.thread']
    _order = 'sana desc, id desc'

    name = fields.Char(
        "Hujjat raqami", default=lambda self: _("Yangi"),
        copy=False, readonly=True, index=True)
    sana = fields.Date(
        "Dezinfeksiya sanasi", required=True, index=True, tracking=True,
        default=fields.Date.context_today)
    bino_id = fields.Many2one(
        'agronova.boquv.bino', string="Bino", required=True, tracking=True,
        ondelete='restrict', index=True)
    filial_id = fields.Many2one(
        related='bino_id.filial_id', string="Filial", store=True, readonly=True)
    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True, readonly=True,
        store=True, precompute=True, compute='_compute_company_id')
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)

    # --- xarajat tarkibi
    sarf_ids = fields.One2many(
        'agronova.boquv.dezinfeksiya.sarf', 'dezinfeksiya_id',
        string="Ishlatilgan vositalar")
    vosita_qiymat = fields.Monetary(
        "Vositalar qiymati", compute='_compute_summa', store=True)
    ishchi_kun = fields.Float(
        "Ishchi-kun", digits=(12, 2),
        help="Dezinfeksiyada ishlagan kishi-kunlar soni (TZ 8-band).")
    ishchi_kun_narx = fields.Monetary(
        "1 ishchi-kun narxi",
        help="Kunlik ishchi haqi. Xarajat kategoriyasidan olinadi.")
    mehnat_qiymat = fields.Monetary(
        "Mehnat qiymati", compute='_compute_summa', store=True)
    boshqa_qiymat = fields.Monetary(
        "Boshqa xarajat", help="TZ 8-band: «boshqa zarur xarajatlar».")
    jami_summa = fields.Monetary(
        "Jami summa", compute='_compute_summa', store=True)

    mas_ul_id = fields.Many2one('hr.employee', string="Mas'ul xodim")
    izoh = fields.Text("Izoh")

    # --- partiyaga biriktirish
    partiya_id = fields.Many2one(
        'agronova.boquv.partiya', string="Biriktirilgan partiya",
        readonly=True, copy=False, index='btree_not_null',
        help="Dezinfeksiyadan keyin ochilgan partiya. Xarajat shunga "
             "ko'chiriladi (TZ 8-band).")
    holat = fields.Selection(
        [('draft', "Qoralama"),
         ('done', "Tasdiqlangan"),
         ('biriktirilgan', "Partiyaga biriktirilgan")],
        string="Holati", default='draft', required=True, tracking=True,
        copy=False)
    analytic_line_ids = fields.Many2many(
        'account.analytic.line', string="Analitik qatorlar",
        readonly=True, copy=False)

    # ------------------------------------------------------------- compute
    @api.depends('bino_id')
    def _compute_company_id(self):
        for d in self:
            d.company_id = d.bino_id.company_id or self.env.company

    @api.depends('sarf_ids.qiymat', 'ishchi_kun', 'ishchi_kun_narx',
                 'boshqa_qiymat')
    def _compute_summa(self):
        for d in self:
            d.vosita_qiymat = sum(d.sarf_ids.mapped('qiymat'))
            d.mehnat_qiymat = d.ishchi_kun * d.ishchi_kun_narx
            d.jami_summa = d.vosita_qiymat + d.mehnat_qiymat + d.boshqa_qiymat

    # ------------------------------------------------------------ yaratish
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _("Yangi"):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'agronova.boquv.dezinfeksiya') or _("Yangi")
        return super().create(vals_list)

    # ----------------------------------------------------------- tasdiqlash
    def action_tasdiqlash(self):
        """Vositani ombordan chiqaradi, xarajatni binoga yozadi."""
        for d in self:
            if d.holat != 'draft':
                raise UserError(_("Faqat qoralama hujjat tasdiqlanadi."))
            d._sarfni_chiqarish()
            d._binoga_yozish()
            d.holat = 'done'
            # Bino dezinfeksiya holatiga o'tadi — doimiy xarajatdan m² ulushi
            # to'liq olinadi (yakuniy TZ).
            if d.bino_id.holat == 'no_aktiv':
                d.bino_id.holat = 'dizinfeksiya'
            d.message_post(body=_(
                "Dezinfeksiya tasdiqlandi. Jami %(summa)s "
                "(vosita %(vosita)s, mehnat %(mehnat)s). Xarajat binoda "
                "turadi, partiya ochilganda unga ko'chadi.",
                summa=d.jami_summa, vosita=d.vosita_qiymat,
                mehnat=d.mehnat_qiymat))
        return True

    def _sarfni_chiqarish(self):
        """Vositalarni bino lokatsiyasidan hisobdan chiqaradi."""
        self.ensure_one()
        if not self.sarf_ids:
            return
        bino = self.bino_id
        if not bino.location_id:
            bino._ensure_location()
        src = bino.location_id
        if not src:
            raise UserError(_(
                "«%s» binosida ombor lokatsiyasi yo'q — vositani hisobdan "
                "chiqarib bo'lmaydi. Filialga ombor biriktiring.",
                bino.display_name))
        dest = bino._production_location()

        Move = self.env['stock.move'].sudo()
        for line in self.sarf_ids.filtered(lambda l: not l.move_id):
            move = Move.create({
                'origin': _("Dezinfeksiya: %s", self.name),
                'date': fields.Datetime.to_datetime(self.sana),
                'product_id': line.product_id.id,
                'product_uom_qty': line.miqdor,
                'product_uom': line.uom_id.id,
                'location_id': src.id,
                'location_dest_id': dest.id,
                'company_id': self.company_id.id,
            })
            move._action_confirm()
            move._action_assign()
            move.quantity = line.miqdor
            move.picked = True
            move._action_done()
            line.move_id = move
            qiymat = abs(move.value or 0.0)
            if not qiymat:
                qiymat = abs(line.product_id.standard_price * line.miqdor)
            line.qiymat = qiymat

    def _binoga_yozish(self):
        """Jami xarajatni binoning analitik hisobiga yozadi."""
        self.ensure_one()
        self.invalidate_recordset(['vosita_qiymat', 'jami_summa'])
        if not self.jami_summa:
            return
        line = self.bino_id._agronova_post_analytic(
            name=_("Dezinfeksiya %s", self.name),
            amount=-abs(self.jami_summa),
            date=self.sana,
        )
        self.analytic_line_ids = [(6, 0, line.ids)]

    # -------------------------------------------------- partiyaga biriktirish
    def action_partiyaga_biriktirish(self, partiya=None):
        """Xarajatni binodan partiyaga ko'chiradi (TZ 8-band).

        Binoda teskari (musbat) qator, partiyada xarajat (manfiy) qator
        yoziladi — shunda binoning oraliq hisobi bo'shaydi va tannarx
        partiyada to'planadi.
        """
        for d in self:
            if d.holat != 'done':
                raise UserError(_(
                    "Faqat tasdiqlangan dezinfeksiya partiyaga biriktiriladi."))
            target = partiya or d._keyingi_partiya()
            if not target:
                raise UserError(_(
                    "«%s» binosida biriktiriladigan partiya topilmadi. "
                    "Avval partiya oching.", d.bino_id.display_name))
            target._tekshir_ochiq(_("dezinfeksiya xarajati"))

            if d.jami_summa:
                # Binoda teskari yozuv — oraliq hisob bo'shaydi.
                d.bino_id._agronova_post_analytic(
                    name=_("Dezinfeksiya %(nom)s → %(partiya)s",
                           nom=d.name, partiya=target.name),
                    amount=abs(d.jami_summa),
                    date=fields.Date.context_today(d),
                    tannarxga=False,
                )
                # Partiyada xarajat.
                target._agronova_post_analytic(
                    name=_("Dezinfeksiya %s", d.name),
                    amount=-abs(d.jami_summa),
                    date=target.ochilish_sana or d.sana,
                )
            d.partiya_id = target
            d.holat = 'biriktirilgan'
            d.message_post(body=_(
                "Xarajat «%s» partiyasiga ko'chirildi.", target.name))
            target.message_post(body=_(
                "«%(nom)s» dezinfeksiya xarajati biriktirildi: %(summa)s.",
                nom=d.name, summa=d.jami_summa))
        return True

    def _keyingi_partiya(self):
        """Dezinfeksiyadan keyin shu binoda ochilgan birinchi partiya."""
        self.ensure_one()
        return self.env['agronova.boquv.partiya'].search([
            ('bino_id', '=', self.bino_id.id),
            ('ochilish_sana', '>=', self.sana),
            ('holat', 'not in', ('cancel',)),
        ], order='ochilish_sana, id', limit=1)

    @api.model
    def _biriktirilmaganlar(self, bino):
        """Binoda partiyaga biriktirilmagan dezinfeksiya hujjatlari."""
        return self.search([
            ('bino_id', '=', bino.id),
            ('holat', '=', 'done'),
        ], order='sana')

    # ------------------------------------------------------------ storno
    def action_storno(self):
        for d in self:
            if d.holat == 'draft':
                raise UserError(_("Qoralama hujjat storno qilinmaydi."))
            bugun = fields.Date.context_today(d)
            for line in d.analytic_line_ids:
                line.copy({
                    'name': _("STORNO: %s", line.name),
                    'amount': -line.amount,
                    'date': bugun,
                })
            if d.holat == 'biriktirilgan' and d.partiya_id and d.jami_summa:
                d.partiya_id._agronova_post_analytic(
                    name=_("STORNO: dezinfeksiya %s", d.name),
                    amount=abs(d.jami_summa),
                    date=bugun,
                    tannarxga=False,
                )
            d.holat = 'draft'
            d.partiya_id = False
            d.message_post(body=_("Dezinfeksiya hujjati storno qilindi."))
        return True

    def write(self, vals):
        qulf_tashqari = {'holat', 'partiya_id', 'analytic_line_ids',
                         'message_follower_ids', 'message_ids', 'izoh'}
        if set(vals) - qulf_tashqari:
            for d in self:
                if d.holat != 'draft':
                    raise UserError(_(
                        "«%s» hujjati tasdiqlangan — tahrirlanmaydi. "
                        "Storno qiling.", d.display_name))
        return super().write(vals)

    def unlink(self):
        if any(d.holat != 'draft' for d in self):
            raise UserError(_("Faqat qoralama dezinfeksiya o'chiriladi."))
        return super().unlink()
