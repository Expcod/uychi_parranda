# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .utils import uz_today


class AgroNovaKassa(models.Model):
    """Kassa — jismoniy naqd pul turadigan joy.

    TZ M04 «kassa kartochkasi, 3 tur»:

      * **markaziy** — bosh kassa (AgroNova);
      * **filial**   — filial kassasi (Yem zavodi, Boquv, So'yish, ...);
      * **valyuta**  — chet el valyutasidagi naqd.

    Qoldiq = boshlang'ich qoldiq + tasdiqlangan kirimlar − chiqimlar.
    Bu son har doim kassadagi REAL pulni ko'rsatishi kerak, shuning uchun
    qoralama va storno yozuvlar unga qo'shilmaydi.
    """
    _name = 'agronova.kassa'
    _description = "Kassa (naqd pul)"
    _order = 'sequence, id'
    _inherit = ['mail.thread']

    name = fields.Char(string="Kassa nomi", required=True, tracking=True)
    code = fields.Char(string="Kod")
    sequence = fields.Integer(string="Tartib", default=10)
    active = fields.Boolean(string="Faol", default=True)
    turi = fields.Selection([
        ('markaziy', "Markaziy kassa"),
        ('filial', "Filial kassasi"),
        ('valyuta', "Valyuta kassasi"),
    ], string="Kassa turi", required=True, default='filial', tracking=True,
        help="Hisobotlar va record rule'lar shu tur bo'yicha guruhlanadi.")
    company_id = fields.Many2one(
        'res.company', string="Korxona / filial", required=True,
        default=lambda self: self.env.company, tracking=True,
        help="Har filial alohida korxona (branch) sifatida yuritiladi. "
             "Kassa qaysi filialga tegishli bo'lsa, yozuvlari o'sha "
             "filialning buxgalteriyasiga tushadi.",
    )
    currency_id = fields.Many2one(
        'res.currency', string="Valyuta", required=True,
        default=lambda self: self.env.company.currency_id,
    )
    mas_ul_id = fields.Many2one(
        'hr.employee', string="Mas'ul kassir", tracking=True,
        help="Kassadagi pul kimning javobgarligida turadi.",
    )
    user_ids = fields.Many2many(
        'res.users', 'agronova_kassa_user_rel', 'kassa_id', 'user_id',
        string="Kassirlar",
        help="Shu kassada ishlaydigan foydalanuvchilar. Kassir guruhidagi "
             "xodim faqat o'ziga biriktirilgan kassani ko'radi.",
    )

    # ------------------------------------------------------------------
    # Buxgalteriya bog'lanishi
    # ------------------------------------------------------------------
    journal_id = fields.Many2one(
        'account.journal', string="Naqd jurnali",
        domain="[('type', 'in', ('cash', 'bank'))]",
        help="Shu jurnal orqali qilingan HAR QANDAY to'lov avtomatik shu "
             "kassa tarixiga tushadi (hisob-fakturadan to'langan bo'lsa ham).",
    )
    account_id = fields.Many2one(
        'account.account', string="Kassa hisobi (5010)",
        help="Provodkaning kassa tomoni. Milliy valyuta uchun 5010, "
             "valyuta kassasi uchun 5020.",
    )
    transit_account_id = fields.Many2one(
        'account.account', string="Yo'ldagi pul hisobi (5710)",
        help="Kassalararo transfer va inkassatsiya «yo'lda» bosqichida pul "
             "shu hisobda turadi. Bo'sh bo'lsa korxonaning standart "
             "«Cash in Transit» hisobi olinadi.",
    )
    buxgalteriya = fields.Boolean(
        string="Provodka yozilsin", default=True,
        help="Qo'lda kiritilgan kirim/chiqim uchun modda hisobiga qarab "
             "provodka yoziladi. Avtomatik yozuvlarda (to'lov, transfer) "
             "provodka manba hujjatda yozilgani uchun takrorlanmaydi.",
    )
    allow_negative = fields.Boolean(
        string="Manfiy qoldiqqa ruxsat", default=False,
        help="Belgilanmagan bo'lsa — kassada bor puldan ko'p chiqim "
             "qilib bo'lmaydi.",
    )
    kun_yopish_majburiy = fields.Boolean(
        string="Kunni yopish majburiy", default=True,
        help="TZ talabi: kassir smenani yopmasdan ertangi kunga yozuv "
             "kirita olmaydi. O'chirilsa — ogohlantirish beriladi, lekin "
             "bloklanmaydi.",
    )

    # ------------------------------------------------------------------
    # Qoldiq
    # ------------------------------------------------------------------
    opening_balance = fields.Monetary(
        string="Boshlang'ich qoldiq", currency_field='currency_id',
        help="Modul ishga tushirilgan kunda kassada bo'lgan real naqd pul.",
    )
    opening_date = fields.Date(
        string="Boshlang'ich sana", default=fields.Date.context_today,
    )
    balance = fields.Monetary(
        string="Kassadagi pul", compute='_compute_balance',
        currency_field='currency_id',
    )
    transit_balance = fields.Monetary(
        string="Yo'ldagi pul", compute='_compute_transit',
        currency_field='currency_id',
        help="Shu kassadan chiqib ketgan, lekin qabul qiluvchi tomon hali "
             "tasdiqlamagan summa (transfer + inkassatsiya).",
    )
    kirim_today = fields.Monetary(
        string="Bugungi kirim", compute='_compute_today',
        currency_field='currency_id',
    )
    chiqim_today = fields.Monetary(
        string="Bugungi chiqim", compute='_compute_today',
        currency_field='currency_id',
    )
    harakat_ids = fields.One2many(
        'agronova.kassa.harakat', 'kassa_id', string="Harakatlar",
    )
    harakat_count = fields.Integer(
        string="Harakatlar soni", compute='_compute_harakat_count',
    )
    note = fields.Text(string="Izoh")

    _journal_uniq = models.Constraint(
        "UNIQUE (journal_id)",
        "Bu jurnal boshqa kassaga biriktirilgan — bitta jurnal faqat bitta "
        "kassaga tegishli bo'ladi.",
    )

    # ------------------------------------------------------------------
    # COMPUTE
    # ------------------------------------------------------------------

    @api.depends('opening_balance', 'harakat_ids.signed_amount',
                 'harakat_ids.state')
    def _compute_balance(self):
        totals = self._harakat_totals([('kassa_id', 'in', self.ids)])
        for kassa in self:
            kassa.balance = (kassa.opening_balance or 0.0) + totals.get(kassa.id, 0.0)

    @api.depends('harakat_ids.signed_amount', 'harakat_ids.state',
                 'harakat_ids.date_day')
    def _compute_today(self):
        bugun = uz_today()
        kirim = self._harakat_totals([
            ('kassa_id', 'in', self.ids), ('date_day', '=', bugun),
            ('direction', '=', 'in'),
        ])
        chiqim = self._harakat_totals([
            ('kassa_id', 'in', self.ids), ('date_day', '=', bugun),
            ('direction', '=', 'out'),
        ])
        for kassa in self:
            kassa.kirim_today = kirim.get(kassa.id, 0.0)
            kassa.chiqim_today = abs(chiqim.get(kassa.id, 0.0))

    def _compute_transit(self):
        """«Yo'lda» holatidagi transfer va inkassatsiya summasi."""
        otkazma = dict(self.env['agronova.kassa.otkazma'].sudo()._read_group(
            [('from_kassa_id', 'in', self.ids), ('state', '=', 'transit')],
            ['from_kassa_id'], ['amount:sum'],
        ))
        inkas = dict(self.env['agronova.kassa.inkassatsiya'].sudo()._read_group(
            [('kassa_id', 'in', self.ids), ('state', '=', 'transit')],
            ['kassa_id'], ['amount:sum'],
        ))
        for kassa in self:
            kassa.transit_balance = (otkazma.get(kassa, 0.0)
                                     + inkas.get(kassa, 0.0))

    def _harakat_totals(self, domain):
        """{kassa_id: signed_amount yig'indisi} — faqat tasdiqlangan yozuvlar."""
        if not self.ids:
            return {}
        groups = self.env['agronova.kassa.harakat'].sudo()._read_group(
            domain + [('state', '=', 'posted')],
            ['kassa_id'], ['signed_amount:sum'],
        )
        return {kassa.id: total for kassa, total in groups}

    def _compute_harakat_count(self):
        groups = self.env['agronova.kassa.harakat'].sudo()._read_group(
            [('kassa_id', 'in', self.ids)], ['kassa_id'], ['__count'],
        )
        mapped = {kassa.id: count for kassa, count in groups}
        for kassa in self:
            kassa.harakat_count = mapped.get(kassa.id, 0)

    # ------------------------------------------------------------------
    # CONSTRAINTS
    # ------------------------------------------------------------------

    @api.constrains('currency_id', 'journal_id', 'company_id')
    def _check_jurnal(self):
        for kassa in self:
            journal = kassa.journal_id
            if not journal:
                continue
            jval = journal.currency_id or journal.company_id.currency_id
            if jval and kassa.currency_id and jval != kassa.currency_id:
                raise ValidationError(_(
                    "«%(kassa)s» kassasi valyutasi (%(kv)s) tanlangan jurnal "
                    "valyutasiga (%(jv)s) mos emas.",
                    kassa=kassa.name, kv=kassa.currency_id.name, jv=jval.name))
            # Filial (branch) o'z ota korxonasining jurnalidan ham
            # foydalanadi — Odoo branch buxgalteriyasi shunday ishlaydi.
            ruxsat = kassa.company_id.parent_ids or kassa.company_id
            if journal.company_id not in ruxsat:
                raise ValidationError(_(
                    "«%(jurnal)s» jurnali «%(jk)s» korxonasiga tegishli — "
                    "«%(kassa)s» kassasi esa «%(kk)s» da. Jurnal kassaning "
                    "o'z korxonasida yoki uning ota korxonasida bo'lishi kerak.",
                    jurnal=journal.name, jk=journal.company_id.name,
                    kassa=kassa.name, kk=kassa.company_id.name))

    @api.constrains('turi', 'currency_id', 'company_id')
    def _check_turi(self):
        for kassa in self:
            kompaniya_valyutasi = kassa.company_id.currency_id
            if kassa.turi == 'valyuta' and kassa.currency_id == kompaniya_valyutasi:
                raise ValidationError(_(
                    "«%(kassa)s» valyuta kassasi deb belgilangan, lekin "
                    "valyutasi korxona valyutasi (%(v)s) bilan bir xil.",
                    kassa=kassa.name, v=kompaniya_valyutasi.name))

    # ------------------------------------------------------------------
    # YORDAMCHI
    # ------------------------------------------------------------------

    def _transit_account(self):
        """Yo'ldagi pul hisobi (kassada ko'rsatilmagan bo'lsa — korxonadan)."""
        self.ensure_one()
        return self.transit_account_id or self.company_id.transfer_account_id

    def _jurnal_outstanding_sozlash(self):
        """Naqd jurnalning «outstanding» hisoblarini to'ldiradi.

        Odoo 19 da `account.payment` **outstanding hisobisiz umuman
        provodka yozmaydi** — to'lov `in_process` holatida osilib qoladi
        va hech qanday `account.move` yaratilmaydi. Bank uchun bu to'g'ri
        (pul yo'lda), lekin kassa uchun emas: naqd pul qo'lga tekkan
        zahoti kassada bo'ladi.

        Shuning uchun naqd jurnalda outstanding hisobi kassa hisobining
        o'ziga (5010) qo'yiladi — natijada to'lov darhol
        `Dt 5010 / Kt 4010` bo'lib tushadi va mijoz qarzi yopiladi.
        """
        for kassa in self:
            journal, hisob = kassa.journal_id, kassa.account_id
            if not journal or not hisob:
                continue
            qatorlar = (journal.inbound_payment_method_line_ids
                        | journal.outbound_payment_method_line_ids)
            bosh = qatorlar.filtered(lambda l: not l.payment_account_id)
            if bosh:
                bosh.sudo().payment_account_id = hisob.id
        return True

    @api.model_create_multi
    def create(self, vals_list):
        kassalar = super().create(vals_list)
        kassalar._jurnal_outstanding_sozlash()
        return kassalar

    def write(self, vals):
        res = super().write(vals)
        if {'journal_id', 'account_id'}.intersection(vals):
            self._jurnal_outstanding_sozlash()
        return res

    @api.model
    def _for_journal(self, journal):
        """Jurnalga biriktirilgan kassa."""
        if not journal:
            return self.browse()
        return self.sudo().search([('journal_id', '=', journal.id)], limit=1)

    @api.model
    def _default_kassa(self, company=None, currency=None):
        """Foydalanuvchiga tegishli birinchi kassa."""
        company = company or self.env.company
        currency = currency or company.currency_id
        base = [('company_id', 'in', self.env.companies.ids),
                ('currency_id', '=', currency.id)]
        oziniki = self.sudo().search(
            base + [('user_ids', 'in', self.env.user.id)], limit=1)
        return oziniki or self.sudo().search(base, limit=1)

    def _kassirmi(self, user=None):
        """Foydalanuvchi shu kassada ishlaydimi."""
        self.ensure_one()
        user = user or self.env.user
        return user in self.user_ids

    # ------------------------------------------------------------------
    # ACTIONS
    # ------------------------------------------------------------------

    def action_open_harakat(self):
        self.ensure_one()
        return {
            'name': _("«%s» harakatlari", self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'agronova.kassa.harakat',
            'views': [(False, 'list'), (False, 'form'),
                      (False, 'pivot'), (False, 'graph')],
            'domain': [('kassa_id', '=', self.id)],
            'context': {'default_kassa_id': self.id},
        }

    def action_open_kun(self):
        self.ensure_one()
        return {
            'name': _("«%s» kassa kitobi", self.name),
            'type': 'ir.actions.act_window',
            'res_model': 'agronova.kassa.kun',
            'views': [(False, 'list'), (False, 'form')],
            'domain': [('kassa_id', '=', self.id)],
            'context': {'default_kassa_id': self.id},
        }

    # ------------------------------------------------------------------
    # PANEL RPC
    # ------------------------------------------------------------------

    def _panel_data(self):
        """Panel uchun kassa kartochkasi."""
        self.ensure_one()
        return {
            'id': self.id,
            'name': self.name,
            'turi': self.turi,
            'balance': self.balance,
            'transit': self.transit_balance,
            'kirim_today': self.kirim_today,
            'chiqim_today': self.chiqim_today,
            # Transfer faqat bir xil valyutadagi kassalar orasida bo'ladi —
            # panel qabul qiluvchi ro'yxatini shu bo'yicha filtrlaydi.
            'currency_id': self.currency_id.id,
            'company_id': self.company_id.id,
            'company': self.company_id.name,
            'currency': self.currency_id.name,
            'symbol': self.currency_id.symbol or self.currency_id.name,
            'decimals': self.currency_id.decimal_places,
        }

    @api.model
    def _panel_kassalar(self):
        """Foydalanuvchi ko'radigan kassalar (kassir — faqat o'zinikini)."""
        domain = [('company_id', 'in', self.env.companies.ids)]
        if (self.env.user.has_group('agronova_kassa.group_agronova_kassir')
                and not self.env.user.has_group('agronova_kassa.group_agronova_kassa_menejer')):
            domain.append(('user_ids', 'in', self.env.user.id))
        return self.search(domain)

    @api.model
    def ui_home(self):
        """Panel ochilishi: kassalar + moddalar."""
        kassalar = self._panel_kassalar()
        moddalar = self.env['agronova.kassa.modda'].search([
            ('faqat_hujjat', '=', False),
            '|', ('company_id', '=', False),
            ('company_id', 'in', self.env.companies.ids),
        ])
        return {
            'kassalar': [k._panel_data() for k in kassalar],
            'moddalar': [{
                'id': m.id, 'name': m.name, 'direction': m.direction,
                'izoh_majburiy': m.izoh_majburiy,
                'analitik_majburiy': m.analitik_majburiy,
                'depozit': m.depozit,
                'qarz': m.qarz_yopish or m.yetkazuvchi_tolov,
            } for m in moddalar],
            'today': fields.Date.to_string(uz_today()),
            'can_close': self.env.user.has_group('agronova_kassa.group_agronova_kassir'),
            'can_reopen': self.env.user.has_group('agronova_kassa.group_agronova_kassa_menejer'),
        }

    @api.model
    def ui_day(self, kassa_id, date=None):
        """Bir kassaning bir kunlik kartochkasi: qoldiqlar + harakatlar."""
        kassa = self.browse(int(kassa_id))
        if not kassa.exists():
            raise UserError(_("Kassa topilmadi."))
        kun_sana = fields.Date.to_date(date) if date else uz_today()
        kun = self.env['agronova.kassa.kun']._kun_topish(kassa, kun_sana,
                                                      yaratish=False)
        # Storno qilinganlar ham ro'yxatda ko'rinadi (tarix yo'qolmasin —
        # ustidan chizilgan holda), lekin summaga kirmaydi.
        harakatlar = self.env['agronova.kassa.harakat'].search([
            ('kassa_id', '=', kassa.id), ('date_day', '=', kun_sana),
        ], order='date desc, id desc')
        ochilish = self.env['agronova.kassa.kun']._ochilish_qoldiq(kassa, kun_sana)
        tasdiqlangan = harakatlar.filtered(lambda h: h.state == 'posted')
        kirim = sum(tasdiqlangan.filtered(
            lambda h: h.direction == 'in').mapped('amount'))
        chiqim = sum(tasdiqlangan.filtered(
            lambda h: h.direction == 'out').mapped('amount'))
        return {
            'kassa': kassa._panel_data(),
            'date': fields.Date.to_string(kun_sana),
            'opening': ochilish,
            'kirim': kirim,
            'chiqim': chiqim,
            'closing': ochilish + kirim - chiqim,
            'kun': {
                'id': kun.id, 'state': kun.state,
                'sanoq': kun.sanoq, 'farq': kun.farq, 'note': kun.note or '',
            } if kun else None,
            'lines': [h._panel_line() for h in harakatlar],
        }

    @api.model
    def ui_create_harakat(self, vals):
        """Panel formasidan kirim/chiqim yozish."""
        harakat = self.env['agronova.kassa.harakat'].create({
            'kassa_id': int(vals['kassa_id']),
            'direction': vals['direction'],
            'amount': float(vals.get('amount') or 0.0),
            'modda_id': int(vals['modda_id']) if vals.get('modda_id') else False,
            'partner_id': int(vals['partner_id']) if vals.get('partner_id') else False,
            'employee_id': int(vals['employee_id']) if vals.get('employee_id') else False,
            'depozit_id': int(vals['depozit_id']) if vals.get('depozit_id') else False,
            'analytic_distribution': vals.get('analytic_distribution') or False,
            'izoh': vals.get('izoh') or '',
            'manba': 'qol',
            'state': 'posted',
        })
        return {
            'name': harakat.name,
            'harakat_id': harakat.id,
            'day': self.ui_day(harakat.kassa_id.id,
                               fields.Date.to_string(harakat.date_day)),
        }

    @api.model
    def ui_create_otkazma(self, vals):
        """Panel formasidan kassalararo transfer (darhol «yo'lda» holatiga)."""
        otkazma = self.env['agronova.kassa.otkazma'].create({
            'from_kassa_id': int(vals['from_kassa_id']),
            'to_kassa_id': int(vals['to_kassa_id']),
            'amount': float(vals.get('amount') or 0.0),
            'olib_boruvchi_id': (int(vals['olib_boruvchi_id'])
                                 if vals.get('olib_boruvchi_id') else False),
            'izoh': vals.get('izoh') or '',
        })
        otkazma.action_jonatish()
        return {'id': otkazma.id, 'name': otkazma.name}

    @api.model
    def ui_storno_harakat(self, harakat_id, sabab=''):
        harakat = self.env['agronova.kassa.harakat'].browse(int(harakat_id))
        harakat.action_storno(sabab=sabab)
        return self.ui_day(harakat.kassa_id.id,
                           fields.Date.to_string(harakat.date_day))

    @api.model
    def ui_close_day(self, kassa_id, date, sanoq=0.0, note=''):
        kassa = self.browse(int(kassa_id))
        kun_sana = fields.Date.to_date(date)
        kun = self.env['agronova.kassa.kun']._kun_topish(kassa, kun_sana)
        kun.write({'sanoq': float(sanoq or 0.0), 'note': note or ''})
        kun.action_yopish()
        return self.ui_day(kassa.id, date)

    @api.model
    def ui_kutilayotgan(self):
        """Shu foydalanuvchi tasdiqlashi kerak bo'lgan «yo'ldagi» hujjatlar."""
        kassalar = self._panel_kassalar()
        otkazmalar = self.env['agronova.kassa.otkazma'].search([
            ('to_kassa_id', 'in', kassalar.ids), ('state', '=', 'transit'),
        ])
        return [{
            'id': o.id,
            'name': o.name,
            'from': o.from_kassa_id.name,
            'to': o.to_kassa_id.name,
            'to_id': o.to_kassa_id.id,
            'amount': o.amount,
            'symbol': o.currency_id.symbol or o.currency_id.name,
            'izoh': o.izoh or '',
            'olib_boruvchi': o.olib_boruvchi_id.display_name or '',
        } for o in otkazmalar]

    @api.model
    def ui_qabul_qilish(self, otkazma_id, sanoq=None):
        otkazma = self.env['agronova.kassa.otkazma'].browse(int(otkazma_id))
        otkazma.action_qabul(sanoq=sanoq)
        return {'ok': True}

    @api.model
    def ui_rad_etish(self, otkazma_id, sabab=''):
        otkazma = self.env['agronova.kassa.otkazma'].browse(int(otkazma_id))
        otkazma.action_rad(sabab=sabab)
        return {'ok': True}

    @api.model
    def ui_search_partners(self, term, limit=12):
        domain = [('name', 'ilike', term)] if term else []
        partners = self.env['res.partner'].search(domain, limit=limit)
        return [{'id': p.id, 'name': p.display_name} for p in partners]

    @api.model
    def ui_search_employees(self, term, limit=12):
        domain = [('name', 'ilike', term)] if term else []
        employees = self.env['hr.employee'].search(domain, limit=limit)
        return [{'id': e.id, 'name': e.display_name} for e in employees]

    @api.model
    def ui_search_depozit(self, term, limit=12):
        domain = [('name', 'ilike', term)] if term else []
        depozitlar = self.env['agronova.depozit'].search(domain, limit=limit)
        return [{'id': d.id, 'name': d.display_name, 'balans': d.balans}
                for d in depozitlar]

    @api.model
    def ui_search_analytic(self, term, limit=15):
        domain = [('name', 'ilike', term)] if term else []
        hisoblar = self.env['account.analytic.account'].search(domain, limit=limit)
        return [{'id': a.id, 'name': a.display_name,
                 'plan': a.plan_id.name or ''} for a in hisoblar]
