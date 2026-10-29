# -*- coding: utf-8 -*-
"""Inkubatsiya partiyasi (TZ 4-band).

Bo'limning markaziy obyekti. Barcha xarajat shu partiyaning analitik
hisobiga yig'iladi, jo'ja tannarxi ham shundan chiqadi.

Uch bosqich:

* **Qoralama** — tuxum qabul qilinmoqda, partiya to'ldirilyapti;
* **Inkubatsiyada** — tuxum inkubatorga qo'yilgan, kutilmoqda;
* **Yakunlangan** — jo'ja ochilgan, natija kiritilgan.

Yakunlangandan keyin tannarx **qotadi**: yangi xarajat qo'shilsa
o'tmishdagi jo'ja tannarxi o'zgarib ketardi va Boquvga berilgan narx
bilan hisobot bir-biriga to'g'ri kelmay qolardi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Tovuq tuxumi uchun standart inkubatsiya muddati. Boshqa parranda
# qo'shilsa partiyada qo'lda o'zgartiriladi.
INKUBATSIYA_KUN = 21


class AgroNovaInkPartiya(models.Model):
    _name = 'agronova.ink.partiya'
    _description = "Inkubatsiya partiyasi"
    _inherit = ['agronova.analitik.mixin', 'agronova.tannarx.qulf.mixin',
                'mail.thread', 'mail.activity.mixin']
    _order = 'sana_qoyilgan desc, id desc'
    _rec_names_search = ['name', 'inkubator_id.kod']

    _agronova_analytic_plan_name = "Inkubatsiya partiyasi"
    _agronova_tannarx_fields = ('tannarx_1_joja',)

    name = fields.Char("Partiya raqami", default=lambda s: _("Yangi"),
                       copy=False, readonly=True, index=True)
    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)
    inkubator_id = fields.Many2one(
        'agronova.ink.inkubator', string="Inkubator", tracking=True,
        domain="[('company_id', '=', company_id)]")
    masul_id = fields.Many2one('hr.employee', string="Mas'ul xodim",
                               tracking=True)

    # --- sanalar
    sana_qoyilgan = fields.Date(
        "Inkubatsiyaga qo'yilgan sana", tracking=True,
        help="Tugma bosilganda avtomat qo'yiladi.")
    inkubatsiya_kun = fields.Integer(
        "Inkubatsiya muddati (kun)", default=INKUBATSIYA_KUN, required=True)
    sana_kutilayotgan = fields.Date(
        "Kutilayotgan ochilish sanasi", compute='_compute_sana_kutilayotgan',
        store=True)
    sana_ochilgan = fields.Date("Haqiqiy ochilish sanasi",
                                compute='_compute_natija', store=True)
    kechikish_kun = fields.Integer("Kechikish (kun)", compute='_compute_natija',
                                   store=True,
                                   help="Haqiqiy ochilish kutilganidan necha "
                                        "kun kech bo'lgani. Manfiy — erta.")

    holat = fields.Selection([
        ('draft', "Qoralama"),
        ('inkubatsiyada', "Inkubatsiyada"),
        ('done', "Yakunlangan"),
    ], string="Holati", default='draft', required=True, tracking=True,
        copy=False)

    # --- tuxum
    qabul_ids = fields.One2many('agronova.ink.qabul', 'partiya_id',
                                string="Tuxum qabullari")
    tuxum_dona = fields.Integer("Inkubatsiyaga qo'yilgan tuxum (dona)",
                                compute='_compute_tuxum', store=True)
    tuxum_qiymat = fields.Monetary("Tuxum qiymati", compute='_compute_tuxum',
                                   store=True)

    # --- natija
    ochilish_ids = fields.One2many('agronova.ink.ochilish', 'partiya_id',
                                   string="Ochilish hujjatlari")
    ochilgan_joja = fields.Integer("Ochilgan jo'ja (dona)",
                                   compute='_compute_natija', store=True)
    ochilmagan_tuxum = fields.Integer("Ochilmagan tuxum (dona)",
                                      compute='_compute_natija', store=True)
    nobud_son = fields.Integer("Nobud jo'ja (dona)", compute='_compute_natija',
                               store=True)
    brak_son = fields.Integer("Brak jo'ja (dona)", compute='_compute_natija',
                              store=True)
    sof_joja = fields.Integer(
        "Yaroqli jo'ja (dona)", compute='_compute_natija', store=True,
        help="Ochilgan minus nobud va brak — omborga kiradigani.")

    # --- ko'rsatkichlar (TZ 5-band)
    ochilish_foiz = fields.Float("Ochilish foizi (%)", compute='_compute_natija',
                                 store=True)
    nobud_foiz = fields.Float("Nobudgarchilik (%)", compute='_compute_natija',
                              store=True)
    brak_foiz = fields.Float("Brak (%)", compute='_compute_natija', store=True)
    koeffitsient = fields.Float(
        "1 tuxumdan jo'ja koeffitsienti", compute='_compute_natija', store=True,
        digits=(12, 4),
        help="Yaroqli jo'ja / qo'yilgan tuxum. 1 ga qancha yaqin — shuncha "
             "yaxshi.")

    # --- moliya
    jami_xarajat = fields.Monetary("Jami xarajat", compute='_compute_moliya')
    jami_daromad = fields.Monetary("Jami daromad", compute='_compute_moliya')
    foyda = fields.Monetary("Foyda / zarar", compute='_compute_moliya')
    tannarx_1_joja = fields.Monetary(
        "1 dona jo'ja tannarxi", readonly=True, copy=False,
        help="Ishlab chiqarish xarajati / yaroqli jo'ja. Qo'lda kiritilmaydi.")
    tannarx_qotgan = fields.Boolean(
        "Tannarx qotgan", default=False, copy=False, readonly=True,
        help="Partiya yakunlangach tannarx o'zgarmaydi.")

    # --- qoldiq
    sotuv_ids = fields.One2many('agronova.ink.ichki_sotuv', 'partiya_id',
                                string="Ichki berishlar")
    berilgan_joja = fields.Integer("Berilgan jo'ja (dona)",
                                   compute='_compute_qoldiq', store=True)
    qoldiq_joja = fields.Integer("Ombordagi qoldiq (dona)",
                                 compute='_compute_qoldiq', store=True)

    izoh = fields.Text("Izoh")

    _tuxum_musbat = models.Constraint(
        'CHECK (inkubatsiya_kun > 0)',
        "Inkubatsiya muddati noldan katta bo'lishi kerak.")

    # ------------------------------------------------------------- compute
    @api.depends('sana_qoyilgan', 'inkubatsiya_kun')
    def _compute_sana_kutilayotgan(self):
        for p in self:
            if p.sana_qoyilgan:
                p.sana_kutilayotgan = fields.Date.add(
                    p.sana_qoyilgan, days=p.inkubatsiya_kun)
            else:
                p.sana_kutilayotgan = False

    @api.depends('qabul_ids.dona', 'qabul_ids.qiymat', 'qabul_ids.holat')
    def _compute_tuxum(self):
        for p in self:
            qabul = p.qabul_ids.filtered(lambda q: q.holat == 'done')
            p.tuxum_dona = sum(qabul.mapped('dona'))
            p.tuxum_qiymat = sum(qabul.mapped('qiymat'))

    @api.depends('ochilish_ids.holat', 'ochilish_ids.ochilgan_joja',
                 'ochilish_ids.ochilmagan_tuxum', 'ochilish_ids.nobud_son',
                 'ochilish_ids.brak_son', 'ochilish_ids.sana', 'tuxum_dona',
                 'sana_kutilayotgan')
    def _compute_natija(self):
        for p in self:
            done = p.ochilish_ids.filtered(lambda o: o.holat == 'done')
            p.ochilgan_joja = sum(done.mapped('ochilgan_joja'))
            p.ochilmagan_tuxum = sum(done.mapped('ochilmagan_tuxum'))
            p.nobud_son = sum(done.mapped('nobud_son'))
            p.brak_son = sum(done.mapped('brak_son'))
            p.sof_joja = p.ochilgan_joja - p.nobud_son - p.brak_son
            sanalar = done.mapped('sana')
            p.sana_ochilgan = max(sanalar) if sanalar else False
            p.kechikish_kun = (
                (p.sana_ochilgan - p.sana_kutilayotgan).days
                if p.sana_ochilgan and p.sana_kutilayotgan else 0)

            baza = p.tuxum_dona or 0
            p.ochilish_foiz = (p.ochilgan_joja / baza * 100.0) if baza else 0.0
            # Nobud va brak ochilgan jo'jadan hisoblanadi, tuxumdan emas:
            # ochilmagan tuxum nobud jo'ja emas, u alohida ko'rsatkich.
            och = p.ochilgan_joja or 0
            p.nobud_foiz = (p.nobud_son / och * 100.0) if och else 0.0
            p.brak_foiz = (p.brak_son / och * 100.0) if och else 0.0
            p.koeffitsient = (p.sof_joja / baza) if baza else 0.0

    # Ichki berishga `sotuv_ids` orqali bog'lanamiz: shunda hujjat
    # tasdiqlangan zahoti qoldiq o'zi yangilanadi. Modelni to'g'ridan-to'g'ri
    # qidirsak, ORM bog'liqlikni ko'rmaydi va qoldiq eskirib qoladi.
    @api.depends('sotuv_ids.holat', 'sotuv_ids.dona', 'sof_joja')
    def _compute_qoldiq(self):
        for p in self:
            berilgan = p.sotuv_ids.filtered(lambda s: s.holat == 'done')
            p.berilgan_joja = sum(berilgan.mapped('dona'))
            p.qoldiq_joja = p.sof_joja - p.berilgan_joja

    def _compute_moliya(self):
        for p in self:
            xarajat = p._agronova_analytic_amount(sign='cost')
            daromad = p._agronova_analytic_amount(sign='income')
            p.jami_xarajat = xarajat
            p.jami_daromad = daromad
            p.foyda = daromad - xarajat

    def _agronova_analytic_vals(self):
        vals = super()._agronova_analytic_vals()
        vals['name'] = (self.name if self.name != _("Yangi")
                        else self.display_name)
        return vals

    @api.depends('name', 'inkubator_id')
    def _compute_display_name(self):
        for p in self:
            qism = [p.name or ""]
            if p.inkubator_id:
                qism.append(p.inkubator_id.kod)
            p.display_name = " · ".join(x for x in qism if x)

    # ------------------------------------------------------------ yaratish
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _("Yangi"):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'agronova.ink.partiya') or _("Yangi")
        return super().create(vals_list)

    # -------------------------------------------------------------- tannarx
    def _tannarxni_hisoblash(self):
        """1 dona jo'ja tannarxi = ishlab chiqarish xarajati / yaroqli jo'ja.

        Maxraj **yaroqli** jo'ja: nobud va brak jo'jaga sarflangan xarajat
        ham qolganlarining tannarxiga tushadi — aks holda bo'lim
        nobudgarchilikni tannarxda ko'rmay qoladi.
        """
        for p in self:
            if p.tannarx_qotgan:
                continue
            xarajat = p._agronova_analytic_amount(sign='cost', faqat_tannarx=True)
            p._tannarx_yozish().tannarx_1_joja = (
                xarajat / p.sof_joja if p.sof_joja else 0.0)
        return True

    # --------------------------------------------------------------- qulf
    def _tekshir_ochiq(self, amal=None):
        for p in self:
            if p.holat == 'done':
                raise UserError(_(
                    "«%(nom)s» partiyasi yakunlangan — unga yangi xarajat "
                    "qo'shilmaydi.%(amal)s",
                    nom=p.name, amal=(_(" (%s)", amal) if amal else "")))
        return True

    def _agronova_post_analytic(self, *args, **kwargs):
        """Yakunlangandan keyin xarajat qo'shilmaydi, sotuv esa davom etadi."""
        amount = kwargs.get('amount')
        if amount is None and len(args) >= 2:
            amount = args[1]
        if kwargs.get('tannarxga', True) and (amount or 0.0) < 0:
            self._tekshir_ochiq()
        return super()._agronova_post_analytic(*args, **kwargs)

    # -------------------------------------------------------------- holat
    def action_inkubatsiyaga(self):
        """Tuxumni inkubatorga qo'yadi."""
        for p in self:
            if p.holat != 'draft':
                raise UserError(_("Faqat qoralama partiya qo'yiladi."))
            qoralama = p.qabul_ids.filtered(lambda q: q.holat == 'draft')
            if qoralama:
                raise UserError(_(
                    "«%s» partiyasida tasdiqlanmagan tuxum qabuli bor.",
                    p.name))
            if not p.tuxum_dona:
                raise UserError(_(
                    "«%s» partiyasida tuxum yo'q.", p.name))
            if not p.inkubator_id:
                raise UserError(_(
                    "«%s» partiyasida inkubator tanlanmagan.", p.name))
            if p.inkubator_id.holat == 'tamir':
                raise UserError(_(
                    "«%s» inkubatori ta'mirda.", p.inkubator_id.display_name))
            bosh = p.inkubator_id.bosh_joy()
            if p.tuxum_dona > bosh:
                raise UserError(_(
                    "«%(ink)s» inkubatorida %(bosh)s dona joy bor, "
                    "%(kerak)s dona sig'maydi.",
                    ink=p.inkubator_id.display_name, bosh=bosh,
                    kerak=p.tuxum_dona))
            p.sana_qoyilgan = p.sana_qoyilgan or fields.Date.context_today(p)
            p.holat = 'inkubatsiyada'
            p.message_post(body=_(
                "%(dona)s dona tuxum «%(ink)s» inkubatoriga qo'yildi. "
                "Kutilayotgan ochilish: %(sana)s.",
                dona=p.tuxum_dona, ink=p.inkubator_id.display_name,
                sana=p.sana_kutilayotgan))
        return True

    def action_yakunlash(self):
        for p in self:
            if p.holat != 'inkubatsiyada':
                raise UserError(_(
                    "Faqat inkubatsiyadagi partiya yakunlanadi."))
            qoralama = p.ochilish_ids.filtered(lambda o: o.holat == 'draft')
            if qoralama:
                raise UserError(_(
                    "«%s» partiyasida tasdiqlanmagan ochilish hujjati bor.",
                    p.name))
            if not p.ochilish_ids.filtered(lambda o: o.holat == 'done'):
                raise UserError(_(
                    "«%s» partiyasida ochilish hujjati yo'q — natija "
                    "kiritilmagan.", p.name))
            p._tannarxni_hisoblash()
            p.holat = 'done'
            p.tannarx_qotgan = True
            p.message_post(body=_(
                "Partiya yakunlandi. Ochilish %(foiz).1f%%, yaroqli jo'ja "
                "%(joja)s dona, 1 dona tannarxi %(tannarx).2f so'm.",
                foiz=p.ochilish_foiz, joja=p.sof_joja,
                tannarx=p.tannarx_1_joja))
        return True

    def action_qayta_ochish(self):
        for p in self:
            if p.holat != 'done':
                raise UserError(_("Faqat yakunlangan partiya qayta ochiladi."))
            p.holat = 'inkubatsiyada'
            p.tannarx_qotgan = False
            p.message_post(body=_("Partiya qayta ochildi — tannarx yangilanadi."))
        return True

    def action_open_qabullar(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Tuxum qabullari"),
            'res_model': 'agronova.ink.qabul',
            'view_mode': 'list,form',
            'domain': [('partiya_id', '=', self.id)],
            'context': {'default_partiya_id': self.id,
                        'default_company_id': self.company_id.id},
        }

    def action_open_ochilish(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Ochilish hujjatlari"),
            'res_model': 'agronova.ink.ochilish',
            'view_mode': 'list,form',
            'domain': [('partiya_id', '=', self.id)],
            'context': {'default_partiya_id': self.id},
        }
