# -*- coding: utf-8 -*-
"""Ish haqini sexlarga taqsimlash — B07.

Oylik hujjat: davr tanlanadi, xodimlar yig'iladi, har birining ish haqi
sexlarga bo'linadi va analitik qatorlar yoziladi.

Qoidalar (TZ B07):

* **Sexga biriktirilgan xodim** (operator) — ish haqi to'g'ridan-to'g'ri
  o'sha sexning aktiv partiyasiga tushadi;
* **Biriktirilmagan xodim** (bo'lim boshlig'i, veterinar) — barcha sexlarga
  **m² bo'yicha** taqsimlanadi;
* **oy o'rtasida sex o'zgarsa** — `agronova.ona_tovuq.xodim.sex.tarix` yozuvlari
  bo'yicha **kunlarga bo'linadi**: 10 kun 1-sexda, 20 kun 2-sexda ishlagan
  xodimning ish haqi ham shu nisbatda bo'linadi.

Ish haqi summasi manbai — `_xodim_summa()`. Payroll o'rnatilgan bo'lsa
tasdiqlangan hisobvaraqdan, aks holda amaldagi shartnoma (`hr.version`)
oyligidan olinadi. Payrollga **qattiq bog'lanish yo'q** — modul u
o'rnatilmagan bazada ham ishlaydi.
"""
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

USUL = [
    ('togridan', "To'g'ridan-to'g'ri (biriktirilgan sex)"),
    ('m2', "m² bo'yicha (biriktirilmagan)"),
]


class AgroNovaOnaTovuqIshHaqi(models.Model):
    _name = 'agronova.ona_tovuq.ish_haqi'
    _description = "Ona tovuq — ish haqi taqsimoti"
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
    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)
    department_ids = fields.Many2many(
        'hr.department', string="Bo'limlar",
        help="Bo'sh bo'lsa — faqat sexga biriktirilgan xodimlar olinadi. "
             "To'ldirilsa, bu bo'limlarning biriktirilmagan xodimlari ham "
             "m² bo'yicha taqsimlanadi.")
    qator_ids = fields.One2many(
        'agronova.ona_tovuq.ish_haqi.qator', 'ish_haqi_id', string="Qatorlar",
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
                    'agronova.ona_tovuq.ish_haqi') or _("Yangi")
        return super().create(vals_list)

    def write(self, vals):
        # Tasdiqlangan taqsimotni tahrirlash tannarxni buzadi.
        if not set(vals) <= {'holat', 'analytic_line_ids', 'izoh'}:
            for rec in self:
                if rec.holat != 'draft':
                    raise UserError(_(
                        "«%s» taqsimoti tasdiqlangan — tahrirlanmaydi. "
                        "Avval storno qiling.", rec.display_name))
        return super().write(vals)

    # ------------------------------------------------------------ xodimlar
    def _xodimlar(self):
        """Taqsimotga kiradigan xodimlar.

        Sexga biriktirilganlar har doim, bo'lim ko'rsatilgan bo'lsa o'sha
        bo'lim xodimlari ham (ular m² bo'yicha bo'linadi).
        """
        self.ensure_one()
        domain = ['|', ('agronova_ot_sex_id', '!=', False)]
        if self.department_ids:
            domain.append(('department_id', 'in', self.department_ids.ids))
        else:
            # `|` juftini yopish uchun hech qachon rost bo'lmaydigan shart
            domain.append(('id', '=', 0))
        domain.append(('company_id', '=', self.company_id.id))
        return self.env['hr.employee'].sudo().search(domain)

    def _xodim_summa(self, employee):
        """Xodimning shu davrdagi ish haqi xarajati.

        Birinchi manba — `agronova_ish_haqi` moduli: uning oylik hisoblash
        hujjati loyihaning o'z tarif tizimi bo'yicha ishlaydi va bo'lim
        taqsimoti aynan shu summani bo'lishi kerak.

        Payroll va shartnoma oyligi — zaxira yo'llar, modul o'rnatilmagan
        yoki oylik hali hisoblanmagan bazada ishlashi uchun.
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

    def _sexlar(self):
        return self.env['agronova.ona_tovuq.sex'].sudo().search(
            [('company_id', '=', self.company_id.id)])

    def _davr_kunlari(self):
        return (self.davr_oxiri - self.davr_boshi).days + 1

    # ------------------------------------------------------------- yig'ish
    def action_yigish(self):
        """Xodimlarni yig'ib, ish haqini sexlarga bo'ladi."""
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
        sexlar = self._sexlar()
        if not sexlar:
            raise UserError(_("Bu korxonada birorta sex yo'q — "
                              "ish haqini taqsimlab bo'lmaydi."))
        jami_kun = self._davr_kunlari()
        vals = []
        for emp in self._xodimlar():
            summa = self._xodim_summa(emp)
            if not summa:
                continue
            kunlik = summa / jami_kun
            biriktirilgan = 0

            for tarix, kun in self._tarix_kunlari(emp):
                biriktirilgan += kun
                vals.append({
                    'employee_id': emp.id,
                    'sex_id': tarix.sex_id.id,
                    'kunlar': kun,
                    'jami_kun': jami_kun,
                    'oylik_summa': summa,
                    'usul': 'togridan',
                    'ulush': self.currency_id.round(kunlik * kun),
                })

            qolgan_kun = jami_kun - biriktirilgan
            if qolgan_kun > 0:
                # Biriktirilmagan kunlar — m² bo'yicha barcha sexlarga
                qoldiq = self.currency_id.round(kunlik * qolgan_kun)
                for sex, ulush in self._m2_bolish(sexlar, qoldiq):
                    if not ulush:
                        continue
                    vals.append({
                        'employee_id': emp.id,
                        'sex_id': sex.id,
                        'kunlar': qolgan_kun,
                        'jami_kun': jami_kun,
                        'oylik_summa': summa,
                        'usul': 'm2',
                        'ulush': ulush,
                    })
        return vals

    def _tarix_kunlari(self, employee):
        """`[(tarix, kunlar), ...]` — xodim davr ichida qaysi sexda necha kun.

        Tarix yozuvlari bir-birining ustiga tushib qolsa ham jami kun davr
        uzunligidan oshmaydi.
        """
        self.ensure_one()
        jami_kun = self._davr_kunlari()
        tarix = self.env['agronova.ona_tovuq.xodim.sex.tarix'].sudo().search([
            ('employee_id', '=', employee.id),
            ('boshlanish_sana', '<=', self.davr_oxiri),
            '|', ('tugash_sana', '=', False),
                 ('tugash_sana', '>=', self.davr_boshi),
        ], order='boshlanish_sana')

        if not tarix and employee.agronova_ot_sex_id:
            # Tarix yuritilmagan (modul o'rnatilishidan oldin biriktirilgan) —
            # butun davr joriy sexga tegishli deb hisoblaymiz.
            soxta = self.env['agronova.ona_tovuq.xodim.sex.tarix'].new({
                'employee_id': employee.id,
                'sex_id': employee.agronova_ot_sex_id.id,
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

    def _m2_bolish(self, sexlar, summa):
        """Summani m² bo'yicha bo'ladi; maydon kiritilmagan bo'lsa teng."""
        self.ensure_one()
        ogirlik = [s.maydoni or 0.0 for s in sexlar]
        if not sum(ogirlik):
            ogirlik = [1.0] * len(sexlar)
        jami = sum(ogirlik)
        natija, taqsimlangan = [], 0.0
        for idx, (sex, w) in enumerate(zip(sexlar, ogirlik)):
            if idx == len(sexlar) - 1:
                ulush = summa - taqsimlangan       # yaxlitlash farqi oxirgisiga
            else:
                ulush = self.currency_id.round(summa * w / jami)
                taqsimlangan += ulush
            natija.append((sex, ulush))
        return natija

    # --------------------------------------------------------------- holat
    def action_tasdiqlash(self):
        for rec in self:
            if rec.holat != 'draft':
                raise UserError(_("«%s» allaqachon tasdiqlangan.", rec.display_name))
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
        return True

    def action_qoralamaga(self):
        for rec in self:
            if rec.holat != 'storno':
                raise UserError(_(
                    "Qoralamaga faqat storno qilingan hujjat qaytariladi."))
            rec.holat = 'draft'
        return True


