# -*- coding: utf-8 -*-
"""Kassalararo transfer — bir kassadan boshqasiga naqd pul topshirish.

TZ M04 dagi zanjir to'liq saqlangan: **qoralama → yo'lda → tasdiq / rad**.

Nega uch bosqich kerak? Filiallar bir-biridan uzoq (Toshkent — Baliqchi),
pul mashinada yo'lda ketadi. Ikki bosqichli sxemada (donxolmdagidek)
jo'natilgan zahoti qabul qiluvchida kirim yozilardi — ya'ni hali qo'lga
tegmagan pul ikkinchi kassada «bor» bo'lib ko'rinardi.

Shu sababli:

    jo'natildi  → Dt 5710 «Yo'ldagi pul»  Kt 5010 manba kassa
    qabul qilindi → Dt 5010 qabul kassa   Kt 5710 «Yo'ldagi pul»
    rad etildi  → Dt 5010 manba kassa     Kt 5710 «Yo'ldagi pul»

«Yo'lda» bosqichida pul hech qaysi kassada emas, lekin balansdan ham
yo'qolmaydi — u tranzit hisobida turadi va kim javobgar ekani (olib
boruvchi) hujjatda yozilgan.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .utils import uz_day

_logger = logging.getLogger(__name__)


class AgroNovaKassaOtkazma(models.Model):
    _name = 'agronova.kassa.otkazma'
    _description = "Kassalararo transfer"
    _order = 'date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string="Raqam", default=lambda self: _("Yangi"), copy=False,
        readonly=True,
    )
    date = fields.Datetime(
        string="Jo'natilgan sana", required=True, default=fields.Datetime.now,
        tracking=True,
    )
    date_day = fields.Date(
        string="Kun", compute='_compute_date_day', store=True, index=True,
    )
    qabul_date = fields.Datetime(
        string="Qabul qilingan sana", readonly=True, copy=False, tracking=True,
    )
    from_kassa_id = fields.Many2one(
        'agronova.kassa', string="Qaysi kassadan", required=True, index=True,
        tracking=True, ondelete='restrict',
        default=lambda self: self.env['agronova.kassa']._default_kassa(),
    )
    to_kassa_id = fields.Many2one(
        'agronova.kassa', string="Qaysi kassaga", required=True, index=True,
        tracking=True, ondelete='restrict',
    )
    amount = fields.Monetary(
        string="Summa", required=True, currency_field='currency_id',
        tracking=True,
    )
    currency_id = fields.Many2one(
        related='from_kassa_id.currency_id', string="Valyuta", store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        related='from_kassa_id.company_id', string="Korxona", store=True,
        readonly=True,
    )
    olib_boruvchi_id = fields.Many2one(
        'hr.employee', string="Olib boruvchi", tracking=True,
        help="Pulni yo'lda kim olib ketyapti — «yo'lda» bosqichida "
             "javobgar shu xodim.",
    )
    izoh = fields.Text(string="Izoh", tracking=True)
    rad_sabab = fields.Char(string="Rad etish sababi", readonly=True, copy=False)
    user_id = fields.Many2one(
        'res.users', string="Kim jo'natdi", readonly=True, copy=False,
        default=lambda self: self.env.user,
    )
    qabul_user_id = fields.Many2one(
        'res.users', string="Kim qabul qildi", readonly=True, copy=False,
    )
    state = fields.Selection([
        ('draft', "Qoralama"),
        ('transit', "Yo'lda"),
        ('done', "Tasdiqlangan"),
        ('rad', "Rad etilgan"),
    ], string="Holat", default='draft', required=True, tracking=True,
        copy=False)

    from_balance = fields.Monetary(
        string="Manba kassada bor", compute='_compute_qoldiqlar',
        currency_field='currency_id',
    )
    to_balance = fields.Monetary(
        string="Qabul qiluvchida bor", compute='_compute_qoldiqlar',
        currency_field='currency_id',
    )

    out_harakat_id = fields.Many2one(
        'agronova.kassa.harakat', string="Chiqim yozuvi", readonly=True,
        copy=False, ondelete='set null',
    )
    in_harakat_id = fields.Many2one(
        'agronova.kassa.harakat', string="Kirim yozuvi", readonly=True,
        copy=False, ondelete='set null',
    )
    qaytish_harakat_id = fields.Many2one(
        'agronova.kassa.harakat', string="Qaytish yozuvi", readonly=True,
        copy=False, ondelete='set null',
    )
    move_ids = fields.Many2many(
        'account.move', string="Provodkalar", readonly=True, copy=False,
    )

    # ------------------------------------------------------------------
    # COMPUTE
    # ------------------------------------------------------------------

    @api.depends('date')
    def _compute_date_day(self):
        for rec in self:
            rec.date_day = uz_day(rec.date)

    @api.depends('from_kassa_id.balance', 'to_kassa_id.balance')
    def _compute_qoldiqlar(self):
        for rec in self:
            rec.from_balance = rec.from_kassa_id.balance
            rec.to_balance = rec.to_kassa_id.balance

    @api.depends('name', 'from_kassa_id', 'to_kassa_id')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "%s (%s → %s)" % (
                rec.name or '', rec.from_kassa_id.name or '?',
                rec.to_kassa_id.name or '?')

    # ------------------------------------------------------------------
    # CONSTRAINTS
    # ------------------------------------------------------------------

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_("Summa 0 dan katta bo'lishi kerak."))

    @api.constrains('from_kassa_id', 'to_kassa_id')
    def _check_kassalar(self):
        for rec in self:
            if not rec.from_kassa_id or not rec.to_kassa_id:
                continue
            if rec.from_kassa_id == rec.to_kassa_id:
                raise ValidationError(_(
                    "Transfer bitta kassaning o'ziga qilinmaydi."))
            if rec.from_kassa_id.currency_id != rec.to_kassa_id.currency_id:
                raise ValidationError(_(
                    "Valyutalar mos emas — transfer faqat bir xil "
                    "valyutadagi kassalar orasida bo'ladi.\n"
                    "• %(a)s — %(av)s\n• %(b)s — %(bv)s",
                    a=rec.from_kassa_id.name,
                    av=rec.from_kassa_id.currency_id.name,
                    b=rec.to_kassa_id.name,
                    bv=rec.to_kassa_id.currency_id.name))

    @api.onchange('from_kassa_id')
    def _onchange_from_kassa_id(self):
        boshqa = self.to_kassa_id
        if not self.from_kassa_id or not boshqa:
            return
        if (boshqa == self.from_kassa_id
                or boshqa.currency_id != self.from_kassa_id.currency_id):
            self.to_kassa_id = False

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _("Yangi"):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'agronova.kassa.otkazma') or '/'
        return super().create(vals_list)

    def write(self, vals):
        qoriqlanadi = {'amount', 'from_kassa_id', 'to_kassa_id', 'date'}
        if qoriqlanadi.intersection(vals):
            for rec in self:
                if rec.state != 'draft':
                    raise UserError(_(
                        "«%s» qoralama emas — summani yoki kassalarni "
                        "o'zgartirib bo'lmaydi.", rec.name))
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_(
                    "«%s» — jo'natilgan transfer o'chirilmaydi. Rad eting "
                    "(tarix saqlanib qolishi uchun).", rec.name))
        return super().unlink()

    # ------------------------------------------------------------------
    # TEKSHIRUVLAR
    # ------------------------------------------------------------------

    def _qoldiq_tekshir(self):
        self.ensure_one()
        kassa = self.from_kassa_id
        if kassa.allow_negative:
            return
        if kassa.balance < self.amount:
            raise UserError(_(
                "«%(kassa)s» kassasida yetarli pul yo'q.\n"
                "Kassada: %(bor)s\nTransfer: %(summa)s",
                kassa=kassa.name, bor=kassa.balance, summa=self.amount))

    def _kun_tekshir(self, kassalar):
        self.ensure_one()
        Kun = self.env['agronova.kassa.kun']
        sana = uz_day(fields.Datetime.now())
        for kassa in kassalar:
            kun = Kun._kun_topish(kassa, sana, yaratish=False)
            if kun and kun.state == 'closed':
                raise UserError(_(
                    "«%(kassa)s» kassasining %(sana)s kuni yopilgan — "
                    "transfer yozib bo'lmaydi. Menejer kunni qayta ochishi "
                    "kerak.", kassa=kassa.name, sana=sana))

    def _transit_hisob(self):
        """Ikki kassadan qaysi biri tranzit hisobini beradi."""
        self.ensure_one()
        hisob = (self.from_kassa_id._transit_account()
                 or self.to_kassa_id._transit_account())
        if not hisob:
            raise UserError(_(
                "«Yo'ldagi pul» hisobi (5710) topilmadi. Kassa kartochkasida "
                "yoki korxona sozlamalarida ko'rsating."))
        return hisob

    # ------------------------------------------------------------------
    # PROVODKA
    # ------------------------------------------------------------------

    def _provodka(self, debet_account, kredit_account, izoh, sana):
        """Ikki satrli provodka yozadi va uni hujjatga bog'laydi."""
        self.ensure_one()
        journal = self.from_kassa_id.journal_id or self.to_kassa_id.journal_id
        if not journal:
            raise UserError(_(
                "«%s» kassasiga naqd jurnali tanlanmagan.",
                self.from_kassa_id.name))
        if debet_account == kredit_account:
            self.message_post(body=_(
                "Provodka yozilmadi: ikkala tomon ham bitta hisobga "
                "(«%s») bog'langan.", debet_account.display_name))
            return False
        company = self.company_id or self.env.company
        summa = self.amount
        if self.currency_id and self.currency_id != company.currency_id:
            summa = self.currency_id._convert(
                self.amount, company.currency_id, company, sana)
        debet = {'name': izoh, 'account_id': debet_account.id,
                 'debit': summa, 'credit': 0.0}
        kredit = {'name': izoh, 'account_id': kredit_account.id,
                  'debit': 0.0, 'credit': summa}
        if self.currency_id and self.currency_id != company.currency_id:
            debet.update(currency_id=self.currency_id.id,
                         amount_currency=self.amount)
            kredit.update(currency_id=self.currency_id.id,
                          amount_currency=-self.amount)
        move = self.env['account.move'].sudo().with_company(company).create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': sana,
            'ref': izoh,
            'line_ids': [(0, 0, debet), (0, 0, kredit)],
        })
        move.action_post()
        self.sudo().move_ids = [(4, move.id)]
        return move

    # ------------------------------------------------------------------
    # BOSQICHLAR
    # ------------------------------------------------------------------

    def action_jonatish(self):
        """Qoralama → Yo'lda. Manba kassada chiqim, pul tranzitga o'tadi."""
        Harakat = self.env['agronova.kassa.harakat']
        Modda = self.env['agronova.kassa.modda']
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Faqat qoralama transferni jo'natish mumkin."))
            rec._kun_tekshir(rec.from_kassa_id)
            rec._qoldiq_tekshir()
            chiqim = Harakat._avto_yozuv(rec.from_kassa_id, {
                'date': rec.date,
                'direction': 'out',
                'amount': rec.amount,
                'modda_id': Modda._hujjat_moddasi('otkazma', 'out').id or False,
                'manba': 'otkazma',
                'otkazma_id': rec.id,
                'origin': rec.name,
                'izoh': _("«%(kassa)s» kassasiga jo'natildi. %(izoh)s",
                          kassa=rec.to_kassa_id.name, izoh=rec.izoh or ''),
            })
            rec.out_harakat_id = chiqim.id
            rec._provodka(
                rec._transit_hisob(), rec.from_kassa_id.account_id,
                _("%(nom)s — %(a)s → yo'lda", nom=rec.name,
                  a=rec.from_kassa_id.name),
                rec.date_day)
            rec.state = 'transit'
            rec.message_post(body=_(
                "Jo'natildi: %(summa)s, «%(a)s» → «%(b)s». Olib boruvchi: "
                "%(kim)s. Qabul qiluvchi tasdiqlashi kutilmoqda.",
                summa=rec.amount, a=rec.from_kassa_id.name,
                b=rec.to_kassa_id.name,
                kim=rec.olib_boruvchi_id.display_name or _("ko'rsatilmagan")))
            rec._qabul_eslatmasi()
        return True

    def _qabul_eslatmasi(self):
        """Qabul qiluvchi kassirlarga vazifa qo'yadi."""
        self.ensure_one()
        qabul_userlar = self.to_kassa_id.user_ids
        if not qabul_userlar:
            return
        for user in qabul_userlar:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=user.id,
                summary=_("Kassaga pul keldi — qabul qiling"),
                note=_("«%(a)s» kassasidan %(summa)s jo'natildi (%(nom)s).",
                       a=self.from_kassa_id.name, summa=self.amount,
                       nom=self.name),
            )

    def action_qabul(self, sanoq=None):
        """Yo'lda → Tasdiqlangan. Qabul qiluvchi kassada kirim yoziladi."""
        Harakat = self.env['agronova.kassa.harakat']
        Modda = self.env['agronova.kassa.modda']
        for rec in self:
            if rec.state != 'transit':
                raise UserError(_(
                    "«%s»: faqat yo'ldagi transferni qabul qilish mumkin.",
                    rec.name))
            if sanoq is not None and not rec.currency_id.is_zero(
                    float(sanoq) - rec.amount):
                raise UserError(_(
                    "Sanab olingan summa (%(sanoq)s) hujjatdagidan "
                    "(%(summa)s) farq qiladi. Bunday holatda transferni "
                    "QABUL QILMANG — rad eting, manba kassa to'g'ri summa "
                    "bilan qayta jo'natsin.",
                    sanoq=sanoq, summa=rec.amount))
            rec._kun_tekshir(rec.to_kassa_id)
            kirim = Harakat._avto_yozuv(rec.to_kassa_id, {
                'date': fields.Datetime.now(),
                'direction': 'in',
                'amount': rec.amount,
                'modda_id': Modda._hujjat_moddasi('otkazma', 'in').id or False,
                'manba': 'otkazma',
                'otkazma_id': rec.id,
                'origin': rec.name,
                'izoh': _("«%(kassa)s» kassasidan keldi. %(izoh)s",
                          kassa=rec.from_kassa_id.name, izoh=rec.izoh or ''),
            })
            rec._provodka(
                rec.to_kassa_id.account_id, rec._transit_hisob(),
                _("%(nom)s — yo'ldan → %(b)s", nom=rec.name,
                  b=rec.to_kassa_id.name),
                kirim.date_day)
            rec.write({
                'in_harakat_id': kirim.id,
                'state': 'done',
                'qabul_date': fields.Datetime.now(),
                'qabul_user_id': self.env.user.id,
            })
            rec.activity_unlink(['mail.mail_activity_data_todo'])
            rec.message_post(body=_(
                "Qabul qilindi: %(summa)s «%(b)s» kassasiga kirdi.",
                summa=rec.amount, b=rec.to_kassa_id.name))
        return True

    def action_rad(self, sabab=''):
        """Yo'lda → Rad etilgan. Pul manba kassaga qaytadi."""
        Harakat = self.env['agronova.kassa.harakat']
        Modda = self.env['agronova.kassa.modda']
        for rec in self:
            if rec.state != 'transit':
                raise UserError(_(
                    "«%s»: faqat yo'ldagi transferni rad etish mumkin.",
                    rec.name))
            rec._kun_tekshir(rec.from_kassa_id)
            qaytish = Harakat._avto_yozuv(rec.from_kassa_id, {
                'date': fields.Datetime.now(),
                'direction': 'in',
                'amount': rec.amount,
                'modda_id': Modda._hujjat_moddasi('otkazma', 'in').id or False,
                'manba': 'otkazma',
                'otkazma_id': rec.id,
                'origin': rec.name,
                'izoh': _("Transfer rad etildi, pul qaytdi. %s", sabab or ''),
            })
            rec._provodka(
                rec.from_kassa_id.account_id, rec._transit_hisob(),
                _("%(nom)s — RAD ETILDI, %(a)s ga qaytdi", nom=rec.name,
                  a=rec.from_kassa_id.name),
                qaytish.date_day)
            rec.write({
                'qaytish_harakat_id': qaytish.id,
                'state': 'rad',
                'rad_sabab': sabab or '',
            })
            rec.activity_unlink(['mail.mail_activity_data_todo'])
            rec.message_post(body=_(
                "Rad etildi. Sabab: %(sabab)s. %(summa)s «%(a)s» kassasiga "
                "qaytarildi.", sabab=sabab or _("ko'rsatilmagan"),
                summa=rec.amount, a=rec.from_kassa_id.name))
        return True

    def action_rad_wizard(self):
        self.ensure_one()
        return {
            'name': _("Transferni rad etish"),
            'type': 'ir.actions.act_window',
            'res_model': 'agronova.kassa.otkazma.rad.wizard',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {'default_otkazma_id': self.id},
        }

    def action_open_harakatlar(self):
        self.ensure_one()
        return {
            'name': _("«%s» yozuvlari", self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'agronova.kassa.harakat',
            'views': [(False, 'list'), (False, 'form')],
            'domain': [('otkazma_id', '=', self.id)],
            'context': {'create': False},
        }

    def action_open_moves(self):
        self.ensure_one()
        return {
            'name': _("«%s» provodkalari", self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'views': [(False, 'list'), (False, 'form')],
            'domain': [('id', 'in', self.move_ids.ids)],
        }


class AgroNovaKassaOtkazmaRadWizard(models.TransientModel):
    _name = 'agronova.kassa.otkazma.rad.wizard'
    _description = "Transferni rad etish sababi"

    otkazma_id = fields.Many2one(
        'agronova.kassa.otkazma', string="Transfer", required=True, readonly=True)
    sabab = fields.Char(string="Rad etish sababi", required=True)

    def action_tasdiqlash(self):
        self.ensure_one()
        self.otkazma_id.action_rad(sabab=self.sabab)
        return {'type': 'ir.actions.act_window_close'}
