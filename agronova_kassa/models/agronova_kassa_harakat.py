# -*- coding: utf-8 -*-
import logging
import uuid
from urllib.parse import quote

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .utils import uz_day

_logger = logging.getLogger(__name__)

# Manba hujjatdan ko'chirilgan yozuvlar — bularga qayta provodka
# YOZILMAYDI, chunki manbada allaqachon yozilgan.
AUTO_MANBA = ('sotuv', 'xarid', 'oylik', 'otkazma', 'inkassatsiya', 'boshqa')

# Kassir orqaga sana bilan necha kun yoza oladi (ir.config_parameter).
ORQAGA_KUN_PARAM = 'agronova_kassa.orqaga_kun'


class AgroNovaKassaHarakat(models.Model):
    """Kassa harakati — naqd pulning har bir kirimi va chiqimi.

    Ikki yo'l bilan paydo bo'ladi:

      1. **Qo'lda** — kassir panelda yoki formada kiritadi. Moddaga qarab
         provodka ham shu yerda yoziladi.
      2. **Avtomatik** — manba hujjatdan ko'chiriladi: naqd jurnal orqali
         qilingan to'lov (`account.payment`), kassalararo transfer va
         inkassatsiya. Provodka manbada yozilgani uchun takrorlanmaydi.

    Tasdiqlangan yozuv **o'chirilmaydi va tahrirlanmaydi** — faqat storno
    qilinadi (TZ M04). Storno qilinganda buxgalteriyada teskari provodka
    yoziladi, yozuvning o'zi esa kassa kitobida ustidan chizilgan holda
    qolib ketadi.
    """
    _name = 'agronova.kassa.harakat'
    _description = "Kassa harakati (naqd kirim/chiqim)"
    _order = 'date desc, id desc'
    _inherit = ['mail.thread', 'analytic.mixin']

    name = fields.Char(
        string="Order raqami", default=lambda self: _("Yangi"), copy=False,
        readonly=True, index=True,
        help="Kirim orderi (KKO) yoki chiqim orderi (KCHO) raqami.",
    )
    kassa_id = fields.Many2one(
        'agronova.kassa', string="Kassa", required=True, index=True, tracking=True,
        default=lambda self: self.env['agronova.kassa']._default_kassa(),
        ondelete='restrict',
    )
    date = fields.Datetime(
        string="Sana va vaqt", required=True, default=fields.Datetime.now,
        tracking=True,
    )
    date_day = fields.Date(
        string="Kun", compute='_compute_date_day', store=True, index=True,
        help="O'zbekiston vaqti bo'yicha kun — kassa kitobi shu bo'yicha.",
    )
    direction = fields.Selection([
        ('in', "Kirim"),
        ('out', "Chiqim"),
    ], string="Turi", required=True, default='in', index=True, tracking=True)
    amount = fields.Monetary(
        string="Summa", required=True, currency_field='currency_id',
        tracking=True,
    )
    signed_amount = fields.Monetary(
        string="Qoldiqqa ta'siri", compute='_compute_signed', store=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        related='kassa_id.currency_id', string="Valyuta", store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        related='kassa_id.company_id', string="Korxona", store=True,
        readonly=True,
    )
    modda_id = fields.Many2one(
        'agronova.kassa.modda', string="Modda", tracking=True, ondelete='restrict',
        help="Pul qayerdan keldi yoki nimaga sarflandi.",
    )
    partner_id = fields.Many2one(
        'res.partner', string="Kontragent",
        help="Kimdan olindi / kimga berildi.",
    )
    employee_id = fields.Many2one('hr.employee', string="Xodim")
    depozit_id = fields.Many2one(
        'agronova.depozit', string="Depozit", ondelete='restrict',
        help="Depozit moddasida majburiy: pul qaysi mas'ul xodimning "
             "qo'liga berildi yoki kimdan qaytdi.",
    )
    izoh = fields.Text(
        string="Izoh", tracking=True,
        help="Pul nima uchun kirdi yoki chiqdi — erkin matn.",
    )
    user_id = fields.Many2one(
        'res.users', string="Kim kiritdi", readonly=True, copy=False,
        default=lambda self: self.env.user,
    )
    state = fields.Selection([
        ('draft', "Qoralama"),
        ('posted', "Tasdiqlangan"),
        ('storno', "Storno qilingan"),
    ], string="Holat", default='draft', required=True, tracking=True,
        copy=False,
        help="Faqat tasdiqlangan yozuvlar kassa qoldig'iga ta'sir qiladi.")

    # ------------------------------------------------------------------
    # Manba
    # ------------------------------------------------------------------
    manba = fields.Selection([
        ('qol', "Qo'lda (kassir)"),
        ('sotuv', "Sotuvdan to'lov"),
        ('xarid', "Xaridga to'lov"),
        ('oylik', "Xodim oyligi"),
        ('otkazma', "Kassalararo transfer"),
        ('inkassatsiya', "Inkassatsiya"),
        ('boshqa', "Boshqa to'lov"),
    ], string="Manba", default='qol', required=True, index=True, readonly=True)
    auto = fields.Boolean(
        string="Avtomatik", compute='_compute_auto', store=True,
        help="Boshqa hujjatdan ko'chirilgan yozuv — bu yerda tahrirlanmaydi.",
    )
    payment_id = fields.Many2one(
        'account.payment', string="To'lov", readonly=True, copy=False,
        ondelete='set null', index=True,
    )
    otkazma_id = fields.Many2one(
        'agronova.kassa.otkazma', string="Kassalararo transfer", readonly=True,
        copy=False, ondelete='set null', index=True,
    )
    inkassatsiya_id = fields.Many2one(
        'agronova.kassa.inkassatsiya', string="Inkassatsiya", readonly=True,
        copy=False, ondelete='set null', index=True,
    )
    depozit_harakat_id = fields.Many2one(
        'agronova.depozit.harakat', string="Depozit yozuvi", readonly=True,
        copy=False, ondelete='set null',
    )
    origin = fields.Char(string="Manba hujjat", readonly=True, copy=False)

    kun_id = fields.Many2one(
        'agronova.kassa.kun', string="Kassa kitobi varag'i", readonly=True,
        copy=False, ondelete='set null', index=True,
    )
    move_id = fields.Many2one(
        'account.move', string="Provodka", readonly=True, copy=False,
    )
    storno_move_id = fields.Many2one(
        'account.move', string="Storno provodkasi", readonly=True, copy=False,
    )
    storno_sabab = fields.Char(string="Storno sababi", readonly=True, copy=False)

    # ------------------------------------------------------------------
    # Chek
    # ------------------------------------------------------------------
    chek_token = fields.Char(
        string="Chek tokeni", copy=False, index=True, readonly=True,
        help="80mm chekdagi QR kod shu tokenli ochiq sahifaga olib boradi.",
    )
    chek_url = fields.Char(string="Chek havolasi", compute='_compute_chek_url')
    chek_qr_src = fields.Char(
        string="QR rasm manzili", compute='_compute_chek_url',
        help="80mm chek shablonida <img src> uchun tayyor manzil.",
    )

    # ------------------------------------------------------------------
    # COMPUTE
    # ------------------------------------------------------------------

    @api.depends('date')
    def _compute_date_day(self):
        for rec in self:
            rec.date_day = uz_day(rec.date)

    @api.depends('amount', 'direction')
    def _compute_signed(self):
        for rec in self:
            rec.signed_amount = rec.amount if rec.direction == 'in' else -rec.amount

    @api.depends('manba')
    def _compute_auto(self):
        for rec in self:
            rec.auto = rec.manba in AUTO_MANBA

    @api.depends('chek_token')
    def _compute_chek_url(self):
        base = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for rec in self:
            if not rec.chek_token:
                rec.chek_url = False
                rec.chek_qr_src = False
                continue
            rec.chek_url = "%s/kassa/chek/%s" % (base, rec.chek_token)
            # QR rasmini QWeb shablonida qurmaymiz — u yerda urlencode
            # yordamchisi yo'q, shuning uchun tayyor manzil beriladi.
            rec.chek_qr_src = (
                "/report/barcode/?barcode_type=QR&value=%s"
                "&width=180&height=180&humanreadable=0"
                % quote(rec.chek_url, safe=''))

    @api.depends('name', 'direction', 'amount')
    def _compute_display_name(self):
        for rec in self:
            belgi = '+' if rec.direction == 'in' else '−'
            rec.display_name = "%s (%s%s)" % (rec.name or '', belgi,
                                              rec.amount or 0)

    # ------------------------------------------------------------------
    # CONSTRAINTS
    # ------------------------------------------------------------------

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_("Summa 0 dan katta bo'lishi kerak."))

    @api.constrains('modda_id', 'direction')
    def _check_modda_direction(self):
        for rec in self:
            if rec.modda_id and rec.modda_id.direction != rec.direction:
                raise ValidationError(_(
                    "«%(modda)s» moddasi %(mt)s uchun — bu yozuv esa %(t)s.",
                    modda=rec.modda_id.name,
                    mt=_("kirim") if rec.modda_id.direction == 'in' else _("chiqim"),
                    t=_("kirim") if rec.direction == 'in' else _("chiqim")))

    @api.constrains('izoh', 'manba', 'modda_id')
    def _check_izoh(self):
        for rec in self:
            if rec.manba != 'qol':
                continue
            if rec.modda_id and not rec.modda_id.izoh_majburiy:
                continue
            if not (rec.izoh or '').strip():
                raise ValidationError(_(
                    "«%s»: izoh yozilmagan. Pul nima uchun kirgani yoki "
                    "chiqqanini yozing.", rec.name or _("Yangi")))

    @api.constrains('analytic_distribution', 'modda_id', 'manba')
    def _check_analitika(self):
        """TZ ning eng qattiq talabi: analitikasiz xarajat saqlanmaydi."""
        for rec in self:
            if rec.manba != 'qol' or not rec.modda_id:
                continue
            if rec.modda_id.analitik_majburiy and not rec.analytic_distribution:
                raise ValidationError(_(
                    "«%(modda)s» moddasi bo'yicha yozuv analitik kesimsiz "
                    "saqlanmaydi — pul qaysi filial, seh yoki partiyaga "
                    "tegishli ekanini ko'rsating. Aks holda bu summa "
                    "tannarxga tushmay qoladi.", modda=rec.modda_id.name))

    @api.constrains('depozit_id', 'modda_id')
    def _check_depozit(self):
        for rec in self:
            if not rec.modda_id:
                continue
            if rec.modda_id.depozit and not rec.depozit_id:
                raise ValidationError(_(
                    "«%s» moddasida depozit egasi tanlanishi shart — pul "
                    "kimning javobgarligiga o'tayotgani ko'rinishi kerak.",
                    rec.modda_id.name))
            if rec.depozit_id and rec.depozit_id.company_id != rec.company_id:
                raise ValidationError(_(
                    "«%(d)s» depoziti «%(dk)s» korxonasiga tegishli, kassa "
                    "esa «%(kk)s» da.", d=rec.depozit_id.name,
                    dk=rec.depozit_id.company_id.name,
                    kk=rec.company_id.name))

    @api.constrains('partner_id', 'modda_id')
    def _check_kontragent(self):
        for rec in self:
            modda = rec.modda_id
            if not modda:
                continue
            if (modda.qarz_yopish or modda.yetkazuvchi_tolov) and not rec.partner_id:
                raise ValidationError(_(
                    "«%s» moddasida kontragent majburiy — qarz kimning "
                    "hisobidan yopilayotgani ko'rsatilishi kerak.",
                    modda.name))

    # ------------------------------------------------------------------
    # ONCHANGE
    # ------------------------------------------------------------------

    @api.onchange('direction')
    def _onchange_direction(self):
        if self.modda_id and self.modda_id.direction != self.direction:
            self.modda_id = False

    @api.onchange('modda_id')
    def _onchange_modda_id(self):
        if self.modda_id and not self.modda_id.depozit:
            self.depozit_id = False

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _("Yangi"):
                kod = ('agronova.kassa.harakat.in'
                       if vals.get('direction') == 'in'
                       else 'agronova.kassa.harakat.out')
                vals['name'] = self.env['ir.sequence'].next_by_code(kod) or '/'
            vals.setdefault('chek_token', uuid.uuid4().hex)
        records = super().create(vals_list)
        for rec in records:
            rec._sana_tekshir()
            rec._kunga_biriktirish()
            if rec.state == 'posted':
                rec._tasdiqlash()
        return records

    def write(self, vals):
        self._tahrirlash_mumkinmi(vals)
        holat = vals.get('state')
        if holat == 'posted':
            oldin = self.filtered(lambda r: r.state != 'posted')
            res = super().write(vals)
            for rec in oldin:
                rec._sana_tekshir()
                rec._kunga_biriktirish()
                rec._tasdiqlash()
            return res
        res = super().write(vals)
        if {'date', 'kassa_id'}.intersection(vals):
            for rec in self:
                rec._kunga_biriktirish()
        return res

    def unlink(self):
        for rec in self:
            if rec.state != 'draft' and not self.env.context.get('agronova_kassa_force_unlink'):
                raise UserError(_(
                    "«%s» tasdiqlangan yozuv — o'chirilmaydi. Xato bo'lsa "
                    "storno qiling (TZ M04: o'chirish taqiqlanadi).", rec.name))
        return super().unlink()

    def _tahrirlash_mumkinmi(self, vals):
        """Tasdiqlangan va avtomatik yozuvlarni tahrirlash cheklovi."""
        if self.env.context.get('agronova_kassa_sync'):
            return
        # Holat va texnik maydonlar — cheklovsiz
        texnik = {'state', 'kun_id', 'move_id', 'storno_move_id',
                  'storno_sabab', 'payment_id', 'depozit_harakat_id',
                  'message_follower_ids', 'message_ids', 'activity_ids'}
        if set(vals) <= texnik:
            return
        pul_maydonlari = {'amount', 'direction', 'kassa_id', 'date',
                          'modda_id', 'depozit_id', 'analytic_distribution'}
        for rec in self:
            if rec.auto and pul_maydonlari.intersection(vals):
                raise UserError(_(
                    "«%s» — manba hujjatdan kelgan avtomatik yozuv. Summa, "
                    "sana yoki kassani manba hujjatdan o'zgartiring.",
                    rec.name))
            if rec.state != 'draft' and pul_maydonlari.intersection(vals):
                raise UserError(_(
                    "«%s» tasdiqlangan — tahrirlanmaydi. Storno qiling va "
                    "yangi order kiriting.", rec.name))

    # ------------------------------------------------------------------
    # SANA VA KUN QOIDALARI
    # ------------------------------------------------------------------

    def _sana_tekshir(self):
        """Orqaga sana qoidasi (TZ M04).

        Kassir faqat bugungi kunga (yoki sozlamada ruxsat etilgan necha kun
        orqaga) yoza oladi. Menejer va bosh buxgalter cheklanmaydi.
        Avtomatik yozuvlar tekshirilmaydi — ular manba hujjat sanasiga
        ergashadi.
        """
        self.ensure_one()
        if self.auto or self.env.context.get('agronova_kassa_sync'):
            return
        if (self.env.user.has_group('agronova_kassa.group_agronova_kassa_menejer')
                or self.env.user.has_group('agronova_base.group_agronova_bosh_buxgalter')):
            return
        from .utils import uz_today
        bugun = uz_today()
        ruxsat = int(self.env['ir.config_parameter'].sudo().get_param(
            ORQAGA_KUN_PARAM, '0') or 0)
        if self.date_day > bugun:
            raise UserError(_(
                "Kelgusi sanaga kassa orderi yozib bo'lmaydi (%s).",
                self.date_day))
        if (bugun - self.date_day).days > ruxsat:
            raise UserError(_(
                "%(sana)s — orqadagi sana. Kassir %(kun)s kundan orqaga "
                "yoza olmaydi; bu yozuvni bosh buxgalter kiritadi.",
                sana=self.date_day, kun=ruxsat))

    def _kunga_biriktirish(self):
        """Yozuvni kassa kitobining varag'iga bog'laydi."""
        self.ensure_one()
        if not self.kassa_id or not self.date_day:
            return
        Kun = self.env['agronova.kassa.kun']
        # Kun yopish majburiyati: oldingi kun yopilmagan bo'lsa yangi kunga
        # yozib bo'lmaydi. Avtomatik yozuvlar bundan mustasno.
        if not self.auto and self.kassa_id.kun_yopish_majburiy:
            ochiq = Kun._oldingi_ochiq_kun(self.kassa_id, self.date_day)
            if ochiq:
                raise UserError(_(
                    "«%(kassa)s» kassasining %(sana)s kuni hali yopilmagan. "
                    "Yangi kunga yozuv kiritishdan oldin o'sha kunni yoping "
                    "(pulni sanab, farqni ko'rsatib).",
                    kassa=self.kassa_id.name, sana=ochiq.date))
        kun = Kun._kun_topish(self.kassa_id, self.date_day)
        if kun and self.kun_id != kun:
            self.with_context(agronova_kassa_sync=True).kun_id = kun.id
        if kun and kun.state == 'closed':
            if self.auto:
                # Avtomatik yozuvni to'sib bo'lmaydi (to'lov allaqachon
                # buxgalteriyaga tushgan) — lekin menejer buni bilsin.
                kun.message_post(body=_(
                    "Diqqat: kun yopilgandan keyin avtomatik yozuv tushdi — "
                    "%(nom)s, %(summa)s. Kunni qayta hisoblang.",
                    nom=self.name, summa=self.amount))
            else:
                raise UserError(_(
                    "%(sana)s kuni yopilgan — yangi order qo'shib bo'lmaydi. "
                    "Menejer kunni qayta ochishi kerak.", sana=self.date_day))

    # ------------------------------------------------------------------
    # TASDIQLASH
    # ------------------------------------------------------------------

    def _tasdiqlash(self):
        self.ensure_one()
        self._qoldiq_tekshir()
        self._depozit_yozish()
        self._provodka_yaratish()

    def _qoldiq_tekshir(self):
        """Kassada bor puldan ko'p chiqim qilinmasin."""
        self.ensure_one()
        if self.direction != 'out' or self.auto:
            return
        kassa = self.kassa_id
        if kassa.allow_negative:
            return
        groups = self.env['agronova.kassa.harakat'].sudo()._read_group(
            [('kassa_id', '=', kassa.id), ('state', '=', 'posted'),
             ('id', '!=', self.id)],
            [], ['signed_amount:sum'],
        )
        boshqalar = (groups[0][0] if groups else 0.0) or 0.0
        mavjud = (kassa.opening_balance or 0.0) + boshqalar
        if mavjud < self.amount:
            raise UserError(_(
                "«%(kassa)s» kassasida yetarli pul yo'q.\n"
                "Kassada: %(bor)s\nChiqim: %(chiqim)s",
                kassa=kassa.name, bor=mavjud, chiqim=self.amount))

    # ------------------------------------------------------------------
    # DEPOZIT
    # ------------------------------------------------------------------

    def _depozit_yozish(self):
        """Depozit moddasida `agronova.depozit` ga qarama-qarshi yozuv qo'yadi.

        Kassadan CHIQIM  → depozitga KIRIM (pul mas'ul xodim qo'liga o'tdi).
        Kassaga  KIRIM   → depozitdan CHIQIM (pul qaytarildi).

        Depozitdagi pul kassa qoldig'iga kirmaydi — u allaqachon kassadan
        chiqib ketgan; shuning uchun ikki marta sanalmaydi.
        """
        self.ensure_one()
        if self.depozit_harakat_id or not self.depozit_id:
            return False
        if not (self.modda_id and self.modda_id.depozit):
            return False
        turi = 'kirim' if self.direction == 'out' else 'chiqim'
        harakat = self.env['agronova.depozit.harakat'].sudo().create({
            'depozit_id': self.depozit_id.id,
            'turi': turi,
            'summa': self.amount,
            'sana': self.date_day,
            'izoh': _("Kassa %(nom)s: %(izoh)s", nom=self.name,
                      izoh=(self.izoh or self.modda_id.name or '')),
            'holat': 'tasdiqlangan',
            'manba_model': self._name,
            'manba_id': self.id,
        })
        self.with_context(agronova_kassa_sync=True).depozit_harakat_id = harakat.id
        return harakat

    # ------------------------------------------------------------------
    # BUXGALTERIYA
    # ------------------------------------------------------------------

    def _provodka_yaratish(self):
        """Qo'lda kiritilgan yozuv uchun provodka.

        Modda «qarz yopadi» deb belgilangan bo'lsa — oddiy provodka emas,
        `account.payment` yaratiladi va kontragentning ochiq hujjatlari
        bilan yarashtiriladi. Shunda mijoz/yetkazuvchi qarzi avtomat
        kamayadi va to'lov Odooning o'z hisobotlarida ham ko'rinadi.
        """
        self.ensure_one()
        if self.move_id or self.payment_id or self.auto:
            return False
        kassa = self.kassa_id
        if not kassa.buxgalteriya:
            return False
        if not self.modda_id:
            raise UserError(_("Modda tanlanmagan — provodka yozib bo'lmaydi."))
        if self.modda_id.qarz_yopish or self.modda_id.yetkazuvchi_tolov:
            return self._tolov_yaratish()
        return self._oddiy_provodka()

    def _oddiy_provodka(self):
        """KIRIM: Dt kassa / Kt modda.  CHIQIM: Dt modda / Kt kassa."""
        self.ensure_one()
        kassa = self.kassa_id
        if not kassa.account_id:
            raise UserError(_(
                "«%s» kassasining buxgalteriya hisobi tanlanmagan "
                "(Kassa → Sozlamalar → Kassalar).", kassa.name))
        if not self.modda_id.account_id:
            raise UserError(_(
                "«%s» moddasining buxgalteriya hisobi tanlanmagan "
                "(Kassa → Sozlamalar → Moddalar).", self.modda_id.name))
        journal = kassa.journal_id
        if not journal:
            raise UserError(_(
                "«%s» kassasiga naqd jurnali tanlanmagan.", kassa.name))

        kassa_coa = kassa.account_id
        modda_coa = self.modda_id.account_id
        summa = self._kompaniya_summasi()
        izoh = self._provodka_izohi()
        partner = self.partner_id or self.employee_id.work_contact_id

        debet, kredit = ((kassa_coa, modda_coa) if self.direction == 'in'
                         else (modda_coa, kassa_coa))
        umumiy = {'partner_id': partner.id if partner else False, 'name': izoh}
        debet_vals = dict(umumiy, account_id=debet.id, debit=summa, credit=0.0)
        kredit_vals = dict(umumiy, account_id=kredit.id, debit=0.0, credit=summa)
        # Analitika modda tomonida — kassa hisobida analitika bo'lmaydi.
        if self.analytic_distribution:
            modda_tomoni = debet_vals if debet == modda_coa else kredit_vals
            modda_tomoni['analytic_distribution'] = self.analytic_distribution
        if self.currency_id and self.currency_id != self.company_id.currency_id:
            if debet == kassa_coa:
                debet_vals.update(currency_id=self.currency_id.id,
                                  amount_currency=self.amount)
                kredit_vals.update(currency_id=self.currency_id.id,
                                   amount_currency=-self.amount)
            else:
                debet_vals.update(currency_id=self.currency_id.id,
                                  amount_currency=self.amount)
                kredit_vals.update(currency_id=self.currency_id.id,
                                   amount_currency=-self.amount)

        move = self.env['account.move'].sudo().with_company(self.company_id).create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': self.date_day,
            'ref': izoh,
            'line_ids': [(0, 0, debet_vals), (0, 0, kredit_vals)],
        })
        move.action_post()
        self.with_context(agronova_kassa_sync=True).move_id = move.id
        return move

    def _tolov_yaratish(self):
        """Kontragent qarzini yopadigan to'lov (account.payment)."""
        self.ensure_one()
        kassa = self.kassa_id
        if not kassa.journal_id:
            raise UserError(_(
                "«%s» kassasiga naqd jurnali tanlanmagan — to'lov yozib "
                "bo'lmaydi.", kassa.name))
        Payment = self.env['account.payment'].sudo().with_company(self.company_id)
        payment = Payment.with_context(agronova_kassa_skip_mirror=True).create({
            'payment_type': 'inbound' if self.direction == 'in' else 'outbound',
            'partner_type': ('customer' if self.modda_id.qarz_yopish
                             else 'supplier'),
            'partner_id': self.partner_id.id,
            'amount': self.amount,
            'currency_id': self.currency_id.id,
            'date': self.date_day,
            'journal_id': kassa.journal_id.id,
            'memo': self._provodka_izohi(),
        })
        payment.with_context(agronova_kassa_skip_mirror=True).action_post()
        if not payment.move_id:
            # Odoo 19: outstanding hisobisiz to'lov `in_process` da qolib
            # ketadi va provodka umuman yozilmaydi. Kassa uchun bu jim
            # qolib ketmasligi kerak — pul kassada, lekin buxgalteriyada
            # yo'q bo'lib qolardi.
            raise UserError(_(
                "«%(jurnal)s» jurnalining to'lov usulida «outstanding» "
                "hisobi tanlanmagan — shuning uchun to'lovga provodka "
                "yozilmadi. Kassa kartochkasini qayta saqlang yoki "
                "jurnalning to'lov usuliga %(hisob)s hisobini qo'ying.",
                jurnal=kassa.journal_id.name,
                hisob=kassa.account_id.display_name or '5010'))
        self.with_context(agronova_kassa_sync=True).write({
            'payment_id': payment.id,
            'move_id': payment.move_id.id,
        })
        payment.sudo().agronova_harakat_id = self.id
        self._qarzni_yopish(payment)
        return payment

    def _qarzni_yopish(self, payment):
        """To'lovni kontragentning eng eski ochiq hujjatlari bilan yarashtiradi."""
        self.ensure_one()
        hisob_turi = ('asset_receivable' if self.direction == 'in'
                      else 'liability_payable')
        tolov_satri = payment.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type == hisob_turi
            and not l.reconciled)
        if not tolov_satri:
            return False
        ochiq = self.env['account.move.line'].sudo().search([
            ('partner_id', '=', self.partner_id.id),
            ('account_id', '=', tolov_satri[0].account_id.id),
            ('parent_state', '=', 'posted'),
            ('reconciled', '=', False),
            ('id', 'not in', tolov_satri.ids),
        ], order='date_maturity, date, id')
        if not ochiq:
            self.message_post(body=_(
                "«%s» ning ochiq hisob-fakturasi topilmadi — to'lov "
                "yarashtirilmagan holda qoldi (avans).",
                self.partner_id.display_name))
            return False
        try:
            (tolov_satri | ochiq).reconcile()
        except Exception as e:  # noqa: BLE001 — yarashtirish yiqilsa ham to'lov qoladi
            _logger.warning("Kassa to'lovini yarashtirib bo'lmadi (%s): %s",
                            self.id, e)
            self.message_post(body=_(
                "To'lov yozildi, lekin hisob-faktura bilan avtomatik "
                "yarashtirib bo'lmadi. Buxgalter qo'lda yarashtiradi."))
            return False
        return True

    def _kompaniya_summasi(self):
        """Summa korxona valyutasida."""
        self.ensure_one()
        company_currency = self.company_id.currency_id
        if self.currency_id and self.currency_id != company_currency:
            return self.currency_id._convert(
                self.amount, company_currency, self.company_id, self.date_day)
        return self.amount

    def _provodka_izohi(self):
        self.ensure_one()
        qismlar = [self.name]
        if self.modda_id:
            qismlar.append(self.modda_id.name)
        kim = (self.partner_id.display_name or self.employee_id.display_name
               or self.depozit_id.display_name)
        if kim:
            qismlar.append(kim)
        if self.izoh:
            qismlar.append((self.izoh or '').strip().replace('\n', ' ')[:120])
        return ' — '.join([q for q in qismlar if q])

    # ------------------------------------------------------------------
    # STORNO
    # ------------------------------------------------------------------

    def action_storno_wizard(self):
        """Formadagi tugma — sababni so'raydi."""
        self.ensure_one()
        return {
            'name': _("Storno sababi"),
            'type': 'ir.actions.act_window',
            'res_model': 'agronova.kassa.storno.wizard',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {'default_harakat_id': self.id},
        }

    def action_storno(self, sabab=''):
        """Tasdiqlangan yozuvni storno qiladi.

        Yozuv o'chirilmaydi va holati tarixda qoladi; buxgalteriyada esa
        teskari provodka yoziladi (`_reverse_moves`), ya'ni jurnal
        raqamlarida bo'shliq qolmaydi — audit izi buzilmaydi.
        """
        for rec in self:
            if rec.state != 'posted':
                raise UserError(_(
                    "«%s»: faqat tasdiqlangan yozuv storno qilinadi.",
                    rec.name))
            if rec.auto and not self.env.context.get('agronova_kassa_sync'):
                raise UserError(_(
                    "«%s» — manba hujjatdan kelgan yozuv. Uni storno qilish "
                    "uchun manba hujjatni (to'lov, transfer yoki "
                    "inkassatsiya) bekor qiling.", rec.name))
            kun = rec.kun_id
            if kun and kun.state == 'closed' and not rec.auto:
                raise UserError(_(
                    "%(sana)s kuni yopilgan — storno qilishdan oldin "
                    "menejer kunni qayta ochishi kerak.", sana=kun.date))
            rec._provodka_storno()
            rec._depozit_storno()
            rec.with_context(agronova_kassa_sync=True).write({
                'state': 'storno',
                'storno_sabab': sabab or rec.storno_sabab or '',
            })
            rec.message_post(body=_(
                "Storno qilindi. Sabab: %s", sabab or _("ko'rsatilmagan")))
        return True

    def _provodka_storno(self):
        self.ensure_one()
        move = self.move_id
        if not move or move.state != 'posted':
            return False
        try:
            teskari = move._reverse_moves([{
                'date': max(move.date, self.date_day),
                'ref': _("STORNO: %s", move.ref or self.name),
            }], cancel=True)
            self.with_context(agronova_kassa_sync=True).storno_move_id = teskari[:1].id
            return teskari
        except Exception as e:  # noqa: BLE001
            _logger.exception("Kassa provodkasini storno qilib bo'lmadi (%s): %s",
                              move.id, e)
            raise UserError(_(
                "Buxgalteriya provodkasini storno qilib bo'lmadi: %s\n"
                "Bosh buxgalterga murojaat qiling.", e)) from e

    def _depozit_storno(self):
        self.ensure_one()
        if self.depozit_harakat_id.holat == 'tasdiqlangan':
            self.depozit_harakat_id.sudo().action_storno()
        return True

    # ------------------------------------------------------------------
    # ACTIONS
    # ------------------------------------------------------------------

    def action_post(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Faqat qoralama orderni tasdiqlash mumkin."))
        return self.write({'state': 'posted'})

    def action_print_chek(self):
        self.ensure_one()
        return self.env.ref(
            'agronova_kassa.action_report_kassa_chek').report_action(self)

    def action_open_source(self):
        """Manba hujjatni ochish."""
        self.ensure_one()
        hujjatlar = [
            (self.payment_id, 'account.payment'),
            (self.otkazma_id, 'agronova.kassa.otkazma'),
            (self.inkassatsiya_id, 'agronova.kassa.inkassatsiya'),
            (self.move_id, 'account.move'),
        ]
        for rec, model in hujjatlar:
            if rec:
                return {
                    'type': 'ir.actions.act_window', 'res_model': model,
                    'res_id': rec.id, 'views': [(False, 'form')],
                }
        raise UserError(_("Bu yozuvda manba hujjat yo'q."))

    # ------------------------------------------------------------------
    # PANEL
    # ------------------------------------------------------------------

    MANBA_BELGI = {
        'qol': '', 'sotuv': '🧾', 'xarid': '📦', 'oylik': '👷',
        'otkazma': '⇄', 'inkassatsiya': '🏦', 'boshqa': '💳',
    }

    def _panel_line(self):
        self.ensure_one()
        return {
            'id': self.id,
            'name': self.name,
            'time': fields.Datetime.to_string(self.date),
            'direction': self.direction,
            'amount': self.amount,
            'modda': self.modda_id.name or '',
            'kim': self._panel_kim(),
            'izoh': self.izoh or '',
            'manba': self.manba,
            'belgi': self.MANBA_BELGI.get(self.manba, ''),
            'auto': self.auto,
            'user': self.user_id.name or '',
            'state': self.state,
            'chek_url': self.chek_url or '',
        }

    def _panel_kim(self):
        """«Kim» ustuni: kontragent / xodim / depozit, transferda — kassa."""
        self.ensure_one()
        kim = (self.partner_id.display_name or self.employee_id.display_name
               or self.depozit_id.display_name)
        if not kim and self.otkazma_id:
            boshqa = (self.otkazma_id.to_kassa_id if self.direction == 'out'
                      else self.otkazma_id.from_kassa_id)
            kim = boshqa.name
        if not kim and self.inkassatsiya_id:
            kim = self.inkassatsiya_id.bank_journal_id.name
        return kim or ''

    # ------------------------------------------------------------------
    # INTEGRATSIYA
    # ------------------------------------------------------------------

    @api.model
    def _avto_yozuv(self, kassa, vals):
        """Boshqa hujjatdan avtomatik yozuv (darhol tasdiqlangan)."""
        if not kassa:
            return self.browse()
        vals = dict(vals, kassa_id=kassa.id, state='posted')
        return self.with_context(agronova_kassa_sync=True).sudo().create(vals)

    def _avto_storno(self, sabab=None):
        """Manba hujjat bekor qilinganda ko'chirilgan yozuvni storno qiladi."""
        stornolanadi = self.filtered(lambda r: r.state == 'posted')
        if not stornolanadi:
            return
        stornolanadi.with_context(agronova_kassa_sync=True).sudo().action_storno(
            sabab=sabab or _("Manba hujjat bekor qilindi"))


class AgroNovaKassaStornoWizard(models.TransientModel):
    """Storno sababini so'raydigan oyna — sababsiz storno yozilmasin."""
    _name = 'agronova.kassa.storno.wizard'
    _description = "Kassa yozuvini storno qilish"

    harakat_id = fields.Many2one(
        'agronova.kassa.harakat', string="Yozuv", required=True, readonly=True)
    sabab = fields.Char(string="Storno sababi", required=True)

    def action_tasdiqlash(self):
        self.ensure_one()
        self.harakat_id.action_storno(sabab=self.sabab)
        return {'type': 'ir.actions.act_window_close'}