class AgroNovaOnaTovuqIshHaqiQator(models.Model):
    """Bitta xodimning bitta sexga tushgan ulushi."""
    _name = 'agronova.ona_tovuq.ish_haqi.qator'
    _description = "Ona tovuq — ish haqi taqsimoti qatori"
    _order = 'employee_id, sex_id'

    ish_haqi_id = fields.Many2one(
        'agronova.ona_tovuq.ish_haqi', string="Hujjat", required=True,
        ondelete='cascade', index=True)
    company_id = fields.Many2one(
        related='ish_haqi_id.company_id', store=True, readonly=True)
    currency_id = fields.Many2one(
        related='ish_haqi_id.currency_id', readonly=True)
    employee_id = fields.Many2one(
        'hr.employee', string="Xodim", required=True, ondelete='restrict')
    sex_id = fields.Many2one(
        'agronova.ona_tovuq.sex', string="Sex", required=True, ondelete='restrict')
    partiya_id = fields.Many2one(
        'agronova.ona_tovuq.partiya.tuxum', string="Partiya",
        compute='_compute_partiya', store=True,
        help="Sexda aktiv tuxum partiyasi bo'lsa — xarajat shunga tushadi.")
    usul = fields.Selection(USUL, string="Taqsimlash usuli", required=True)
    kunlar = fields.Integer("Kunlar")
    jami_kun = fields.Integer("Davr kunlari")
    oylik_summa = fields.Monetary("Xodimning ish haqi")
    ulush = fields.Monetary("Ulush", required=True)

    @api.depends('sex_id')
    def _compute_partiya(self):
        for q in self:
            q.partiya_id = q.sex_id.aktiv_partiya_id

    def _obyekt(self):
        """Xarajat tushadigan yozuv — aktiv partiya, bo'lmasa sexning o'zi."""
        self.ensure_one()
        sex = self.sex_id
        return sex.aktiv_partiya_id or sex.aktiv_ostirish_id or sex
