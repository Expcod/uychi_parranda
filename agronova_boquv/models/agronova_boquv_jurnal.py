# -*- coding: utf-8 -*-
"""Kunlik jurnal — partiyaning eng ko'p to'ldiriladigan hujjati.

Har partiya, har kun bitta yozuv. Ikkita vazifasi bor:

1. **Bosh sonini yuritish** — nobud shu yerdan yig'iladi, partiyaning tirik
   soni undan hisoblanadi (TZ 12-band).
2. **Resurs sarfini ombordan hisobdan chiqarish** — yem, dori, vaksina bino
   lokatsiyasidan «ishlab chiqarish» joyiga ko'chadi, FIFO qiymati esa
   partiyaning analitik hisobiga xarajat bo'lib tushadi (TZ 5, 6, 7-band).

**Yem kg da yuritiladi** — FCR (yem konversiyasi) shundan hisoblanadi.
Mahsulot boshqa birlikda bo'lsa (qop, tonna) kg ga o'giriladi.

Tasdiqlangandan keyin jurnal tahrirlanmaydi: tannarx shu qatorlardan
hisoblanadi, keyin o'zgarsa hisobot buziladi. Tuzatish storno orqali.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class AgroNovaBoquvJurnalSarf(models.Model):
    """Jurnaldagi bitta resurs qatori (yem, dori, vaksina)."""
    _name = 'agronova.boquv.jurnal.sarf'
    _description = "Boquv — kunlik sarf qatori"

    jurnal_id = fields.Many2one(
        'agronova.boquv.jurnal', string="Kunlik jurnal",
        required=True, ondelete='cascade', index=True)
    product_id = fields.Many2one(
        'product.product', string="Mahsulot", required=True,
        domain="[('is_storable', '=', True)]")
    tur = fields.Selection(
        [('yem', "Yem"),
         ('dori', "Dori / vaksina"),
         ('dezinfeksiya', "Dezinfeksiya vositasi"),
         ('boshqa', "Boshqa material")],
        string="Turi", required=True, default='yem',
        help="«Yem» belgilangan qatorlar kg ga o'girilib FCR hisobiga kiradi.")
    miqdor = fields.Float("Miqdor", required=True, digits='Product Unit')
    uom_id = fields.Many2one(
        'uom.uom', string="Birlik", required=True,
        compute='_compute_uom', store=True, readonly=False, precompute=True,
        help="Mahsulotdan avtomat olinadi, kerak bo'lsa o'zgartiriladi. "
             "`precompute` — INSERT dan oldin hisoblanadi, aks holda "
             "required maydon bo'sh bo'lib qoladi.")
    miqdor_kg = fields.Float(
        "Miqdor (kg)", compute='_compute_miqdor_kg', store=True,
        precompute=True, digits='Product Unit',
        help="Yem sarfini FCR uchun kg ga keltirish. Birlik kg ga "
             "o'girilmasa (masalan dona) 0 bo'ladi.")
    move_id = fields.Many2one(
        'stock.move', string="Ombor harakati", readonly=True, copy=False,
        help="Jurnal tasdiqlanganda avtomat yaratiladi.")
    qiymat = fields.Monetary(
        "Qiymati", readonly=True, copy=False,
        help="FIFO bo'yicha hisobdan chiqqan qiymat. Qo'lda kiritilmaydi.")
    currency_id = fields.Many2one(
        'res.currency', related='jurnal_id.currency_id', readonly=True)
    izoh = fields.Char("Izoh")

    _miqdor_musbat = models.Constraint(
        'CHECK (miqdor > 0)', "Sarf miqdori noldan katta bo'lishi kerak.")

    @api.depends('product_id')
    def _compute_uom(self):
        for line in self:
            line.uom_id = line.product_id.uom_id

    @api.depends('miqdor', 'uom_id', 'tur')
    def _compute_miqdor_kg(self):
        """Yem miqdorini kg ga o'giradi — FCR bazasi."""
        kg = self.env.ref('uom.product_uom_kgm', raise_if_not_found=False)
        for line in self:
            if line.tur != 'yem' or not line.uom_id or not kg:
                line.miqdor_kg = 0.0
                continue
            if line.uom_id == kg:
                line.miqdor_kg = line.miqdor
            elif line.uom_id.relative_uom_id == kg.relative_uom_id \
                    or line.uom_id.relative_uom_id == kg:
                # Bir o'lchov turkumida — Odoo konversiyasi ishlaydi.
                line.miqdor_kg = line.uom_id._compute_quantity(line.miqdor, kg)
            else:
                # Dona, litr va h.k. — kg ga o'girilmaydi, FCR ga kirmaydi.
                line.miqdor_kg = 0.0


