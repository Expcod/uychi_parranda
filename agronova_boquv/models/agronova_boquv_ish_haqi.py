# -*- coding: utf-8 -*-
"""Ish haqini binolarga taqsimlash (TZ 17-band).

Oylik hujjat: davr tanlanadi, xodimlar yig'iladi, har birining ish haqi
binolarga bo'linadi va analitik qatorlar yoziladi.

Yakuniy TZ dagi qoidalar:

* **binoga biriktirilgan xodim** (operator) — ish haqi to'g'ridan-to'g'ri
  o'sha binoning faol partiyalariga tushadi;
* **biriktirilmagan xodim** (brigadir, qorovul, oshpaz) — **m² bo'yicha**
  taqsimlanadi;
* **filialga biriktirilgan** xodim faqat o'sha filial binolariga bo'linadi;
* **oy o'rtasida bino o'zgarsa** — `agronova.boquv.xodim.bino.tarix` yozuvlari
  bo'yicha **kunlarga bo'linadi**;
* **veterinar** (`agronova_boquv_faqat_aktiv`) mehnati faqat *aktiv* binoga
  tushadi — dizinfeksiyadagi binoda jo'ja yo'q.

Ish haqi summasi `_xodim_summa()` dan olinadi: Payroll o'rnatilgan bo'lsa
tasdiqlangan hisobvaraqdan, aks holda shartnoma oyligidan. Payrollga qattiq
bog'lanish yo'q — modul u o'rnatilmagan bazada ham ishlaydi.
"""
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

USUL = [
    ('togridan', "To'g'ridan-to'g'ri (biriktirilgan bino)"),
    ('m2', "m² bo'yicha (biriktirilmagan)"),
]


