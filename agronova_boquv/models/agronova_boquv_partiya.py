# -*- coding: utf-8 -*-
"""Boquv partiyasi — modulning yadrosi.

Bir binoda bir vaqtda boqiladigan va bir vaqtda yakunlanadigan jo'jalar
guruhi (o'rtacha 45 kun). Barcha xarajat shu partiyaning analitik hisobiga
yig'iladi, tannarx faqat shundan hisoblanadi.

**Ikkita sana** (yakuniy TZ, «Partiya hayot sikli»):

* `ochilish_sana` — partiya ochildi, **xarajat boshlanadi** (dizinfeksiya,
  tayyorgarlik);
* `joja_sana` — jo'ja keldi, **yosh kunlari shundan sanaladi**.

Ikkisi orasidagi kutish normasi **15 kun**. Ortiqcha kun partiyaga emas,
«bo'sh turish zarari» hisobiga o'tadi — aks holda sekin tashkil qilingan
partiya tannarxi asossiz oshib ketadi.

**Ona Tovuqdan farqi:** tannarx partiya yopilganda emas, **har kuni**
hisoblanadi (TZ 15-band: «Ushbu ko'rsatkich har kuni yangilanadi»).
Yopilganda esa qotadi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# Partiya ochilgandan jo'ja kelgunicha kutish normasi (kun).
# Yakuniy TZ: «Kutish normasi 15 kun; ortiqcha kun partiyaga emas →
# bo'sh turish zarari hisobiga».
KUTISH_NORMASI_KUN = 15


class AgroNovaBoquvPartiya(models.Model):
    _name = 'agronova.boquv.partiya'
    _description = "Boquv partiyasi"
    _inherit = ['agronova.analitik.mixin', 'agronova.tannarx.qulf.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'ochilish_sana desc, id desc'

    # Tannarx maydonlarini DB darajasida readonly qilish (TZ 3-bo'lim)
    _agronova_tannarx_fields = ('tannarx_1_bosh', 'tannarx_1_kg')

    # Bazada «Boquv partiyasi» rejasi allaqachon yaratilgan (id=4).
    _agronova_analytic_plan_name = "Boquv partiyasi"

    _rec_names_search = ['name', 'bino_id.name', 'filial_id.name']

    name = fields.Char(
        "Partiya raqami", default=lambda self: _("Yangi"),
        copy=False, readonly=True, index=True)
    filial_id = fields.Many2one(
        'agronova.boquv.filial', string="Filial", required=True, tracking=True,
        ondelete='restrict', index=True)
    bino_id = fields.Many2one(
        'agronova.boquv.bino', string="Bino (seh)", required=True, tracking=True,
        ondelete='restrict', index=True,
        domain="[('filial_id', '=', filial_id)]")
    brigadir_id = fields.Many2one(
        'hr.employee', string="Mas'ul brigader", tracking=True,
        help="TZ 3-band. Bo'sh qoldirilsa binoning brigaderi olinadi.")
    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True, readonly=True,
        store=True, precompute=True, compute='_compute_company_id')
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)

    # ------------------------------------------------------------ sanalar
    ochilish_sana = fields.Date(
        "Partiya ochilgan sana", required=True, tracking=True,
        default=fields.Date.context_today,
        help="Xarajat shu sanadan boshlab yig'iladi (dizinfeksiya, tayyorgarlik).")
    joja_sana = fields.Date(
        "Jo'ja kelgan sana", tracking=True,
        help="Yosh kunlari shu sanadan sanaladi. Jo'ja kirimi tasdiqlanganda "
             "avtomat to'ldiriladi.")
    reja_kun = fields.Integer(
        "Rejalashtirilgan muddat (kun)", default=45, tracking=True,
        help="TZ 3-band: standart 45 kun.")
    yopilish_sana = fields.Date("Yopilgan sana", readonly=True, copy=False)
    yosh_kun = fields.Integer(
        "Yoshi (kun)", compute='_compute_yosh', store=True,
        help="Jo'ja kelgan sanadan bugungacha. Jo'ja kelmagan bo'lsa 0.")
    kutish_kun = fields.Integer(
        "Kutish (kun)", compute='_compute_yosh', store=True,
        help="Partiya ochilgandan jo'ja kelgunicha o'tgan kunlar.")
    ortiqcha_kutish_kun = fields.Integer(
        "Ortiqcha kutish (kun)", compute='_compute_yosh', store=True,
        help="Normadan (15 kun) ortiq kutilgan kunlar. Bu kunlarning "
             "doimiy xarajati partiyaga emas, «bo'sh turish zarari» "
             "hisobiga yoziladi.")

    # ------------------------------------------------------- bosh soni
    boshlangich_son = fields.Integer(
        "Boshlang'ich bosh soni", tracking=True,
        help="Jo'ja kirimi tasdiqlanganda avtomat to'ldiriladi.")
    boshlangich_vazn = fields.Float(
        "Boshlang'ich o'rtacha vazn (kg)", digits='Product Unit', tracking=True,
        help="TZ 3-band: «agar mavjud bo'lsa».")
    nobud_son = fields.Integer(
        "Nobud bo'lgan", compute='_compute_son', store=True,
        help="Kunlik jurnaldan yig'iladi.")
    chiqim_son = fields.Integer(
        "Chiqib ketgan", default=0, readonly=True, copy=False,
        help="So'yishga jo'natilgan, ehson qilingan, qo'lda so'yilgan yoki "
             "boshqa binoga o'tkazilgan bosh soni.")
    joriy_son = fields.Integer(
        "Tirik bosh soni", compute='_compute_son', store=True, tracking=True,
        help="Boshlang'ich − nobud − chiqim (TZ 12-band).")
    nobud_foiz = fields.Float(
        "Nobudgarchilik (%)", compute='_compute_son', store=True, digits=(12, 2),
        help="Nobud / boshlang'ich × 100 (TZ 12-band).")
    yashovchanlik = fields.Float(
        "Yashovchanlik (%)", compute='_compute_son', store=True, digits=(12, 2))

    # ------------------------------------------------------------ vazn
    ortacha_vazn = fields.Float(
        "O'rtacha vazn (kg)", compute='_compute_vazn', store=True,
        digits='Product Unit',
        help="Oxirgi tortishdan olinadi (TZ 13-band).")
    jami_tirik_vazn = fields.Float(
        "Jami tirik vazn (kg)", compute='_compute_vazn', store=True,
        digits='Product Unit',
        help="Tirik bosh soni × o'rtacha vazn (TZ 13-band).")
    kunlik_osish_gr = fields.Float(
        "O'rtacha kunlik o'sish (gr)", compute='_compute_vazn', store=True,
        digits=(12, 2))

    # --------------------------------------------------- yem va samaradorlik
    yem_sarf_kg = fields.Float(
        "Jami yem sarfi (kg)", compute='_compute_yem', store=True,
        digits='Product Unit',
        help="Kunlik jurnaldagi yem qatorlaridan kg da yig'iladi. "
             "FCR shundan hisoblanadi.")
    fcr = fields.Float(
        "FCR (yem konversiyasi)", compute='_compute_samaradorlik', store=True,
        digits=(12, 3),
        help="Yem sarfi (kg) / jami tirik vazn (kg). 1 kg tirik vazn olish "
             "uchun sarflangan yem.")
    epef = fields.Float(
        "EPEF (samaradorlik indeksi)", compute='_compute_samaradorlik',
        store=True, digits=(12, 1),
        help="(yashovchanlik % × o'rtacha vazn kg) / (yosh kun × FCR) × 100. "
             "Broyler boqishning umumiy samaradorlik ko'rsatkichi.")

    # --- reja-fakt (normativ kiritilgan bo'lsa)
    fcr_norma = fields.Float(
        "FCR normasi", compute='_compute_norma', digits=(12, 3))
    fcr_ogish = fields.Float(
        "FCR og'ishi", compute='_compute_norma', digits=(12, 3),
        help="Fakt − norma. Musbat qiymat — yem normadan ko'p sarflangan.")
    nobud_norma = fields.Float(
        "Nobudgarchilik normasi (%)", compute='_compute_norma', digits=(12, 2))
    nobud_ogish = fields.Float(
        "Nobudgarchilik og'ishi (p.p.)", compute='_compute_norma', digits=(12, 2))
    ogish_bormi = fields.Boolean(
        "Normadan og'ish bor", compute='_compute_norma', store=True,
        help="Normativ kiritilgan va fakt undan yomon bo'lsa belgilanadi. "
             "Saqlanadi — «og'ish bor» filtri shu maydon bo'yicha ishlaydi.")

    # ------------------------------------------------------------- moliya
    jami_xarajat = fields.Monetary("Jami xarajat", compute='_compute_moliya')
    jami_daromad = fields.Monetary("Jami daromad", compute='_compute_moliya')
    foyda = fields.Monetary("Foyda / zarar", compute='_compute_moliya')
    rentabellik = fields.Float(
        "Rentabellik (%)", compute='_compute_moliya', digits=(12, 2))

    # TZ: tannarx maydoni BARCHA rollar uchun readonly — qo'lda kiritilmaydi.
    tannarx_1_bosh = fields.Monetary(
        "1 bosh tannarxi", compute='_compute_tannarx', store=True, readonly=True,
        help="Jami xarajat / tirik bosh soni. Har kuni yangilanadi (TZ 15-band).")
    tannarx_1_kg = fields.Monetary(
        "1 kg tirik vazn tannarxi", compute='_compute_tannarx', store=True,
        readonly=True,
        help="Jami xarajat / jami tirik vazn. Har kuni yangilanadi (TZ 16-band).")
    tannarx_qotgan = fields.Boolean(
        "Tannarx qotgan", default=False, readonly=True, copy=False,
        help="Partiya yopilganda belgilanadi — undan keyin tannarx "
             "qayta hisoblanmaydi.")

    # ------------------------------------------------------------- holat
    holat = fields.Selection(
        [('draft', "Qoralama"),
         ('kutilmoqda', "Jo'ja kutilmoqda"),
         ('active', "Faol"),
         ('closed', "Yopilgan"),
         ('cancel', "Bekor qilingan")],
        string="Holati", default='draft', required=True, tracking=True, copy=False)

    # --------------------------------------------------------- bog'liq yozuvlar
    jurnal_ids = fields.One2many(
        'agronova.boquv.jurnal', 'partiya_id', string="Kunlik jurnal")
    jurnal_count = fields.Integer("Jurnal kunlari", compute='_compute_counts')
    obxod_ids = fields.One2many(
        'agronova.boquv.obxod', 'partiya_id', string="Obxodlar")
    obxod_bugun_soni = fields.Integer(
        "Bugungi obxodlar", compute='_compute_obxod_bugun',
        help="TZ 10-band: kuniga kamida 3 marta obxod talab qilinadi.")
    vazn_ids = fields.One2many(
        'agronova.boquv.vazn', 'partiya_id', string="Vazn nazorati")
    kirim_ids = fields.One2many(
        'agronova.boquv.joja.kirim', 'partiya_id', string="Jo'ja kirimlari")
    jonatma_ids = fields.One2many(
        'agronova.boquv.jonatma', 'partiya_id', string="So'yimga jo'natmalar")

    izoh = fields.Text("Izoh")

    _boshlangich_musbat = models.Constraint(
        'CHECK (boshlangich_son >= 0)',
        "Boshlang'ich bosh soni manfiy bo'lmasin.")
    _reja_kun_musbat = models.Constraint(
        'CHECK (reja_kun > 0)', "Rejalashtirilgan muddat noldan katta bo'lsin.")

    # =====================================================  COMPUTE
    @api.depends('bino_id')
    def _compute_company_id(self):
        for p in self:
            p.company_id = p.bino_id.company_id or self.env.company

    @api.depends('name', 'bino_id')
    def _compute_display_name(self):
        for p in self:
            p.display_name = ("%s · %s" % (p.name, p.bino_id.display_name)
                              if p.bino_id else p.name)

    @api.depends('ochilish_sana', 'joja_sana', 'yopilish_sana')
    def _compute_yosh(self):
        bugun = fields.Date.context_today(self)
        for p in self:
            oxir = p.yopilish_sana or bugun
            if p.joja_sana:
                p.yosh_kun = max((oxir - p.joja_sana).days, 0)
                p.kutish_kun = max((p.joja_sana - p.ochilish_sana).days, 0) \
                    if p.ochilish_sana else 0
            else:
                p.yosh_kun = 0
                p.kutish_kun = max((oxir - p.ochilish_sana).days, 0) \
                    if p.ochilish_sana else 0
            p.ortiqcha_kutish_kun = max(p.kutish_kun - KUTISH_NORMASI_KUN, 0)

    @api.depends('boshlangich_son', 'chiqim_son', 'jurnal_ids.nobud_son',
                 'jurnal_ids.holat')
    def _compute_son(self):
        for p in self:
            tasdiqlangan = p.jurnal_ids.filtered(lambda j: j.holat == 'posted')
            p.nobud_son = sum(tasdiqlangan.mapped('nobud_son'))
            p.joriy_son = p.boshlangich_son - p.nobud_son - p.chiqim_son
            if p.boshlangich_son:
                p.nobud_foiz = p.nobud_son / p.boshlangich_son * 100.0
                p.yashovchanlik = 100.0 - p.nobud_foiz
            else:
                p.nobud_foiz = 0.0
                p.yashovchanlik = 0.0

    @api.depends('vazn_ids.sana', 'vazn_ids.ortacha_vazn', 'joriy_son',
                 'boshlangich_vazn', 'yosh_kun')
    def _compute_vazn(self):
        for p in self:
            # Oxirgi tortish natijasi — o'rtacha vazn shundan olinadi.
            oxirgi = p.vazn_ids.sorted('sana', reverse=True)[:1]
            p.ortacha_vazn = oxirgi.ortacha_vazn if oxirgi else 0.0
            p.jami_tirik_vazn = p.joriy_son * p.ortacha_vazn
            if p.yosh_kun and p.ortacha_vazn:
                osish = p.ortacha_vazn - (p.boshlangich_vazn or 0.0)
                p.kunlik_osish_gr = osish * 1000.0 / p.yosh_kun
            else:
                p.kunlik_osish_gr = 0.0

    @api.depends('jurnal_ids.yem_kg', 'jurnal_ids.holat')
    def _compute_yem(self):
        for p in self:
            tasdiqlangan = p.jurnal_ids.filtered(lambda j: j.holat == 'posted')
            p.yem_sarf_kg = sum(tasdiqlangan.mapped('yem_kg'))

    @api.depends('yem_sarf_kg', 'jami_tirik_vazn', 'joriy_son', 'chiqim_son',
                 'yashovchanlik', 'ortacha_vazn', 'yosh_kun')
    def _compute_samaradorlik(self):
        for p in self:
            # FCR = sarflangan yem (kg) / jami yetishtirilgan tirik vazn (kg)
            # Baza: joriy tirik jo'jalar + chiqib ketgan boshlar vazni
            baza_vazn = (p.joriy_son + p.chiqim_son) * p.ortacha_vazn
            p.fcr = (p.yem_sarf_kg / baza_vazn
                     if baza_vazn else 0.0)
            # EPEF = (yashovchanlik % × o'rtacha vazn kg) / (yosh kun × FCR) × 100
            if p.yosh_kun and p.fcr:
                p.epef = (p.yashovchanlik * p.ortacha_vazn) / (p.yosh_kun * p.fcr) * 100.0
            else:
                p.epef = 0.0

    @api.depends('fcr', 'nobud_foiz', 'yosh_kun')
    def _compute_norma(self):
        """Reja-fakt taqqoslash.

        `ogish_bormi` saqlanadi (search filtri uchun), lekin bog'liqlik
        ro'yxatida normativ jadvali yo'q — Odoo boshqa modeldagi qatorlar
        o'zgarishini kuzata olmaydi. Normativ qiymatlari o'zgarganda
        `agronova.boquv.normativ` o'zi partiyalarni qayta hisoblashga
        majburlaydi (`_qayta_hisoblash`).
        """
        Normativ = self.env['agronova.boquv.normativ']
        for p in self:
            fcr_norma = Normativ.qiymat('fcr_norma', yosh_kun=p.yosh_kun)
            nobud_norma = Normativ.qiymat('nobud_foiz_norma', yosh_kun=p.yosh_kun)
            p.fcr_norma = fcr_norma
            p.nobud_norma = nobud_norma
            # Normativ kiritilmagan bo'lsa (0.0) — taqqoslash o'tkazilmaydi.
            p.fcr_ogish = (p.fcr - fcr_norma) if (fcr_norma and p.fcr) else 0.0
            p.nobud_ogish = (p.nobud_foiz - nobud_norma) if nobud_norma else 0.0
            p.ogish_bormi = bool(
                (fcr_norma and p.fcr and p.fcr > fcr_norma)
                or (nobud_norma and p.nobud_foiz > nobud_norma))

    def _compute_moliya(self):
        for p in self:
            xarajat = p._agronova_analytic_amount(sign='cost')
            daromad = p._agronova_analytic_amount(sign='income')
            p.jami_xarajat = xarajat
            p.jami_daromad = daromad
            p.foyda = daromad - xarajat
            p.rentabellik = (p.foyda / daromad * 100.0) if daromad else 0.0

    @api.depends('joriy_son', 'chiqim_son', 'jami_tirik_vazn', 'ortacha_vazn',
                 'holat', 'tannarx_qotgan',
                 'jurnal_ids.holat', 'kirim_ids.holat')
    def _compute_tannarx(self):
        """Kunlik tannarx (TZ 15, 16-band).

        Ona Tovuqdan farqi: bu yerda tannarx har safar qayta hisoblanadi,
        yopilganda esa `tannarx_qotgan` bayrog'i qo'yiladi va qiymat
        o'zgarmaydi.

        **Baza — tirik + chiqib ketgan bosh soni.** TZ 15-band «shu kundagi
        tirik jo'jalar soni» deydi va boqish davomida bu to'g'ri: hali hech
        kim ketmagan. Lekin so'yishga jo'natish boshlangach `joriy_son`
        kamayaveradi, xarajat esa joyida qoladi — natijada oxirgi qolgan
        bir necha boshga butun partiya xarajati tushib, tannarx yuz barobar
        oshib ketadi.

        Shuning uchun maxraj `joriy_son + chiqim_son`: xarajat aynan shu
        boshlarning hammasiga sarflangan. Jo'natish boshlanmaguncha
        `chiqim_son = 0` va formula TZ dagidek ishlaydi.
        """
        for p in self:
            if p.tannarx_qotgan:
                p._tannarx_yozish().tannarx_1_bosh = p.tannarx_1_bosh or 0.0
                p._tannarx_yozish().tannarx_1_kg = p.tannarx_1_kg or 0.0
                continue
            xarajat = p._agronova_analytic_amount(sign='cost', faqat_tannarx=True)
            # Xarajat sarflangan boshlar: podada turganlar + chiqib ketganlar.
            baza_son = p.joriy_son + p.chiqim_son
            p._tannarx_yozish().tannarx_1_bosh = xarajat / baza_son if baza_son else 0.0
            # 1 kg tannarxi ham shu bazaning vazniga bo'linadi.
            baza_vazn = baza_son * p.ortacha_vazn
            p._tannarx_yozish().tannarx_1_kg = xarajat / baza_vazn if baza_vazn else 0.0

    @api.depends('jurnal_ids')
    @api.depends('jurnal_ids')
    def _compute_counts(self):
        for p in self:
            p.jurnal_count = len(p.jurnal_ids)

    @api.depends('obxod_ids.vaqt')
    def _compute_obxod_bugun(self):
        """Bugungi obxodlar soni.

        `depends` SHART: usiz Odoo qiymatni bir marta hisoblab keshda
        saqlaydi va shu tranzaksiya davomida qayta hisoblamaydi. Brigadir
        paneli obxodni yozib, darhol o'sha so'rov ichida sonni qaytaradi —
        depends bo'lmaganda kassir «3/3» o'rniga «0/3» ni ko'rardi.

        Sana ham foydalanuvchi vaqt mintaqasida olinadi: UTC bo'yicha
        hisoblansa Toshkentda kechqurun soat 19:00 dan keyingi obxod
        ertangi kunga tushib ketardi va «kuniga 3 marta» normasi
        buzilgandek ko'rinardi.
        """
        bugun = fields.Date.context_today(self)
        for p in self:
            p.obxod_bugun_soni = len(p.obxod_ids.filtered(
                lambda o: o.vaqt and fields.Datetime.context_timestamp(
                    o, o.vaqt).date() == bugun))

    # =====================================================  VALIDATSIYA
    @api.constrains('filial_id', 'bino_id')
    def _check_bino_filial(self):
        for p in self:
            if p.bino_id and p.bino_id.filial_id != p.filial_id:
                raise ValidationError(_(
                    "«%(bino)s» binosi «%(bfilial)s» filialiga tegishli, "
                    "partiyada esa «%(pfilial)s» ko'rsatilgan.",
                    bino=p.bino_id.display_name,
                    bfilial=p.bino_id.filial_id.name,
                    pfilial=p.filial_id.name))

    @api.constrains('joja_sana', 'ochilish_sana')
    def _check_sanalar(self):
        for p in self:
            if p.joja_sana and p.ochilish_sana and p.joja_sana < p.ochilish_sana:
                raise ValidationError(_(
                    "Jo'ja kelgan sana partiya ochilgan sanadan oldin "
                    "bo'lmaydi («%s»).", p.name))

    @api.onchange('bino_id')
    def _onchange_bino(self):
        """Bino tanlanganda filial va brigaderni to'ldiradi."""
        if self.bino_id:
            self.filial_id = self.bino_id.filial_id
            if not self.brigadir_id:
                self.brigadir_id = self.bino_id.brigadir_id

    # =====================================================  YARATISH
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _("Yangi"):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'agronova.boquv.partiya') or _("Yangi")
        return super().create(vals_list)

    # =====================================================  QULF
    def _tekshir_ochiq(self, amal=None):
        """Yopilgan yoki bekor qilingan partiyaga yozuv qo'shishni taqiqlaydi.

        Yakuniy TZ: «Yopilgach tuzatish partiyaga emas, joriy davr hisobiga.
        Yopilgan partiyaga yozuv qo'shish taqiq.»
        """
        for p in self:
            if p.holat in ('closed', 'cancel'):
                raise UserError(_(
                    "«%(nom)s» partiyasi %(holat)s — unga yangi yozuv "
                    "qo'shilmaydi. Tuzatish joriy davr hisobiga "
                    "o'tkaziladi.%(amal)s",
                    nom=p.name,
                    holat=dict(self._fields['holat'].selection).get(p.holat, ''),
                    amal=(_(" (%s)", amal) if amal else "")))
        return True

    def _agronova_post_analytic(self, *args, **kwargs):
        self._tekshir_ochiq()
        return super()._agronova_post_analytic(*args, **kwargs)

    # =====================================================  HOLATLAR
    def action_ochish(self):
        """Qoralama → jo'ja kutilmoqda. Xarajat yig'ish shu paytdan boshlanadi."""
        for p in self:
            if p.holat != 'draft':
                raise UserError(_("Faqat qoralama partiya ochiladi."))
            if p.bino_id.holat == 'no_aktiv':
                raise UserError(_(
                    "«%s» binosi «No aktiv» holatida — unda partiya "
                    "ochilmaydi. Avval dizinfeksiyaga o'tkazing.",
                    p.bino_id.display_name))
            p.holat = 'kutilmoqda'
            p.message_post(body=_(
                "Partiya ochildi. Xarajat yig'ish boshlandi. "
                "Jo'ja kutilmoqda (norma %s kun).", KUTISH_NORMASI_KUN))
            # Binoda biriktirilmagan dezinfeksiya bo'lsa — xarajatini
            # o'zimizga tortamiz (TZ 8-band).
            dez = self.env['agronova.boquv.dezinfeksiya']._biriktirilmaganlar(
                p.bino_id)
            if dez:
                dez.action_partiyaga_biriktirish(partiya=p)
        return True

    def action_faollashtirish(self):
        """Jo'ja keldi → faol. Odatda jo'ja kirimi tasdiqlanganda avtomat."""
        for p in self:
            if p.holat not in ('draft', 'kutilmoqda'):
                raise UserError(_("Faqat ochilgan partiya faollashtiriladi."))
            if not p.boshlangich_son:
                raise UserError(_(
                    "«%s» partiyasida boshlang'ich bosh soni yo'q. "
                    "Avval jo'ja kirimini tasdiqlang.", p.name))
            if not p.joja_sana:
                p.joja_sana = fields.Date.context_today(p)
            p.holat = 'active'
            p.bino_id.holat = 'aktiv'
            if p.ortiqcha_kutish_kun:
                p._bosh_turish_zarari()
        return True

    def _bosh_turish_zarari(self):
        """Ortiqcha kutish kunlarining xarajatini partiyadan chiqaradi.

        Yakuniy TZ: «Kutish normasi 15 kun; ortiqcha kun partiyaga emas →
        bo'sh turish zarari hisobiga».

        Sabab: sekin tashkil qilingan partiya aybdor emas — jo'ja kechikkani
        uchun uning tannarxi oshib ketmasligi kerak. Shu kunlarga to'g'ri
        keladigan xarajat partiyadan olib tashlanadi va **binoning** hisobiga
        yoziladi: u yerda «bo'sh turish» sifatida ko'rinadi va davr zarariga
        kiradi.

        Hisob: partiya ochilgandan jo'ja kelgunicha yig'ilgan xarajatning
        ortiqcha kunlarga to'g'ri keladigan ulushi.
        """
        self.ensure_one()
        if not self.ortiqcha_kutish_kun or not self.kutish_kun:
            return False
        # Kutish davrida yig'ilgan xarajat: dezinfeksiya, doimiy xarajatlar.
        #
        # **Jo'ja qiymati bu hisobga kirmaydi.** U aynan jo'ja kelgan kuni
        # yoziladi, ya'ni sana bo'yicha kutish davriga tushadi — lekin bu
        # bo'sh turish xarajati emas, balki podaning o'zi. Uni qo'shsak
        # zarar bir necha o'n barobar oshib ketardi.
        Line = self.env['account.analytic.line'].sudo()
        plan = self.analytic_account_id.plan_id
        joja_line_ids = self.kirim_ids.mapped('analytic_line_ids').ids \
            if 'analytic_line_ids' in self.kirim_ids._fields else []
        domain = [
            (plan._column_name(), '=', self.analytic_account_id.id),
            ('date', '>=', self.ochilish_sana),
            ('date', '<=', self.joja_sana),
            ('amount', '<', 0.0),
            ('agronova_tannarx_bazasi', '=', True),
        ]
        if joja_line_ids:
            domain.append(('id', 'not in', joja_line_ids))
        else:
            # Kirim qatorlari alohida saqlanmaydi — nomi bo'yicha ajratamiz.
            domain.append(('name', 'not ilike', "Jo'ja kirimi"))
        kutish_xarajat = -sum(Line.search(domain).mapped('amount'))
        if not kutish_xarajat:
            self.message_post(body=_(
                "Jo'ja %(kun)s kun kutildi (norma %(norma)s). Kutish davrida "
                "xarajat yozilmagan — bo'sh turish zarari nolga teng.",
                kun=self.kutish_kun, norma=KUTISH_NORMASI_KUN))
            return False

        ulush = kutish_xarajat * self.ortiqcha_kutish_kun / self.kutish_kun
        ulush = self.currency_id.round(ulush)
        if not ulush:
            return False

        # Partiyada teskari qator — tannarxdan chiqadi.
        self._agronova_post_analytic(
            name=_("Bo'sh turish zarari: %s kun normadan ortiq",
                   self.ortiqcha_kutish_kun),
            amount=abs(ulush),
            date=self.joja_sana or fields.Date.context_today(self),
            tannarxga=False,
        )
        # Binoda xarajat sifatida qoladi — davr zarari.
        self.bino_id._agronova_post_analytic(
            name=_("Bo'sh turish zarari (%(partiya)s, %(kun)s kun)",
                   partiya=self.name, kun=self.ortiqcha_kutish_kun),
            amount=-abs(ulush),
            date=self.joja_sana or fields.Date.context_today(self),
            tannarxga=False,
        )
        self.message_post(body=_(
            "Jo'ja %(kun)s kun kutildi, norma %(norma)s kun. Ortiqcha "
            "%(ortiq)s kunning xarajati (%(summa)s) partiya tannarxidan "
            "chiqarilib, «bo'sh turish zarari» sifatida binoga yozildi.",
            kun=self.kutish_kun, norma=KUTISH_NORMASI_KUN,
            ortiq=self.ortiqcha_kutish_kun, summa=ulush))
        return True

    def action_close(self):
        """Partiyani yopadi va tannarxni qotiradi."""
        for p in self:
            if p.holat != 'active':
                raise UserError(_("Faqat faol partiya yopiladi."))
            if p.joriy_son > 0:
                raise UserError(_(
                    "«%(nom)s» partiyasida %(son)s bosh tirik qolgan — "
                    "yopib bo'lmaydi. Avval so'yishga topshiring yoki "
                    "chiqimni rasmiylashtiring.",
                    nom=p.name, son=p.joriy_son))
            p.yopilish_sana = fields.Date.context_today(p)
            p.holat = 'closed'
            p.tannarx_qotgan = True
            p.message_post(body=_(
                "Partiya yopildi. Tannarx qotdi: 1 bosh %(bosh)s, "
                "1 kg tirik vazn %(kg)s. FCR %(fcr).3f, nobudgarchilik %(nob).2f%%.",
                bosh=p.tannarx_1_bosh, kg=p.tannarx_1_kg,
                fcr=p.fcr, nob=p.nobud_foiz))
            # Binoda boshqa faol partiya qolmagan bo'lsa — bo'shatamiz.
            if not p.bino_id.partiya_ids.filtered(
                    lambda x: x.holat == 'active' and x.id != p.id):
                p.bino_id.holat = 'no_aktiv'
        return True

    def action_bekor(self):
        """Partiyani bekor qiladi — xarajat davr zarariga o'tadi."""
        for p in self:
            if p.holat == 'closed':
                raise UserError(_("Yopilgan partiya bekor qilinmaydi."))
            p.holat = 'cancel'
            p.tannarx_qotgan = True
            p.message_post(body=_(
                "Partiya bekor qilindi. Yig'ilgan xarajat (%s) davr "
                "zarariga o'tadi.", p.jami_xarajat))
        return True

    def action_draftga(self):
        for p in self:
            if p.holat != 'kutilmoqda':
                raise UserError(_(
                    "Faqat «Jo'ja kutilmoqda» holatidagi partiya qoralamaga "
                    "qaytariladi."))
            if p.jami_xarajat:
                raise UserError(_(
                    "«%s» partiyasiga xarajat yozilgan — qoralamaga "
                    "qaytarilmaydi. Bekor qiling.", p.name))
            p.holat = 'draft'
        return True

    # =====================================================  WRITE / UNLINK
    def write(self, vals):
        qulf_tashqari = {
            'holat', 'chiqim_son', 'tannarx_qotgan', 'yopilish_sana',
            'message_follower_ids', 'message_ids', 'activity_ids',
        }
        if set(vals) - qulf_tashqari:
            for p in self:
                if p.holat in ('closed', 'cancel'):
                    raise UserError(_(
                        "«%s» partiyasi yopilgan yoki bekor qilingan — "
                        "tannarx qotgan, tahrirlash taqiqlanadi.", p.name))
        return super().write(vals)

    def unlink(self):
        if any(p.holat != 'draft' for p in self):
            raise UserError(_("Faqat qoralama partiya o'chiriladi."))
        return super().unlink()

    # =====================================================  HISOBOT
    def xarajat_tarkibi(self):
        """Xarajatni hisobot guruhlari bo'yicha yig'adi (A ilova).

        Qaytaradi: `[{'kod', 'nom', 'summa', 'ulush'}, ...]` — kamayish
        tartibida saralangan, `ulush` foizda.

        Guruhlash manbai — analitik qatorning xarajat kategoriyasi. Kategoriya
        aniqlanmagan qatorlar (ombordan sarf, ish haqi, jo'ja kirimi) qator
        nomidagi kalit so'z bo'yicha ajratiladi: bu qatorlarni yozgan kod
        nomni o'zi belgilaydi, shuning uchun ishonchli.
        """
        self.ensure_one()
        from .agronova_xarajat_kategoriya import HISOBOT_GURUHI
        nomlar = dict(HISOBOT_GURUHI)

        if not self.analytic_account_id:
            return []
        plan = self.analytic_account_id.plan_id
        lines = self.env['account.analytic.line'].sudo().search([
            (plan._column_name(), '=', self.analytic_account_id.id),
            ('amount', '<', 0.0),
            ('agronova_tannarx_bazasi', '=', True),
        ])

        yigindi = {}
        for line in lines:
            yigindi.setdefault(self._satr_guruhi(line), 0.0)
            yigindi[self._satr_guruhi(line)] += abs(line.amount)

        jami = sum(yigindi.values())
        natija = [{
            'kod': kod,
            'nom': nomlar.get(kod, kod),
            'summa': summa,
            'ulush': (summa / jami * 100.0) if jami else 0.0,
        } for kod, summa in yigindi.items() if summa]
        return sorted(natija, key=lambda r: r['summa'], reverse=True)

    @api.model
    def _satr_guruhi(self, line):
        """Analitik qator qaysi hisobot guruhiga tegishli."""
        # 1) Xarajat hujjati orqali kelgan bo'lsa — kategoriyadan.
        xarajat = self.env['agronova.boquv.xarajat'].sudo().search(
            [('analytic_line_ids', 'in', line.id)], limit=1)
        if xarajat and xarajat.kategoriya_id.boquv_hisobot_guruhi:
            return xarajat.kategoriya_id.boquv_hisobot_guruhi

        # 2) Aks holda qator nomidagi kalit so'z bo'yicha. Bu nomlarni
        #    shu modulning o'zi yozadi, shuning uchun barqaror.
        nom = (line.name or '').lower()
        kalitlar = [
            ("jo'ja kirimi", 'joja'),
            ("yem", 'yem'),
            ("dori", 'veterinariya'),
            ("vaksina", 'veterinariya'),
            ("dezinfeksiya", 'dezinfeksiya'),
            ("ish haqi", 'ish_haqi'),
            ("so'yish", 'soyish'),
            ("ijara", 'ijara'),
            ("amortizatsiya", 'amortizatsiya'),
            ("elektr", 'kommunal'),
            ("gaz", 'kommunal'),
            ("suv", 'kommunal'),
            ("kommunal", 'kommunal'),
        ]
        for kalit, guruh in kalitlar:
            if kalit in nom:
                return guruh
        return 'boshqa'

    # =====================================================  ACTIONS
    def action_open_jurnal(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("«%s» kunlik jurnali", self.name),
            'res_model': 'agronova.boquv.jurnal',
            'view_mode': 'list,form',
            'domain': [('partiya_id', '=', self.id)],
            'context': {'default_partiya_id': self.id},
        }

    def action_open_obxod(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("«%s» obxodlari", self.name),
            'res_model': 'agronova.boquv.obxod',
            'view_mode': 'list,form',
            'domain': [('partiya_id', '=', self.id)],
            'context': {'default_partiya_id': self.id},
        }
