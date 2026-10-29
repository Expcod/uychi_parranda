# -*- coding: utf-8 -*-
"""Kunlik jurnal — o'stirish va tuxum davri uchun.

Jurnal loyihaning eng ko'p to'ldiriladigan hujjati: har sex, har kun bitta
yozuv. Ikkita vazifasi bor:

1. **Bosh sonini yuritish** — nobud va brak shu yerdan yig'iladi, partiyaning
   joriy soni undan hisoblanadi.
2. **Resurs sarfini ombordan hisobdan chiqarish** — yem, dori, vaksina sex
   lokatsiyasidan «ishlab chiqarish» joyiga ko'chadi, FIFO qiymati esa
   partiyaning analitik hisobiga xarajat bo'lib tushadi.

Tasdiqlangandan keyin jurnal tahrirlanmaydi: tannarx shu qatorlardan
hisoblanadi, keyin o'zgarsa hisobot buziladi. Tuzatish storno orqali.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class AgroNovaOnaTovuqJurnalSarf(models.Model):
    """Jurnaldagi bitta resurs qatori (yem, dori, vaksina, suv)."""
    _name = 'agronova.ona_tovuq.jurnal.sarf'
    _description = "Ona tovuq — kunlik sarf qatori"

    jurnal_ostirish_id = fields.Many2one(
        'agronova.ona_tovuq.jurnal.ostirish', string="Jo'ja o'stirish jurnali",
        ondelete='cascade', index='btree_not_null')
    jurnal_tuxum_id = fields.Many2one(
        'agronova.ona_tovuq.jurnal.tuxum', string="Tuxum jurnali",
        ondelete='cascade', index='btree_not_null')
    product_id = fields.Many2one(
        'product.product', string="Mahsulot", required=True,
        domain="[('is_storable', '=', True)]")
    miqdor = fields.Float("Miqdor", required=True, digits='Product Unit')
    uom_id = fields.Many2one(
        'uom.uom', string="Birlik", required=True,
        compute='_compute_uom', store=True, readonly=False)
    move_id = fields.Many2one(
        'stock.move', string="Ombor harakati", readonly=True, copy=False,
        help="Jurnal tasdiqlanganda avtomat yaratiladi.")
    qiymat = fields.Monetary(
        "Qiymati", readonly=True, copy=False,
        help="FIFO bo'yicha hisobdan chiqqan qiymat. Qo'lda kiritilmaydi.")
    currency_id = fields.Many2one(
        'res.currency', compute='_compute_currency', readonly=True)

    _miqdor_musbat = models.Constraint(
        'CHECK (miqdor > 0)', "Sarf miqdori noldan katta bo'lishi kerak.")

    @api.depends('product_id')
    def _compute_uom(self):
        for line in self:
            line.uom_id = line.product_id.uom_id

    def _compute_currency(self):
        for line in self:
            jurnal = line.jurnal_ostirish_id or line.jurnal_tuxum_id
            line.currency_id = jurnal.company_id.currency_id

    def _jurnal(self):
        self.ensure_one()
        return self.jurnal_ostirish_id or self.jurnal_tuxum_id


class AgroNovaOnaTovuqJurnalMixin(models.AbstractModel):
    """Ikkala jurnalning umumiy qismi."""
    _name = 'agronova.ona_tovuq.jurnal.mixin'
    _description = "Ona tovuq — kunlik jurnal skeleti"
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    date = fields.Date(
        "Sana", required=True, default=fields.Date.context_today,
        tracking=True, index=True)
    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True, readonly=True,
        store=True, precompute=True, compute='_compute_company_id',
        help="Partiya qaysi korxonada bo'lsa — jurnal ham o'shanda. "
             "Foydalanuvchining joriy korxonasiga bog'liq emas.")
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)
    holat = fields.Selection(
        [('draft', "Qoralama"), ('posted', "Tasdiqlangan")],
        string="Holati", default='draft', required=True, tracking=True, copy=False)

    # DIQQAT — bosh sonini QO'SHIB bo'lmaydi. Oylik guruhda kunlik
    # qoldiqlar yig'ilsa 8 000 boshlik sex 74 841 bo'lib ko'rinadi.
    # Poda faqat kamayadi (nobud, brak, chiqim), shuning uchun guruhdagi
    # eng katta qiymat — davr boshidagi, eng kichigi — davr oxiridagi son.
    kun_boshi_son = fields.Integer(
        "Kun boshidagi bosh soni", readonly=True, aggregator='max',
        help="Partiyaning shu kungacha bo'lgan joriy soni — avtomat. "
             "Guruhlarda davr boshidagi son ko'rsatiladi.")
    nobud_son = fields.Integer("Nobud bo'lgan", tracking=True)
    brak_son = fields.Integer("Brak qilingan", tracking=True)
    kun_oxiri_son = fields.Integer(
        "Kun oxiridagi bosh soni", compute='_compute_kun_oxiri', store=True,
        aggregator='min',
        help="Guruhlarda davr oxiridagi son ko'rsatiladi.")
    nobud_sabab = fields.Char("Nobud sababi")

    suv_litr = fields.Float("Suv sarfi (litr)")
    harorat = fields.Float("Harorat (°C)")
    izoh = fields.Text("Izoh")

    sarf_ids = fields.One2many('agronova.ona_tovuq.jurnal.sarf', 'jurnal_ostirish_id',
                               string="Resurs sarfi")
    sarf_qiymat = fields.Monetary(
        "Sarf qiymati", compute='_compute_sarf_qiymat', store=True)

    _son_manfiy_emas = models.Constraint(
        'CHECK (nobud_son >= 0 AND brak_son >= 0)',
        "Nobud va brak soni manfiy bo'lmaydi.")

    # --------------------------------------------------------------- compute
    @api.depends('kun_boshi_son', 'nobud_son', 'brak_son')
    def _compute_kun_oxiri(self):
        for j in self:
            j.kun_oxiri_son = j.kun_boshi_son - j.nobud_son - j.brak_son

    @api.depends('sarf_ids.qiymat')
    def _compute_sarf_qiymat(self):
        for j in self:
            j.sarf_qiymat = sum(j.sarf_ids.mapped('qiymat'))

    # ---------------------------------------------------------- avtomat sex
    def _agronova_xodim_sexi(self):
        """Joriy foydalanuvchining biriktirilgan sexi (bo'lmasa bo'sh).

        Operator har kuni bir xil partiyani qo'lda tanlab o'tirmasligi uchun
        kerak — jurnal ochilganda uning sexidagi faol partiya o'zi qo'yiladi.
        """
        xodim = self.env['hr.employee'].sudo().search(
            [('user_id', '=', self.env.uid)], limit=1)
        return xodim.agronova_ot_sex_id

    # Diqqat: `partiya_id` abstrakt modelda yo'q (o'stirish va tuxum
    # jurnallari alohida modellar), shuning uchun bog'liqlik meros oluvchi
    # modelda e'lon qilinadi.
    def _compute_company_id(self):
        for j in self:
            j.company_id = j._partiya().company_id or self.env.company

    # --------------------------------------------------------------- partiya
    def _partiya(self):
        """Meros oluvchi model o'z partiyasini qaytaradi."""
        self.ensure_one()
        return self.env['agronova.ona_tovuq.partiya.mixin']

    def _sex(self):
        return self._partiya().sex_id

    # ---------------------------------------------------------------- yozish
    @api.model_create_multi
    def create(self, vals_list):
        jurnallar = super().create(vals_list)
        for j in jurnallar:
            j._partiya()._tekshir_ochiq(_("kunlik jurnal"))
            j.kun_boshi_son = j._partiya().joriy_son + j.nobud_son + j.brak_son
        return jurnallar

    def write(self, vals):
        if not self.env.context.get('agronova_jurnal_post'):
            for j in self:
                if j.holat == 'posted' and set(vals) - {'izoh', 'message_ids',
                                                        'message_follower_ids'}:
                    raise UserError(_(
                        "«%s» kunidagi jurnal tasdiqlangan — tahrirlanmaydi. "
                        "Tuzatish uchun storno qiling.", j.date))
        return super().write(vals)

    def unlink(self):
        for j in self:
            if j.holat == 'posted':
                raise UserError(_(
                    "Tasdiqlangan jurnalni o'chirib bo'lmaydi (%s).", j.date))
        return super().unlink()

    @api.constrains('date')
    def _check_kelajak(self):
        bugun = fields.Date.context_today(self)
        for j in self:
            if j.date > bugun:
                raise ValidationError(_("Kelajakdagi sana bilan jurnal ochilmaydi."))

    # -------------------------------------------------------------- tasdiqlash
    def action_tasdiqlash(self):
        """Sarfni ombordan chiqaradi va analitik hisobga xarajat yozadi."""
        for j in self:
            if j.holat == 'posted':
                continue
            partiya = j._partiya()
            partiya._tekshir_ochiq(_("jurnalni tasdiqlash"))
            j._sarfni_chiqarish()
            j.with_context(agronova_jurnal_post=True).holat = 'posted'
        return True

    def _sarfni_chiqarish(self):
        """Har bir sarf qatoriga ombor harakati yaratadi va uni yakunlaydi."""
        self.ensure_one()
        sex = self._sex()
        if not sex or not sex.location_id:
            if self.sarf_ids:
                raise UserError(_(
                    "«%s» sexida ombor lokatsiyasi yo'q — sarfni hisobdan "
                    "chiqarib bo'lmaydi.", sex.display_name or "?"))
            return
        src = sex.location_id
        dest = sex._production_location()
        partiya = self._partiya()
        for line in self.sarf_ids.filtered(lambda l: not l.move_id):
            move = self.env['stock.move'].sudo().create({
                'product_id': line.product_id.id,
                'product_uom_qty': line.miqdor,
                'product_uom': line.uom_id.id,
                'location_id': src.id,
                'location_dest_id': dest.id,
                'company_id': self.company_id.id,
                'origin': "%s / %s" % (partiya.name, self.date),
            })
            move._action_confirm()
            move._action_assign()
            move.quantity = line.miqdor
            move.picked = True
            move._action_done()
            line.move_id = move
            # FIFO qiymati — hisobdan chiqqan haqiqiy summa.
            # Odoo 19 da `stock.valuation.layer` yo'q, qiymat to'g'ridan-to'g'ri
            # `stock.move.value` maydonida turadi.
            qiymat = abs(move.value or 0.0)
            if not qiymat:
                # Baholanmaydigan mahsulot (masalan xizmat) — tannarxdan olamiz
                qiymat = abs(line.product_id.standard_price * line.miqdor)
            line.qiymat = qiymat
            if qiymat:
                partiya._agronova_post_analytic(
                    name=_("Sarf: %s (%s)", line.product_id.display_name, self.date),
                    amount=-qiymat,
                    date=self.date,
                    unit_amount=line.miqdor,
                    product=line.product_id,
                )

    def action_qoralamaga(self):
        """Faqat sarfsiz jurnalni qoralamaga qaytarish mumkin."""
        for j in self:
            if j.sarf_ids.filtered('move_id'):
                raise UserError(_(
                    "Sarf ombordan chiqarilgan — jurnalni qoralamaga "
                    "qaytarib bo'lmaydi. Storno qiling."))
            j.with_context(agronova_jurnal_post=True).holat = 'draft'
        return True