class AgroNovaBoquvIshHaqi(models.Model):
    _name = 'agronova.boquv.ish_haqi'
    _description = "Boquv — ish haqi taqsimoti"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'davr_boshi desc, id desc'

    name = fields.Char(
        "Hujjat", default=lambda self: _("Yangi"), copy=False, readonly=True,
        index=True)
    davr_boshi = fields.Date(
        "Davr boshi", required=True, tracking=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1))
    davr_oxiri = fields.Date(
        "Davr oxiri", required=True, tracking=True,
        default=lambda self: (
            fields.Date.context_today(self).replace(day=1)
            + relativedelta(months=1, days=-1)))
    filial_id = fields.Many2one(
        'agronova.boquv.filial', string="Filial", tracking=True,
        help="Bo'sh bo'lsa — barcha filiallar bo'yicha taqsimlanadi.")
    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)
    department_ids = fields.Many2many(
        'hr.department', string="Bo'limlar",
        help="Bo'sh bo'lsa — faqat binoga yoki filialga biriktirilgan "
             "xodimlar olinadi. To'ldirilsa, bu bo'limlarning boshqa "
             "xodimlari ham m² bo'yicha taqsimlanadi.")
    qator_ids = fields.One2many(
        'agronova.boquv.ish_haqi.qator', 'ish_haqi_id', string="Qatorlar",
        copy=False)
    jami_summa = fields.Monetary(
        "Jami taqsimlangan", compute='_compute_jami', store=True)
    xodim_soni = fields.Integer("Xodim soni", compute='_compute_jami', store=True)
    holat = fields.Selection(
        [('draft', "Qoralama"), ('posted', "Tasdiqlangan"), ('storno', "Storno")],
        default='draft', tracking=True, string="Holati", copy=False)
    analytic_line_ids = fields.Many2many(
        'account.analytic.line', string="Analitik qatorlar", copy=False,
        readonly=True)
    izoh = fields.Text("Izoh")

    _davr_togri = models.Constraint(
        'CHECK (davr_oxiri >= davr_boshi)',
        "Davr oxiri boshidan oldin bo'lishi mumkin emas.")

    @api.depends('qator_ids.ulush', 'qator_ids.employee_id')
    def _compute_jami(self):
        for rec in self:
            rec.jami_summa = sum(rec.qator_ids.mapped('ulush'))
            rec.xodim_soni = len(rec.qator_ids.mapped('employee_id'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _("Yangi"):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'agronova.boquv.ish_haqi') or _("Yangi")
        return super().create(vals_list)

    def write(self, vals):
        # Tasdiqlangan taqsimotni tahrirlash tannarxni buzadi.
        if not set(vals) <= {'holat', 'analytic_line_ids', 'izoh',
                             'message_follower_ids', 'message_ids',
                             'activity_ids'}:
            for rec in self:
                if rec.holat != 'draft':
                    raise UserError(_(
                        "«%s» taqsimoti tasdiqlangan — tahrirlanmaydi. "
                        "Avval storno qiling.", rec.display_name))
        return super().write(vals)

    # ------------------------------------------------------------ xodimlar
    def _xodimlar(self):
        """Taqsimotga kiradigan xodimlar.

        **Korxona bo'yicha qat'iy filtr yo'q.** Loyihada xodimlar odatda bosh
        korxonada (`AgroNova`) yuritiladi, Boquv esa alohida
        korxona. `company_id = Boquv` deb qidirsak birorta xodim topilmaydi.
        Shuning uchun bosh korxona xodimlari ham qabul qilinadi — ular
        Boquv binosiga biriktirilgani ish haqi shu bo'limga tegishli
        ekanining o'zi dalili.
        """
        self.ensure_one()
        korxonalar = [self.company_id.id]
        bosh = self.company_id.parent_id
        while bosh:
            korxonalar.append(bosh.id)
            bosh = bosh.parent_id
        domain = ['|', ('company_id', 'in', korxonalar),
                       ('company_id', '=', False)]
        shartlar = ['|', ('agronova_boquv_bino_id', '!=', False),
                         ('agronova_boquv_filial_id', '!=', False)]
        if self.department_ids:
            shartlar = ['|'] + shartlar + [
                ('department_id', 'in', self.department_ids.ids)]
        if self.filial_id:
            # Filial ko'rsatilgan — boshqa filial xodimlari kirmasin.
            domain += ['|', ('agronova_boquv_filial_id', '=', self.filial_id.id),
                            ('agronova_boquv_bino_id.filial_id', '=', self.filial_id.id)]
        return self.env['hr.employee'].sudo().search(domain + shartlar)

    def _xodim_summa(self, employee):
        """Xodimning shu davrdagi ish haqi xarajati.

        1. `agronova_ish_haqi` moduli bo'lsa tasdiqlangan davr qatoridan (hisoblangan + bonus);
        2. Payroll o'rnatilgan bo'lsa tasdiqlangan hisobvaraqdan;
        3. Aks holda xodim shartnoma oyligidan.
        """
        self.ensure_one()
        Qator = self.env.get('agronova.ish_haqi.davr.qator')
        if Qator is not None:
            qatorlar = Qator.sudo().search([
                ('employee_id', '=', employee.id),
                ('davr_id.holat', '=', 'posted'),
                ('davr_id.davr_boshi', '<=', self.davr_oxiri),
                ('davr_id.davr_oxiri', '>=', self.davr_boshi),
            ])
            # Bonus ham tannarxga kiradi — u ham ishlagani uchun to'lanadi.
            jami = sum(q.hisoblangan + q.bonus for q in qatorlar)
            if jami:
                return jami
        Payslip = self.env.get('hr.payslip')
        if Payslip is not None:
            slips = Payslip.sudo().search([
                ('employee_id', '=', employee.id),
                ('state', 'in', ('done', 'paid')),
                ('date_from', '<=', self.davr_oxiri),
                ('date_to', '>=', self.davr_boshi),
            ])
            if slips:
                jami = sum(slips.mapped(
                    'net_wage' if 'net_wage' in slips._fields else 'basic_wage'))
                if jami:
                    return jami
        # Payroll yo'q yoki hisobvaraq yaratilmagan — shartnoma oyligi
        return employee.sudo().version_id.wage or 0.0

    def _binolar(self, employee=None):
        """Xarajat tushadigan binolar.

        Qamrov qoidasi (yakuniy TZ): veterinar kabi xodimlarning mehnati
        faqat **aktiv** binoga tushadi, qolganlariniki **aktiv va
        dizinfeksiyadagi** binolarga. «No aktiv» binoga hech qachon
        tushmaydi.
        """
        self.ensure_one()
        domain = [('company_id', '=', self.company_id.id)]
        faqat_aktiv = bool(employee and employee.agronova_boquv_faqat_aktiv)
        domain.append(('holat', '=', 'aktiv') if faqat_aktiv
                      else ('holat', 'in', ('aktiv', 'dizinfeksiya')))
        # Xodim filialga biriktirilgan bo'lsa — faqat o'sha filial binolari.
        filial = (employee.agronova_boquv_filial_id if employee else False) \
            or self.filial_id
        if filial:
            domain.append(('filial_id', '=', filial.id))
        return self.env['agronova.boquv.bino'].sudo().search(domain)

    def _davr_kunlari(self):
        return (self.davr_oxiri - self.davr_boshi).days + 1

    # ------------------------------------------------------------- yig'ish
    def action_yigish(self):
        """Xodimlarni yig'ib, ish haqini binolarga bo'ladi."""
        for rec in self:
            if rec.holat != 'draft':
                raise UserError(_(
                    "«%s» tasdiqlangan — qayta yig'ib bo'lmaydi.",
                    rec.display_name))
            rec.qator_ids.unlink()
            rec.qator_ids = [(0, 0, v) for v in rec._qator_vals()]
        return True

    def _qator_vals(self):
        """Barcha xodimlar uchun qator qiymatlari."""
        self.ensure_one()
        jami_kun = self._davr_kunlari()
        vals = []
        for emp in self._xodimlar():
            summa = self._xodim_summa(emp)
            if not summa:
                continue
            binolar = self._binolar(emp)
            if not binolar:
                # Xodim biriktirilgan filialda aktiv bino yo'q — ish haqi
                # taqsimlanmaydi, xabar chatterga yoziladi.
                continue
            kunlik = summa / jami_kun
            biriktirilgan = 0

            for tarix, kun in self._tarix_kunlari(emp):
                if tarix.bino_id.holat == 'no_aktiv':
                    continue    # bo'sh binoga xarajat tushmaydi
                biriktirilgan += kun
                vals.append({
                    'employee_id': emp.id,
                    'bino_id': tarix.bino_id.id,
                    'kunlar': kun,
                    'jami_kun': jami_kun,
                    'oylik_summa': summa,
                    'usul': 'togridan',
                    'ulush': self.currency_id.round(kunlik * kun),
                })

            qolgan_kun = jami_kun - biriktirilgan
            if qolgan_kun > 0:
                # Biriktirilmagan kunlar — m² bo'yicha binolarga
                qoldiq = self.currency_id.round(kunlik * qolgan_kun)
                for bino, ulush in self._m2_bolish(binolar, qoldiq):
                    if not ulush:
                        continue
                    vals.append({
                        'employee_id': emp.id,
                        'bino_id': bino.id,
                        'kunlar': qolgan_kun,
                        'jami_kun': jami_kun,
                        'oylik_summa': summa,
                        'usul': 'm2',
                        'ulush': ulush,
                    })
        return vals

    def _tarix_kunlari(self, employee):
        """`[(tarix, kunlar), ...]` — xodim davr ichida qaysi binoda necha kun.

        Tarix yozuvlari bir-birining ustiga tushib qolsa ham jami kun davr
        uzunligidan oshmaydi.
        """
        self.ensure_one()
        jami_kun = self._davr_kunlari()
        Tarix = self.env['agronova.boquv.xodim.bino.tarix'].sudo()
        tarix = Tarix.search([
            ('employee_id', '=', employee.id),
            ('boshlanish_sana', '<=', self.davr_oxiri),
            '|', ('tugash_sana', '=', False),
                 ('tugash_sana', '>=', self.davr_boshi),
        ], order='boshlanish_sana')

        if not tarix and employee.agronova_boquv_bino_id:
            # Tarix yuritilmagan (modul o'rnatilishidan oldin biriktirilgan) —
            # butun davr joriy binoga tegishli deb hisoblaymiz.
            soxta = Tarix.new({
                'employee_id': employee.id,
                'bino_id': employee.agronova_boquv_bino_id.id,
                'boshlanish_sana': self.davr_boshi,
                'tugash_sana': self.davr_oxiri,
            })
            return [(soxta, jami_kun)]

        natija, yigilgan = [], 0
        for t in tarix:
            kun = min(t.kunlar(self.davr_boshi, self.davr_oxiri),
                      jami_kun - yigilgan)
            if kun <= 0:
                continue
            yigilgan += kun
            natija.append((t, kun))
        return natija

    def _m2_bolish(self, binolar, summa):
        """Summani m² bo'yicha bo'ladi; maydon kiritilmagan bo'lsa teng."""
        self.ensure_one()
        ogirlik = [b.maydoni or 0.0 for b in binolar]
        if not sum(ogirlik):
            ogirlik = [1.0] * len(binolar)
        jami = sum(ogirlik)
        natija, taqsimlangan = [], 0.0
        for idx, (bino, w) in enumerate(zip(binolar, ogirlik)):
            if idx == len(binolar) - 1:
                ulush = summa - taqsimlangan       # yaxlitlash farqi oxirgisiga
            else:
                ulush = self.currency_id.round(summa * w / jami)
                taqsimlangan += ulush
            natija.append((bino, ulush))
        return natija

    # --------------------------------------------------------------- holat
    def action_tasdiqlash(self):
        for rec in self:
            if rec.holat != 'draft':
                raise UserError(_("«%s» allaqachon tasdiqlangan.",
                                  rec.display_name))
            if not rec.qator_ids:
                raise UserError(_(
                    "«%s» hujjatida qator yo'q — avval «Yig'ish» tugmasini "
                    "bosing.", rec.display_name))
            Line = rec.env['account.analytic.line']
            lines = Line
            # `employee_id` analitik qatorda hr_timesheet bilan keladi —
            # o'rnatilmagan bazada bo'lmasligi mumkin.
            xodim_maydoni = 'employee_id' in Line._fields
            for q in rec.qator_ids:
                if not q.ulush:
                    continue
                extra = {'company_id': rec.company_id.id}
                if xodim_maydoni:
                    extra['employee_id'] = q.employee_id.id
                lines |= q._obyekt()._agronova_post_analytic(
                    name=_("Ish haqi: %(xodim)s (%(kun)s kun)",
                           xodim=q.employee_id.name, kun=q.kunlar),
                    amount=-abs(q.ulush),          # xarajat — manfiy
                    date=rec.davr_oxiri,
                    extra=extra,
                )
            rec.analytic_line_ids = [(6, 0, lines.ids)]
            rec.holat = 'posted'
            rec.message_post(body=_(
                "Ish haqi taqsimlandi: %(xodim)s xodim, jami %(summa)s.",
                xodim=rec.xodim_soni, summa=rec.jami_summa))
        return True

    def action_storno(self):
        """Yozuvlarni o'chirmaydi — teskari analitik qator yozadi."""
        for rec in self:
            if rec.holat != 'posted':
                raise UserError(_("Faqat tasdiqlangan taqsimot storno qilinadi."))
            bugun = fields.Date.context_today(rec)
            for line in rec.analytic_line_ids:
                line.copy({
                    'name': _("STORNO: %s", line.name),
                    'amount': -line.amount,
                    'date': bugun,
                })
            rec.holat = 'storno'
            rec.message_post(body=_("Taqsimot storno qilindi."))
        return True

    def action_qoralamaga(self):
        for rec in self:
            if rec.holat != 'storno':
                raise UserError(_(
                    "Qoralamaga faqat storno qilingan hujjat qaytariladi."))
            rec.holat = 'draft'
        return True


class AgroNovaBoquvIshHaqiQator(models.Model):
    """Bitta xodimning bitta binoga tushgan ulushi."""
    _name = 'agronova.boquv.ish_haqi.qator'
    _description = "Boquv — ish haqi taqsimoti qatori"
    _order = 'employee_id, bino_id'

    ish_haqi_id = fields.Many2one(
        'agronova.boquv.ish_haqi', string="Hujjat", required=True,
        ondelete='cascade', index=True)
    company_id = fields.Many2one(
        related='ish_haqi_id.company_id', store=True, readonly=True)
    currency_id = fields.Many2one(
        related='ish_haqi_id.currency_id', readonly=True)
    employee_id = fields.Many2one(
        'hr.employee', string="Xodim", required=True, ondelete='restrict')
    bino_id = fields.Many2one(
        'agronova.boquv.bino', string="Bino", required=True, ondelete='restrict')
    filial_id = fields.Many2one(
        related='bino_id.filial_id', string="Filial", store=True, readonly=True)
    partiya_ids = fields.Many2many(
        'agronova.boquv.partiya', string="Partiyalar",
        compute='_compute_partiya',
        help="Binoda faol partiyalar bo'lsa — xarajat ular orasida bosh "
             "soniga qarab bo'linadi.")
    usul = fields.Selection(USUL, string="Taqsimlash usuli", required=True)
    kunlar = fields.Integer("Kunlar")
    jami_kun = fields.Integer("Davr kunlari")
    oylik_summa = fields.Monetary("Xodimning ish haqi")
    ulush = fields.Monetary("Ulush", required=True)

    @api.depends('bino_id')
    def _compute_partiya(self):
        for q in self:
            q.partiya_ids = [(6, 0, q.bino_id.aktiv_partiya_ids.ids)]

    def _obyekt(self):
        """Xarajat tushadigan yozuv.

        Binoda bitta faol partiya bo'lsa — o'shanga. Bir nechta bo'lsa
        (har xil yoshdagi jo'jalar) eng ko'p boshli partiyaga yoziladi:
        qator darajasida summani yana bo'lish tannarx izini
        murakkablashtiradi, taqsimot esa `_qator_vals()` da bino
        darajasida allaqachon adolatli bajarilgan.

        Faol partiya bo'lmasa (dizinfeksiya davri) — binoning o'ziga.
        """
        self.ensure_one()
        aktiv = self.bino_id.aktiv_partiya_ids
        if not aktiv:
            return self.bino_id
        return max(aktiv, key=lambda p: p.joriy_son)