class AgroNovaBoquvJurnal(models.Model):
    _name = 'agronova.boquv.jurnal'
    _description = "Boquv — kunlik jurnal"
    _inherit = ['mail.thread']
    _order = 'sana desc, id desc'

    name = fields.Char("Hujjat", compute='_compute_name', store=True)
    sana = fields.Date(
        "Sana", required=True, default=fields.Date.context_today,
        tracking=True, index=True)
    partiya_id = fields.Many2one(
        'agronova.boquv.partiya', string="Partiya", required=True, tracking=True,
        ondelete='restrict', index=True,
        domain="[('holat', '=', 'active')]")
    bino_id = fields.Many2one(
        related='partiya_id.bino_id', string="Bino", store=True, readonly=True)
    filial_id = fields.Many2one(
        related='partiya_id.filial_id', string="Filial", store=True, readonly=True)
    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True, readonly=True,
        store=True, precompute=True, compute='_compute_company_id')
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)

    holat = fields.Selection(
        [('draft', "Qoralama"), ('posted', "Tasdiqlangan")],
        string="Holati", default='draft', required=True, tracking=True, copy=False)

    # --- bosh soni
    kun_boshi_son = fields.Integer(
        "Kun boshidagi bosh soni", readonly=True,
        help="Partiyaning shu kungacha bo'lgan tirik soni — avtomat.")
    nobud_son = fields.Integer("Nobud bo'lgan", tracking=True)
    nobud_sabab = fields.Selection(
        [('kasallik', "Kasallik"),
         ('harorat', "Harorat rejimi"),
         ('yem_suv', "Yem yoki suv muammosi"),
         ('jarohat', "Jarohat / bosilib qolish"),
         ('nomalum', "Noma'lum"),
         ('boshqa', "Boshqa")],
        string="Nobud sababi", tracking=True,
        help="TZ 12-band: har yozuvda sabab ko'rsatiladi.")
    kun_oxiri_son = fields.Integer(
        "Kun oxiridagi bosh soni", compute='_compute_kun_oxiri', store=True)

    # --- sharoit
    suv_litr = fields.Float("Suv sarfi (litr)")
    harorat = fields.Float("O'rtacha harorat (°C)", digits=(12, 1))

    # --- sarf
    sarf_ids = fields.One2many(
        'agronova.boquv.jurnal.sarf', 'jurnal_id', string="Resurs sarfi")
    sarf_qiymat = fields.Monetary(
        "Sarf qiymati", compute='_compute_sarf', store=True)
    yem_kg = fields.Float(
        "Yem sarfi (kg)", compute='_compute_sarf', store=True,
        digits='Product Unit',
        help="Shu kundagi yem sarfi kg da — partiyaning FCR hisobiga kiradi.")

    mas_ul_id = fields.Many2one(
        'hr.employee', string="Mas'ul xodim", tracking=True)
    izoh = fields.Text("Izoh")

    _son_manfiy_emas = models.Constraint(
        'CHECK (nobud_son >= 0)', "Nobud soni manfiy bo'lmaydi.")
    _partiya_sana_uniq = models.Constraint(
        'UNIQUE(partiya_id, sana)',
        "Bu partiya uchun shu sanadagi jurnal allaqachon mavjud — "
        "kuniga bitta yozuv yuritiladi.")

    # ------------------------------------------------------------- compute
    @api.depends('partiya_id', 'sana')
    def _compute_name(self):
        for j in self:
            j.name = ("%s / %s" % (j.partiya_id.name, j.sana)
                      if j.partiya_id and j.sana else _("Yangi"))

    @api.depends('partiya_id')
    def _compute_company_id(self):
        for j in self:
            j.company_id = j.partiya_id.company_id or self.env.company

    @api.depends('kun_boshi_son', 'nobud_son')
    def _compute_kun_oxiri(self):
        for j in self:
            j.kun_oxiri_son = j.kun_boshi_son - j.nobud_son

    @api.depends('sarf_ids.qiymat', 'sarf_ids.miqdor_kg')
    def _compute_sarf(self):
        for j in self:
            j.sarf_qiymat = sum(j.sarf_ids.mapped('qiymat'))
            j.yem_kg = sum(j.sarf_ids.mapped('miqdor_kg'))

    @api.onchange('partiya_id')
    def _onchange_partiya(self):
        """Kun boshidagi sonni partiyadan oladi."""
        if self.partiya_id:
            self.kun_boshi_son = self.partiya_id.joriy_son
            if not self.mas_ul_id:
                self.mas_ul_id = self.partiya_id.brigadir_id

    # ----------------------------------------------------------- validatsiya
    @api.constrains('nobud_son', 'kun_boshi_son')
    def _check_nobud(self):
        for j in self:
            if j.nobud_son > j.kun_boshi_son:
                raise ValidationError(_(
                    "«%(nom)s»: nobud soni (%(nobud)s) kun boshidagi bosh "
                    "sonidan (%(bosh)s) ko'p bo'lmaydi.",
                    nom=j.display_name, nobud=j.nobud_son, bosh=j.kun_boshi_son))

    @api.constrains('sana', 'partiya_id')
    def _check_sana(self):
        for j in self:
            p = j.partiya_id
            if p.joja_sana and j.sana < p.joja_sana:
                raise ValidationError(_(
                    "«%(nom)s» jurnali jo'ja kelgan sanadan (%(joja)s) "
                    "oldin bo'lmaydi.", nom=j.display_name, joja=p.joja_sana))
            if j.sana > fields.Date.context_today(j):
                raise ValidationError(_(
                    "Kelajakdagi sana bilan jurnal kiritilmaydi."))

    # ------------------------------------------------------------ yaratish
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'kun_boshi_son' not in vals and vals.get('partiya_id'):
                partiya = self.env['agronova.boquv.partiya'].browse(vals['partiya_id'])
                vals['kun_boshi_son'] = partiya.joriy_son
        return super().create(vals_list)

    # ----------------------------------------------------------- tasdiqlash
    def action_tasdiqlash(self):
        """Jurnalni tasdiqlaydi: resursni ombordan chiqaradi va xarajatni yozadi."""
        for j in self:
            if j.holat != 'draft':
                raise UserError(_("Faqat qoralama jurnal tasdiqlanadi."))
            j.partiya_id._tekshir_ochiq(_("kunlik jurnal"))
            j._sarfni_chiqarish()
            j.holat = 'posted'
        return True

    def _sarfni_chiqarish(self):
        """Har bir sarf qatori uchun ombor harakati yaratadi va tasdiqlaydi.

        Qiymat FIFO bo'yicha `stock.move` dan olinadi va partiyaning
        analitik hisobiga xarajat bo'lib yoziladi.
        """
        self.ensure_one()
        bino = self.bino_id
        if not bino.location_id:
            bino._ensure_location()
        src = bino.location_id
        if not src:
            raise UserError(_(
                "«%s» binosida ombor lokatsiyasi yo'q — resurs hisobdan "
                "chiqarilmaydi. Filialga ombor biriktiring.",
                bino.display_name))
        dest = bino._production_location()

        Move = self.env['stock.move'].sudo()
        for line in self.sarf_ids.filtered(lambda l: not l.move_id):
            # Odoo 19 da `stock.move.name` yo'q — manba hujjat `origin` da.
            move = Move.create({
                'origin': self.display_name,
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
            # FIFO qiymati — hisobdan chiqqan haqiqiy tannarx.
            # Odoo 19 da `stock.valuation.layer` yo'q, qiymat to'g'ridan-
            # to'g'ri `stock.move.value` maydonida turadi.
            qiymat = abs(move.value or 0.0)
            if not qiymat:
                # Baholanmaydigan mahsulot — kartochkadagi tannarxdan olamiz.
                qiymat = abs(line.product_id.standard_price * line.miqdor)
            line.qiymat = qiymat
            if qiymat:
                self.partiya_id._agronova_post_analytic(
                    name=_("%(tur)s: %(mahsulot)s",
                           tur=dict(line._fields['tur'].selection)[line.tur],
                           mahsulot=line.product_id.display_name),
                    amount=-abs(qiymat),
                    date=self.sana,
                    unit_amount=line.miqdor,
                    product=line.product_id,
                )

    def action_storno(self):
        """Tasdiqlangan jurnalni storno qiladi — yozuv o'chirilmaydi."""
        for j in self:
            if j.holat != 'posted':
                raise UserError(_("Faqat tasdiqlangan jurnal storno qilinadi."))
            for line in j.sarf_ids.filtered('qiymat'):
                j.partiya_id._agronova_post_analytic(
                    name=_("STORNO: %s", line.product_id.display_name),
                    amount=abs(line.qiymat),
                    date=fields.Date.context_today(j),
                    tannarxga=True,
                )
            j.holat = 'draft'
            j.message_post(body=_("Jurnal storno qilindi."))
        return True

    # ------------------------------------------------------------ qulf
    def write(self, vals):
        holat_ozgarish = set(vals) <= {
            'holat', 'message_follower_ids', 'message_ids', 'activity_ids',
        }
        if not holat_ozgarish:
            for j in self:
                if j.holat == 'posted':
                    raise UserError(_(
                        "«%s» jurnali tasdiqlangan — tahrirlanmaydi. "
                        "Xato bo'lsa storno qiling.", j.display_name))
        return super().write(vals)

    def unlink(self):
        if any(j.holat == 'posted' for j in self):
            raise UserError(_(
                "Tasdiqlangan jurnal o'chirilmaydi — storno qiling."))
        return super().unlink()