class AgroNovaOnaTovuqJurnalOstirish(models.Model):
    """O'stirish davri kunlik jurnali — tuxum yo'q, faqat o'sish va sarf."""
    _name = 'agronova.ona_tovuq.jurnal.ostirish'
    _description = "Ona tovuq — kunlik jurnal (jo'ja o'stirish)"
    _inherit = ['agronova.ona_tovuq.jurnal.mixin']

    partiya_id = fields.Many2one(
        'agronova.ona_tovuq.partiya.ostirish', string="Jo'ja o'stirish partiyasi",
        required=True, ondelete='cascade', index=True,
        domain="[('holat', '=', 'active')]",
        help="Faqat faol partiyalar — yopilganiga jurnal qo'shilmaydi.")
    sex_id = fields.Many2one(
        related='partiya_id.sex_id', string="Sex", store=True, readonly=True)
    ortacha_vazn = fields.Float(
        "O'rtacha vazn (kg)", digits='Product Unit',
        help="Nazorat tortishi — davriy, har kuni shart emas.")

    _partiya_sana_uniq = models.Constraint(
        'UNIQUE(partiya_id, date)',
        "Bu partiya uchun shu kunda jurnal allaqachon ochilgan.")

    def _partiya(self):
        self.ensure_one()
        return self.partiya_id

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        if 'partiya_id' in fields_list and not vals.get('partiya_id'):
            sex = self._agronova_xodim_sexi()
            if sex.aktiv_ostirish_id.holat == 'active':
                vals['partiya_id'] = sex.aktiv_ostirish_id.id
        return vals

    @api.depends('partiya_id')
    def _compute_company_id(self):
        return super()._compute_company_id()


