# -*- coding: utf-8 -*-
"""Inkassatsiya — kassadan bankka naqd pul topshirish.

Zanjir kassalararo transfer bilan bir xil, chunki muammo ham bir xil:
pul kassadan chiqib ketdi, lekin bank hisobiga hali tushmadi. Shu oraliqda
u **5710 «Yo'ldagi pul»** hisobida turadi va bank ko'chirmasi kelgach
tasdiqlanadi.

    jo'natildi   → Dt 5710 «Yo'ldagi pul»   Kt 5010 kassa
    bank tasdiqi → Dt 5110 bank hisobi      Kt 5710 «Yo'ldagi pul»
    rad etildi   → Dt 5010 kassa            Kt 5710 «Yo'ldagi pul»
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .utils import uz_day


class AgroNovaKassaInkassatsiya(models.Model):
    _name = 'agronova.kassa.inkassatsiya'
    _description = "Inkassatsiya (kassa → bank)"
    _order = 'date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string="Raqam", default=lambda self: _("Yangi"), copy=False,
        readonly=True,
    )
    date = fields.Datetime(
        string="Topshirilgan sana", required=True, default=fields.Datetime.now,
        tracking=True,
    )
    date_day = fields.Date(
        string="Kun", compute='_compute_date_day', store=True, index=True,
    )
    bank_date = fields.Date(
        string="Bankka tushgan sana", tracking=True, copy=False,
        help="Bank ko'chirmasidagi sana. Provodkaning ikkinchi qismi shu "
             "sana bilan yoziladi.",
    )
    kassa_id = fields.Many2one(
        'agronova.kassa', string="Kassa", required=True, index=True,
        tracking=True, ondelete='restrict',
        default=lambda self: self.env['agronova.kassa']._default_kassa(),
    )
    bank_journal_id = fields.Many2one(
        'account.journal', string="Bank hisobi", required=True, tracking=True,
        domain="[('type', '=', 'bank')]",
    )
    amount = fields.Monetary(
        string="Summa", required=True, currency_field='currency_id',
        tracking=True,
    )
    currency_id = fields.Many2one(
        related='kassa_id.currency_id', string="Valyuta", store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        related='kassa_id.company_id', string="Korxona", store=True,
        readonly=True,
    )
    inkassator = fields.Char(
        string="Inkassator / olib boruvchi",
        help="Bank inkassatori yoki pulni bankka olib borgan xodim.",
    )
    hujjat_raqami = fields.Char(
        string="E'lon / kvitansiya raqami",
        help="Bankka topshirish e'loni (объявление на взнос наличными) yoki "
             "inkassator kvitansiyasining raqami.",
    )
    izoh = fields.Text(string="Izoh", tracking=True)
    rad_sabab = fields.Char(string="Rad etish sababi", readonly=True, copy=False)
    user_id = fields.Many2one(
        'res.users', string="Kim topshirdi", readonly=True, copy=False,
        default=lambda self: self.env.user,
    )
    state = fields.Selection([
        ('draft', "Qoralama"),
        ('transit', "Yo'lda"),
        ('done', "Bankka tushdi"),
        ('rad', "Rad etilgan"),
    ], string="Holat", default='draft', required=True, tracking=True,
        copy=False)

    out_harakat_id = fields.Many2one(
        'agronova.kassa.harakat', string="Kassa chiqimi", readonly=True,
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
    # COMPUTE / CONSTRAINTS
    # ------------------------------------------------------------------

    @api.depends('date')
    def _compute_date_day(self):
        for rec in self:
            rec.date_day = uz_day(rec.date)

    @api.depends('name', 'kassa_id', 'bank_journal_id')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "%s (%s → %s)" % (
                rec.name or '', rec.kassa_id.name or '?',
                rec.bank_journal_id.name or '?')

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_("Summa 0 dan katta bo'lishi kerak."))

    @api.constrains('kassa_id', 'bank_journal_id')
    def _check_valyuta(self):
        for rec in self:
            if not rec.bank_journal_id or not rec.kassa_id:
                continue
            bank_valyuta = (rec.bank_journal_id.currency_id
                            or rec.bank_journal_id.company_id.currency_id)
            if bank_valyuta != rec.kassa_id.currency_id:
                raise ValidationError(_(
                    "«%(kassa)s» kassasi %(kv)s da, «%(bank)s» hisobi esa "
                    "%(bv)s da — valyutalar mos emas.",
                    kassa=rec.kassa_id.name, kv=rec.kassa_id.currency_id.name,
                    bank=rec.bank_journal_id.name, bv=bank_valyuta.name))

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _("Yangi"):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'agronova.kassa.inkassatsiya') or '/'
        return super().create(vals_list)

    def write(self, vals):
        qoriqlanadi = {'amount', 'kassa_id', 'bank_journal_id', 'date'}
        if qoriqlanadi.intersection(vals):
            for rec in self:
                if rec.state != 'draft':
                    raise UserError(_(
                        "«%s» qoralama emas — asosiy maydonlarni "
                        "o'zgartirib bo'lmaydi.", rec.name))
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_(
                    "«%s» — topshirilgan inkassatsiya o'chirilmaydi. Rad "
                    "eting.", rec.name))
        return super().unlink()

    # ------------------------------------------------------------------
    # PROVODKA
    # ------------------------------------------------------------------

    def _transit_hisob(self):
        self.ensure_one()
        hisob = self.kassa_id._transit_account()
        if not hisob:
            raise UserError(_(
                "«Yo'ldagi pul» hisobi (5710) topilmadi. Kassa kartochkasida "
                "yoki korxona sozlamalarida ko'rsating."))
        return hisob

    def _bank_hisob(self):
        self.ensure_one()
        hisob = self.bank_journal_id.default_account_id
        if not hisob:
            raise UserError(_(
                "«%s» bank jurnalining standart hisobi tanlanmagan.",
                self.bank_journal_id.name))
        return hisob

    def _provodka(self, debet_account, kredit_account, journal, izoh, sana):
        self.ensure_one()
        if debet_account == kredit_account:
            self.message_post(body=_(
                "Provodka yozilmadi: ikkala tomon ham bitta hisobda."))
            return False
        company = self.company_id or self.env.company
        summa = self.amount
        if self.currency_id and self.currency_id != company.currency_id:
            summa = self.currency_id._convert(
                self.amount, company.currency_id, company, sana)
        umumiy = {'name': izoh, 'partner_id': False}
        debet = dict(umumiy, account_id=debet_account.id, debit=summa, credit=0.0)
        kredit = dict(umumiy, account_id=kredit_account.id, debit=0.0, credit=summa)
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

    def action_topshirish(self):
        """Qoralama → Yo'lda. Kassadan chiqim, pul tranzitga o'tadi."""
        Harakat = self.env['agronova.kassa.harakat']
        Modda = self.env['agronova.kassa.modda']
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Faqat qoralama inkassatsiya topshiriladi."))
            kassa = rec.kassa_id
            if not kassa.allow_negative and kassa.balance < rec.amount:
                raise UserError(_(
                    "«%(kassa)s» kassasida yetarli pul yo'q.\n"
                    "Kassada: %(bor)s\nInkassatsiya: %(summa)s",
                    kassa=kassa.name, bor=kassa.balance, summa=rec.amount))
            if not kassa.journal_id:
                raise UserError(_(
                    "«%s» kassasiga naqd jurnali tanlanmagan.", kassa.name))
            chiqim = Harakat._avto_yozuv(kassa, {
                'date': rec.date,
                'direction': 'out',
                'amount': rec.amount,
                'modda_id': Modda._hujjat_moddasi('inkassatsiya', 'out').id or False,
                'manba': 'inkassatsiya',
                'inkassatsiya_id': rec.id,
                'origin': rec.name,
                'izoh': _("«%(bank)s» hisobiga topshirildi. %(izoh)s",
                          bank=rec.bank_journal_id.name, izoh=rec.izoh or ''),
            })
            rec._provodka(
                rec._transit_hisob(), kassa.account_id, kassa.journal_id,
                _("%(nom)s — %(kassa)s → yo'lda (bankka)", nom=rec.name,
                  kassa=kassa.name),
                rec.date_day)
            rec.write({'out_harakat_id': chiqim.id, 'state': 'transit'})
            rec.message_post(body=_(
                "Topshirildi: %(summa)s → «%(bank)s». Bank ko'chirmasi "
                "kutilmoqda.", summa=rec.amount,
                bank=rec.bank_journal_id.name))
        return True

    def action_bank_tasdiq(self):
        """Yo'lda → Bankka tushdi. Bank hisobiga kirim provodkasi."""
        for rec in self:
            if rec.state != 'transit':
                raise UserError(_(
                    "«%s»: faqat yo'ldagi inkassatsiyani tasdiqlash mumkin.",
                    rec.name))
            sana = rec.bank_date or fields.Date.context_today(rec)
            rec._provodka(
                rec._bank_hisob(), rec._transit_hisob(), rec.bank_journal_id,
                _("%(nom)s — yo'ldan → %(bank)s", nom=rec.name,
                  bank=rec.bank_journal_id.name),
                sana)
            rec.write({'state': 'done', 'bank_date': sana})
            rec.message_post(body=_(
                "Bank tasdiqladi: %(summa)s «%(bank)s» hisobiga tushdi "
                "(%(sana)s).", summa=rec.amount,
                bank=rec.bank_journal_id.name, sana=sana))
        return True

    def action_rad(self, sabab=''):
        """Yo'lda → Rad etilgan. Pul kassaga qaytadi."""
        Harakat = self.env['agronova.kassa.harakat']
        Modda = self.env['agronova.kassa.modda']
        for rec in self:
            if rec.state != 'transit':
                raise UserError(_(
                    "«%s»: faqat yo'ldagi inkassatsiyani rad etish mumkin.",
                    rec.name))
            qaytish = Harakat._avto_yozuv(rec.kassa_id, {
                'date': fields.Datetime.now(),
                'direction': 'in',
                'amount': rec.amount,
                'modda_id': Modda._hujjat_moddasi('inkassatsiya', 'out').id or False,
                'manba': 'inkassatsiya',
                'inkassatsiya_id': rec.id,
                'origin': rec.name,
                'izoh': _("Inkassatsiya rad etildi, pul qaytdi. %s", sabab or ''),
            })
            # Qaytish yozuvi KIRIM bo'lgani uchun moddasi ham kirim bo'lishi
            # kerak — chiqim moddasi bilan yozilsa constraint yiqiladi.
            qaytish.with_context(agronova_kassa_sync=True).modda_id = \
                Modda._hujjat_moddasi('inkassatsiya', 'in').id or False
            rec._provodka(
                rec.kassa_id.account_id, rec._transit_hisob(),
                rec.kassa_id.journal_id,
                _("%(nom)s — RAD ETILDI, %(kassa)s ga qaytdi", nom=rec.name,
                  kassa=rec.kassa_id.name),
                qaytish.date_day)
            rec.write({'qaytish_harakat_id': qaytish.id, 'state': 'rad',
                       'rad_sabab': sabab or ''})
            rec.message_post(body=_(
                "Rad etildi. Sabab: %(sabab)s. %(summa)s kassaga qaytarildi.",
                sabab=sabab or _("ko'rsatilmagan"), summa=rec.amount))
        return True

    def action_rad_wizard(self):
        self.ensure_one()
        return {
            'name': _("Inkassatsiyani rad etish"),
            'type': 'ir.actions.act_window',
            'res_model': 'agronova.kassa.inkassatsiya.rad.wizard',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {'default_inkassatsiya_id': self.id},
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


class AgroNovaKassaInkassatsiyaRadWizard(models.TransientModel):
    _name = 'agronova.kassa.inkassatsiya.rad.wizard'
    _description = "Inkassatsiyani rad etish sababi"

    inkassatsiya_id = fields.Many2one(
        'agronova.kassa.inkassatsiya', string="Inkassatsiya", required=True,
        readonly=True)
    sabab = fields.Char(string="Rad etish sababi", required=True)

    def action_tasdiqlash(self):
        self.ensure_one()
        self.inkassatsiya_id.action_rad(sabab=self.sabab)
        return {'type': 'ir.actions.act_window_close'}
