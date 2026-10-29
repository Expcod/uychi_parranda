# -*- coding: utf-8 -*-
"""So'yimga jo'natma — partiyaning chiqishi (TZ 18-band).

45 kunlik boqish yakunlangach tirik tovuqlar so'yish filialiga **ichki
sotuv** orqali beriladi. Bu ham oddiy ko'chirish emas: Boquv bo'limining
daromadi shundan shakllanadi va foyda/zarar aniqlanadi (TZ 19-band):

    Foyda/Zarar = ichki sotuv summasi − partiyaning jami tannarxi

**Oraliq jo'natmalar** bo'ladi (yakuniy TZ) — bitta partiyadan bir necha
marta jo'natilishi mumkin, hammasi bir kunda emas.

**Yo'l yo'qotishi** (yakuniy TZ, «So'yimga jo'natish»): jo'natilgan va
qabul qilingan vazn orasidagi farq. **3% gacha** binoga (normal transport
yo'qotishi), ortig'i **tekshiruv aktiga** tushadi. Qabul vazni jo'natish
vaznidan ko'p chiqsa — bino foydasiga yoziladi.

So'yish moduli hali yozilmagan, shuning uchun qabul ma'lumotlari shu
hujjatda qo'lda kiritiladi. Modul kelganda `soyish_hujjat` maydoniga
ulanadi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# Yo'l yo'qotishining normal chegarasi (%). Ortig'i tekshiruv aktiga.
YOL_YOQOTISH_NORMA_FOIZ = 3.0

CHIQIM_TURI = [
    ('soyish', "So'yish filialiga"),
    ('boshqa_bino', "Boshqa binoga o'tkazma"),
    ('ehson', "Ehson"),
    ('qolda_soyilgan', "Qo'lda so'yilgan"),
]


class AgroNovaBoquvJonatma(models.Model):
    _name = 'agronova.boquv.jonatma'
    _description = "Boquv — so'yimga jo'natma"
    _inherit = ['mail.thread']
    _order = 'sana desc, id desc'

    name = fields.Char(
        "Hujjat raqami", default=lambda self: _("Yangi"),
        copy=False, readonly=True, index=True)
    sana = fields.Date(
        "Jo'natish sanasi", required=True, default=fields.Date.context_today,
        tracking=True, index=True)
    tur = fields.Selection(
        CHIQIM_TURI, string="Chiqim turi", required=True, default='soyish',
        tracking=True,
        help="Mijoz izohi: partiyadan chiqqan har bir bosh hisobga olinishi "
             "kerak — so'yishga ketgani ham, ehson qilingani ham, qo'lda "
             "so'yilgani ham.")
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

    # --- jo'natish ma'lumotlari (yakuniy TZ: mashina, yuk xati, manzil)
    bosh_soni = fields.Integer("Jo'natilgan bosh soni", required=True, tracking=True)
    jonatilgan_vazn = fields.Float(
        "Jo'natilgan tirik vazn (kg)", required=True, digits='Product Unit',
        tracking=True, help="Boquv filialida tortilgan vazn.")
    mashina = fields.Char("Mashina raqami", tracking=True)
    haydovchi_id = fields.Many2one('hr.employee', string="Haydovchi", tracking=True)
    yuk_xati = fields.Char("Yuk xati №", tracking=True)
    manzil = fields.Char("Manzil", tracking=True)
    qabul_qiluvchi_id = fields.Many2one(
        'res.partner', string="Qabul qiluvchi",
        help="So'yish filiali. So'yish moduli ishga tushgach avtomat "
             "to'ldiriladi.")

    # --- qabul (so'yish tomonidan)
    qabul_sana = fields.Date("Qabul sanasi", tracking=True)
    qabul_bosh_soni = fields.Integer("Qabul qilingan bosh soni", tracking=True)
    qabul_vazn = fields.Float(
        "Qabul qilingan vazn (kg)", digits='Product Unit', tracking=True,
        help="So'yish filialida tortilgan vazn. Farq yo'l yo'qotishi.")
    soyish_hujjat = fields.Char(
        "So'yish hujjati", help="So'yish moduli ishga tushgach ulanadi.")

    # --- yo'l yo'qotishi
    yol_yoqotish_kg = fields.Float(
        "Yo'l yo'qotishi (kg)", compute='_compute_yoqotish', store=True,
        digits='Product Unit',
        help="Jo'natilgan − qabul qilingan. Musbat qiymat — yo'lda kamaygan.")
    yol_yoqotish_foiz = fields.Float(
        "Yo'l yo'qotishi (%)", compute='_compute_yoqotish', store=True,
        digits=(12, 2))
    yoqotish_holati = fields.Selection(
        [('norma', "Norma ichida (≤3%)"),
         ('ortiqcha', "Normadan ortiq — tekshiruv akti"),
         ('ortiq_chiqdi', "Qabul vazni ko'p — bino foydasiga")],
        string="Yo'qotish bahosi", compute='_compute_yoqotish', store=True)
    tekshiruv_akti = fields.Char(
        "Tekshiruv akti №", tracking=True,
        help="Yo'qotish normadan oshganda rasmiylashtiriladi.")
    bosh_farqi = fields.Integer(
        "Bosh soni farqi", compute='_compute_yoqotish', store=True,
        help="Jo'natilgan − qabul qilingan bosh soni.")

    # --- narx va natija
    birlik_narx = fields.Monetary(
        "1 kg narxi", tracking=True,
        help="Ichki sotuv narxi. Bosh buxgalter tasdiqlagan narx ro'yxatidan.")
    summa = fields.Monetary("Jami summa", compute='_compute_summa', store=True)
    tannarx_summa = fields.Monetary(
        "Tannarx summasi", readonly=True, copy=False,
        help="Partiyaning yugurib boruvchi tannarxidan. Qo'lda kiritilmaydi.")
    natija = fields.Monetary(
        "Natija (marja)", compute='_compute_summa', store=True,
        help="Summa − tannarx.")

    holat = fields.Selection(
        [('draft', "Qoralama"),
         ('yolda', "Yo'lda"),
         ('done', "Qabul qilingan")],
        string="Holati", default='draft', required=True, tracking=True, copy=False)
    move_id = fields.Many2one(
        'stock.move', string="Ombor harakati", readonly=True, copy=False)
    izoh = fields.Text("Izoh")

    _bosh_musbat = models.Constraint(
        'CHECK (bosh_soni > 0)', "Bosh soni noldan katta bo'lishi kerak.")
    _vazn_musbat = models.Constraint(
        'CHECK (jonatilgan_vazn > 0)',
        "Jo'natilgan vazn noldan katta bo'lishi kerak.")

    # ------------------------------------------------------------- compute
    @api.depends('partiya_id')
    def _compute_company_id(self):
        for j in self:
            j.company_id = j.partiya_id.company_id or self.env.company

    @api.depends('jonatilgan_vazn', 'qabul_vazn', 'bosh_soni', 'qabul_bosh_soni')
    def _compute_yoqotish(self):
        for j in self:
            if not j.qabul_vazn:
                j.yol_yoqotish_kg = 0.0
                j.yol_yoqotish_foiz = 0.0
                j.yoqotish_holati = False
                j.bosh_farqi = 0
                continue
            farq = j.jonatilgan_vazn - j.qabul_vazn
            j.yol_yoqotish_kg = farq
            j.yol_yoqotish_foiz = (farq / j.jonatilgan_vazn * 100.0
                                   if j.jonatilgan_vazn else 0.0)
            j.bosh_farqi = j.bosh_soni - j.qabul_bosh_soni
            if farq < 0:
                # Qabul vazni ko'p chiqdi — bino foydasiga.
                j.yoqotish_holati = 'ortiq_chiqdi'
            elif j.yol_yoqotish_foiz <= YOL_YOQOTISH_NORMA_FOIZ:
                j.yoqotish_holati = 'norma'
            else:
                j.yoqotish_holati = 'ortiqcha'

    @api.depends('qabul_vazn', 'jonatilgan_vazn', 'birlik_narx', 'tannarx_summa')
    def _compute_summa(self):
        for j in self:
            # Hisob-kitob qabul qilingan vazn bo'yicha — so'yish shuni oladi.
            vazn = j.qabul_vazn or j.jonatilgan_vazn
            j.summa = vazn * j.birlik_narx
            j.natija = j.summa - j.tannarx_summa

    # ----------------------------------------------------------- validatsiya
    @api.constrains('bosh_soni', 'partiya_id')
    def _check_bosh_soni(self):
        for j in self:
            if j.holat == 'draft' and j.bosh_soni > j.partiya_id.joriy_son:
                raise ValidationError(_(
                    "«%(nom)s»: jo'natilayotgan bosh soni (%(jonat)s) "
                    "partiyadagi tirik sondan (%(tirik)s) ko'p.",
                    nom=j.display_name, jonat=j.bosh_soni,
                    tirik=j.partiya_id.joriy_son))

    @api.constrains('yoqotish_holati', 'tekshiruv_akti')
    def _check_tekshiruv_akti(self):
        for j in self:
            if j.holat == 'done' and j.yoqotish_holati == 'ortiqcha' \
                    and not j.tekshiruv_akti:
                raise ValidationError(_(
                    "«%(nom)s»: yo'l yo'qotishi %(foiz).2f%% — normadan "
                    "(%(norma)s%%) ortiq. Tekshiruv akti raqamini kiriting.",
                    nom=j.display_name, foiz=j.yol_yoqotish_foiz,
                    norma=YOL_YOQOTISH_NORMA_FOIZ))

    # ------------------------------------------------------------ yaratish
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _("Yangi"):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'agronova.boquv.jonatma') or _("Yangi")
        return super().create(vals_list)

    # --------------------------------------------------------------- holat
    def action_jonatish(self):
        """Qoralama → yo'lda. Bosh soni partiyadan chiqadi."""
        for j in self:
            if j.holat != 'draft':
                raise UserError(_("Faqat qoralama jo'natma yo'lga chiqadi."))
            j.partiya_id._tekshir_ochiq(_("so'yimga jo'natma"))
            if j.tur == 'soyish' and not j.birlik_narx:
                raise UserError(_(
                    "Ichki sotuv narxi ko'rsatilmagan — bo'lim daromadi "
                    "hisoblanmaydi. Avval narxni tasdiqlang («%s»).", j.name))
            j.partiya_id.chiqim_son += j.bosh_soni
            j.holat = 'yolda'
            j.message_post(body=_(
                "Jo'natildi: %(bosh)s bosh, %(vazn)s kg. Mashina %(mashina)s, "
                "yuk xati %(xat)s.",
                bosh=j.bosh_soni, vazn=j.jonatilgan_vazn,
                mashina=j.mashina or '—', xat=j.yuk_xati or '—'))
        return True

    def action_qabul(self):
        """Yo'lda → qabul qilingan. Daromad va tannarx yoziladi."""
        for j in self:
            if j.holat != 'yolda':
                raise UserError(_("Faqat yo'ldagi jo'natma qabul qilinadi."))
            if not j.qabul_vazn:
                raise UserError(_(
                    "Qabul qilingan vazn kiritilmagan — yo'l yo'qotishi "
                    "hisoblanmaydi («%s»).", j.name))
            if not j.qabul_sana:
                j.qabul_sana = fields.Date.context_today(j)
            # Yo'qotish normadan oshgan bo'lsa akt majburiy. Bu tekshiruv
            # `@api.constrains` da emas, aynan shu yerda: constrain faqat
            # o'zgargan maydonlarda ishlaydi va `holat` ni keyin yozganimiz
            # uchun kechikib qoladi.
            if j.yoqotish_holati == 'ortiqcha' and not j.tekshiruv_akti:
                raise UserError(_(
                    "«%(nom)s»: yo'l yo'qotishi %(foiz).2f%% — normadan "
                    "(%(norma)s%%) ortiq. Qabul qilishdan oldin tekshiruv "
                    "akti raqamini kiriting.",
                    nom=j.display_name, foiz=j.yol_yoqotish_foiz,
                    norma=YOL_YOQOTISH_NORMA_FOIZ))

            j._tannarxni_hisoblash()
            j._analitik_yozish()
            j.holat = 'done'

            xabar = _(
                "Qabul qilindi: %(bosh)s bosh, %(vazn)s kg. "
                "Yo'l yo'qotishi %(kg)s kg (%(foiz).2f%%).",
                bosh=j.qabul_bosh_soni, vazn=j.qabul_vazn,
                kg=j.yol_yoqotish_kg, foiz=j.yol_yoqotish_foiz)
            if j.yoqotish_holati == 'ortiqcha':
                xabar += _(" Normadan ortiq — tekshiruv akti: %s.",
                           j.tekshiruv_akti or '—')
            elif j.yoqotish_holati == 'ortiq_chiqdi':
                xabar += _(" Qabul vazni ko'p chiqdi — bino foydasiga.")
            j.message_post(body=xabar)
        return True

    def _tannarxni_hisoblash(self):
        """Jo'natilgan bosh sonining tannarxi.

        Partiyaning `tannarx_1_bosh` maydoni «tirik + chiqib ketgan» bazaga
        bo'lingani uchun bu yerda uni to'g'ridan-to'g'ri ishlatsa bo'ladi:
        jo'natish `chiqim_son` ni oshirsa ham maxraj o'zgarmaydi, ya'ni
        birinchi va oxirgi jo'natma bir xil birlik tannarxni oladi.
        """
        self.ensure_one()
        partiya = self.partiya_id
        partiya.invalidate_recordset(['tannarx_1_bosh'])
        self.tannarx_summa = partiya.tannarx_1_bosh * self.bosh_soni

    def _analitik_yozish(self):
        """Bo'lim daromadi va tannarx chiqimini analitik hisobga yozadi."""
        self.ensure_one()
        partiya = self.partiya_id
        turi = dict(CHIQIM_TURI)[self.tur]
        if self.summa:
            partiya._agronova_post_analytic(
                name=_("%(tur)s: %(bosh)s bosh, %(vazn)s kg",
                       tur=turi, bosh=self.qabul_bosh_soni or self.bosh_soni,
                       vazn=self.qabul_vazn),
                amount=self.summa,
                date=self.qabul_sana,
                unit_amount=self.qabul_vazn,
            )
        if self.tannarx_summa:
            # `tannarxga=False` — sotilgan mahsulotning tannarx chiqimi
            # qolgan podaning birlik tannarxini oshirmasligi kerak.
            partiya._agronova_post_analytic(
                name=_("%s — tannarx chiqimi", turi),
                amount=-abs(self.tannarx_summa),
                date=self.qabul_sana,
                tannarxga=False,
            )

    def action_storno(self):
        for j in self:
            if j.holat != 'done':
                raise UserError(_("Faqat qabul qilingan jo'natma storno qilinadi."))
            partiya = j.partiya_id
            if j.summa:
                partiya._agronova_post_analytic(
                    name=_("STORNO: %s", j.name),
                    amount=-abs(j.summa),
                    date=fields.Date.context_today(j),
                    tannarxga=False,
                )
            if j.tannarx_summa:
                partiya._agronova_post_analytic(
                    name=_("STORNO tannarx: %s", j.name),
                    amount=abs(j.tannarx_summa),
                    date=fields.Date.context_today(j),
                    tannarxga=False,
                )
            partiya.chiqim_son -= j.bosh_soni
            j.holat = 'draft'
            j.message_post(body=_("Jo'natma storno qilindi."))
        return True

    def write(self, vals):
        # Qabul ma'lumotlari «yo'lda» holatida kiritiladi — ular qulflanmaydi.
        qabul_maydonlari = {
            'qabul_sana', 'qabul_bosh_soni', 'qabul_vazn', 'soyish_hujjat',
            'tekshiruv_akti', 'holat', 'move_id', 'tannarx_summa',
            'message_follower_ids', 'message_ids', 'izoh',
        }
        if set(vals) - qabul_maydonlari:
            for j in self:
                if j.holat == 'done':
                    raise UserError(_(
                        "«%s» jo'natmasi qabul qilingan — tahrirlanmaydi. "
                        "Storno qiling.", j.display_name))
        return super().write(vals)

    def unlink(self):
        if any(j.holat != 'draft' for j in self):
            raise UserError(_("Faqat qoralama jo'natma o'chiriladi."))
        return super().unlink()