class AgroNovaOnaTovuqJurnalTuxum(models.Model):
    """Tuxum davri kunlik jurnali — asosiy ishlab chiqarish hujjati."""
    _name = 'agronova.ona_tovuq.jurnal.tuxum'
    _description = "Ona tovuq — kunlik jurnal (ona tovuq)"
    _inherit = ['agronova.ona_tovuq.jurnal.mixin']

    partiya_id = fields.Many2one(
        'agronova.ona_tovuq.partiya.tuxum', string="Ona tovuq partiyasi",
        required=True, ondelete='cascade', index=True,
        domain="[('holat', '=', 'active')]",
        help="Faqat faol partiyalar — yopilganiga jurnal qo'shilmaydi.")
    sex_id = fields.Many2one(
        related='partiya_id.sex_id', string="Sex", store=True, readonly=True)
    sarf_ids = fields.One2many('agronova.ona_tovuq.jurnal.sarf', 'jurnal_tuxum_id',
                               string="Resurs sarfi")

    # --- poda tarkibi
    # Operator faqat «nobuddan nechtasi xo'roz» degan raqamni kiritadi
    # (odatda 0). Xo'roz va tovuq soni shundan hisoblanadi — har kuni
    # ikkalasini qayta yozish shart emas.
    nobud_xoroz = fields.Integer(
        "shundan xo'roz", tracking=True,
        help="Bugungi nobud va brakdan nechtasi xo'roz bo'lgani. "
             "Qolgani tovuq deb hisoblanadi.")
    xoroz_son = fields.Integer(
        "Xo'roz soni", compute='_compute_xoroz_tovuq', store=True,
        aggregator='max',
        help="Kun boshidagi xo'roz soni — avtomat. Tovuq soniga "
             "qo'shilmaydi: tuxum berish foizi faqat tovuqqa bo'linadi.")
    tovuq_son = fields.Integer(
        "Tovuq (davr boshi)", compute='_compute_xoroz_tovuq', store=True,
        aggregator='max',
        help="Kun boshidagi tuxum berayotgan tovuq soni — avtomat.")
    tovuq_oxiri = fields.Integer(
        "Tovuq (davr oxiri)", compute='_compute_xoroz_tovuq', store=True,
        aggregator='min',
        help="Kun oxiridagi tovuq soni: nobud va brakdan xo'rozlar "
             "ayrilgandan keyin qolgani.")

    # --- tuxum
    jami_tuxum = fields.Integer("Jami yig'ilgan tuxum (dona)", tracking=True)
    sifatli_tuxum = fields.Integer("Sifatli tuxum")
    brak_tuxum = fields.Integer("Brak tuxum")
    inkubatsiyaga_yarokli = fields.Integer("Inkubatsiyaga yaroqli")

    # Foizni ham qo'shib bo'lmaydi — guruhda o'rtachasi chiqadi.
    tuxum_berish_foiz = fields.Float(
        "Tuxum berish (%)", compute='_compute_foizlar', store=True,
        aggregator='avg',
        help="Jami tuxum / tuxum berayotgan tovuq soni × 100. "
             "Guruhlarda kunlik foizlarning o'rtachasi.")
    uruglanish_foiz = fields.Float(
        "Urug'lanish (%)", compute='_compute_foizlar', store=True,
        aggregator='avg',
        help="Inkubatsiyaga yaroqli / sifatli tuxum × 100.")

    # --- normadan chetlanish
    # Saqlanadi — ogohlantirishli kunlarni filtrlash va hisobotda ko'rsatish
    # uchun kerak (saqlanmaydigan maydon bo'yicha qidirib bo'lmaydi).
    norma_tuxum_berish = fields.Float(
        "Norma (%)", compute='_compute_ogohlantirish', store=True)
    ogohlantirish = fields.Char(
        "Ogohlantirish", compute='_compute_ogohlantirish', store=True,
        help="Normadan sezilarli chetlanish bo'lsa to'ldiriladi.")

    _partiya_sana_uniq = models.Constraint(
        'UNIQUE(partiya_id, date)',
        "Bu partiya uchun shu kunda jurnal allaqachon ochilgan.")
    _tuxum_manfiy_emas = models.Constraint(
        'CHECK (jami_tuxum >= 0 AND sifatli_tuxum >= 0 AND brak_tuxum >= 0)',
        "Tuxum soni manfiy bo'lmaydi.")

    def _partiya(self):
        self.ensure_one()
        return self.partiya_id

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        if 'partiya_id' in fields_list and not vals.get('partiya_id'):
            sex = self._agronova_xodim_sexi()
            if sex.aktiv_partiya_id.holat == 'active':
                vals['partiya_id'] = sex.aktiv_partiya_id.id
        return vals

    @api.depends('partiya_id')
    def _compute_company_id(self):
        return super()._compute_company_id()

    # --------------------------------------------------------------- compute
    @api.depends('partiya_id.xoroz_boshlangich', 'partiya_id.jurnal_ids.nobud_xoroz',
                 'date', 'kun_boshi_son', 'nobud_son', 'brak_son', 'nobud_xoroz')
    def _compute_xoroz_tovuq(self):
        """Kun boshidagi va kun oxiridagi tarkib.

        Partiyaning `xoroz_son` maydoniga bog'lanmaydi — u ham shu
        jurnallardan hisoblanadi, aylanma bog'liqlik chiqib ketardi.
        """
        for j in self:
            oldingi = j.partiya_id.jurnal_ids.filtered(
                lambda x, j=j: x.date and j.date and x.date < j.date)
            j.xoroz_son = max(
                j.partiya_id.xoroz_boshlangich - sum(oldingi.mapped('nobud_xoroz')), 0)
            j.tovuq_son = max(j.kun_boshi_son - j.xoroz_son, 0)
            # Bugungi yo'qotishdan xo'rozlar ayriladi — qolgani tovuq.
            tovuq_yoqotish = max(j.nobud_son + j.brak_son - j.nobud_xoroz, 0)
            j.tovuq_oxiri = max(j.tovuq_son - tovuq_yoqotish, 0)

    @api.constrains('nobud_xoroz', 'nobud_son', 'brak_son')
    def _check_nobud_xoroz(self):
        for j in self:
            if j.nobud_xoroz < 0:
                raise ValidationError(_("Xo'roz soni manfiy bo'lmaydi."))
            if j.nobud_xoroz > j.nobud_son + j.brak_son:
                raise ValidationError(_(
                    "Xo'rozlar soni (%(x)s) nobud va brak yig'indisidan "
                    "(%(n)s) ko'p bo'lmaydi.",
                    x=j.nobud_xoroz, n=j.nobud_son + j.brak_son))

    @api.depends('jami_tuxum', 'sifatli_tuxum', 'inkubatsiyaga_yarokli',
                 'tovuq_son', 'kun_boshi_son')
    def _compute_foizlar(self):
        for j in self:
            baza = j.tovuq_son or j.kun_boshi_son
            j.tuxum_berish_foiz = (j.jami_tuxum / baza * 100.0) if baza else 0.0
            j.uruglanish_foiz = (
                j.inkubatsiyaga_yarokli / j.sifatli_tuxum * 100.0
                if j.sifatli_tuxum else 0.0)

    @api.depends('tuxum_berish_foiz', 'partiya_id.zot_id', 'partiya_id.yosh_hafta')
    def _compute_ogohlantirish(self):
        Normativ = self.env['agronova.ona_tovuq.normativ']
        for j in self:
            norma = Normativ.qiymat('tuxum_berish_foiz',
                                    zot=j.partiya_id.zot_id,
                                    hafta=j.partiya_id.yosh_hafta)
            j.norma_tuxum_berish = norma
            xabar = False
            if norma and j.tuxum_berish_foiz and j.tuxum_berish_foiz < norma * 0.9:
                xabar = _("Tuxum berish normadan past: %(fakt).1f%% / %(norma).1f%%",
                          fakt=j.tuxum_berish_foiz, norma=norma)
            elif j.kun_boshi_son and j.nobud_son > j.kun_boshi_son * 0.005:
                xabar = _("Nobudgarchilik yuqori: %s bosh", j.nobud_son)
            j.ogohlantirish = xabar

    @api.constrains('jami_tuxum', 'sifatli_tuxum', 'brak_tuxum',
                    'inkubatsiyaga_yarokli')
    def _check_tuxum_tarkibi(self):
        for j in self:
            if j.sifatli_tuxum + j.brak_tuxum > j.jami_tuxum:
                raise ValidationError(_(
                    "Sifatli va brak tuxum yig'indisi jami tuxumdan ko'p "
                    "bo'lmaydi (%(s)s + %(b)s > %(j)s).",
                    s=j.sifatli_tuxum, b=j.brak_tuxum, j=j.jami_tuxum))
            if j.inkubatsiyaga_yarokli > j.sifatli_tuxum:
                raise ValidationError(_(
                    "Inkubatsiyaga yaroqli tuxum sifatli tuxumdan ko'p "
                    "bo'lmaydi (%(i)s > %(s)s).",
                    i=j.inkubatsiyaga_yarokli, s=j.sifatli_tuxum))

    def action_tasdiqlash(self):
        """Sarfdan tashqari yig'ilgan tuxumni ham omborga kirim qiladi."""
        res = super().action_tasdiqlash()
        for j in self:
            j._tuxum_kirim_yaratish()
        return res

    def _tuxum_kirim_yaratish(self):
        """Kunlik yig'ilgan tuxumga kirim hujjatini ochadi."""
        self.ensure_one()
        if not self.jami_tuxum:
            return
        mavjud = self.env['agronova.ona_tovuq.tuxum.kirim'].search(
            [('jurnal_id', '=', self.id)], limit=1)
        if mavjud:
            return mavjud
        return self.env['agronova.ona_tovuq.tuxum.kirim'].create({
            'jurnal_id': self.id,
            'partiya_id': self.partiya_id.id,
            'date': self.date,
            'company_id': self.company_id.id,
        })
