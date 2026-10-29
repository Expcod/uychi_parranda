# -*- coding: utf-8 -*-
"""Boquv filiali — tuzilmaning ikkinchi qavati (TZ 2-band).

    Korxona → **Filial** → Bino → Partiya

Ona Tovuqda bu qavat yo'q (u yerda sex to'g'ridan-to'g'ri korxonaga tegishli),
Boquvda esa Andijon viloyati bo'ylab bir necha filial bor va rahbariyat
«qaysi filial samarali» degan savolga javob olishi kerak (TZ 21-band).

**Muhim:** bazada filial uchun analitik hisob va ombor allaqachon yaratilgan
(`Boquv N-filial`, `BQ0N`). Bu model ularni **topib ulanadi**, yangisini
yaratmaydi — aks holda bir obyektga ikki hisob ochilib, xarajat ikkiga
bo'linib ketadi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AgroNovaBoquvFilial(models.Model):
    _name = 'agronova.boquv.filial'
    _description = "Boquv filiali"
    _inherit = ['mail.thread']
    _order = 'sequence, code, name'

    name = fields.Char("Filial nomi", required=True, tracking=True)
    code = fields.Char("Kod", required=True, tracking=True)
    sequence = fields.Integer("Tartib", default=10)
    joylashuvi = fields.Char("Manzil", tracking=True)
    boshliq_id = fields.Many2one(
        'hr.employee', string="Filial boshlig'i", tracking=True,
        help="Filialga mas'ul xodim. Uning ish haqi filial binolariga "
             "m² bo'yicha taqsimlanadi.")
    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)

    # --- mavjud infratuzilmaga ulanish
    analytic_account_id = fields.Many2one(
        'account.analytic.account', string="Analitik hisob",
        ondelete='restrict', index=True, tracking=True,
        help="Filialning «Filial» rejasidagi mavjud analitik hisobi. "
             "Bo'sh qoldirilsa nom bo'yicha qidiriladi, topilmasa yaratiladi.")
    warehouse_id = fields.Many2one(
        'stock.warehouse', string="Ombor",
        domain="[('company_id', '=', company_id)]", tracking=True,
        help="Filial ombori. Bino lokatsiyalari shu ombor ostida ochiladi.")

    active = fields.Boolean("Faol", default=True)
    izoh = fields.Text("Izoh")

    # --- binolar
    bino_ids = fields.One2many(
        'agronova.boquv.bino', 'filial_id', string="Binolar")
    bino_soni = fields.Integer("Binolar soni", compute='_compute_bino')
    aktiv_bino_soni = fields.Integer(
        "Faol binolar", compute='_compute_bino',
        help="Holati «Aktiv» bo'lgan binolar — ularda jo'ja boqilmoqda.")
    jami_maydon = fields.Float(
        "Jami maydon (m²)", compute='_compute_bino',
        help="Doimiy xarajatni filiallar orasida bo'lishda ishlatiladi.")
    joriy_son = fields.Integer(
        "Joriy bosh soni", compute='_compute_bino',
        help="Filialdagi barcha faol partiyalarning jami tirik bosh soni.")

    _code_uniq = models.Constraint(
        'UNIQUE(code, company_id)', "Bu kodli filial allaqachon mavjud.")

    # ------------------------------------------------------------- compute
    @api.depends('bino_ids.holat', 'bino_ids.maydoni', 'bino_ids.joriy_son')
    def _compute_bino(self):
        for f in self:
            binolar = f.bino_ids
            f.bino_soni = len(binolar)
            f.aktiv_bino_soni = len(binolar.filtered(lambda b: b.holat == 'aktiv'))
            f.jami_maydon = sum(binolar.mapped('maydoni'))
            f.joriy_son = sum(binolar.mapped('joriy_son'))

    @api.constrains('analytic_account_id')
    def _check_analytic_unique(self):
        """Bitta analitik hisob ikki filialga biriktirilmasin."""
        for f in self.filtered('analytic_account_id'):
            band = self.search([
                ('analytic_account_id', '=', f.analytic_account_id.id),
                ('id', '!=', f.id),
            ], limit=1)
            if band:
                raise ValidationError(_(
                    "«%(hisob)s» analitik hisobi «%(filial)s» filialiga "
                    "allaqachon biriktirilgan. Bir hisob ikki filialga "
                    "bog'lanmaydi — xarajat ikkiga bo'linib ketadi.",
                    hisob=f.analytic_account_id.display_name,
                    filial=band.display_name))

    # ------------------------------------------------------- analitik hisob
    @api.model
    def _boquv_filial_plan(self):
        """«Filial» analitik rejasi — bazada allaqachon mavjud."""
        return self.env['agronova.analitik.mixin']._agronova_get_plan(name="Filial")

    def _ensure_analytic_account(self):
        """Analitik hisobni **topib** ulanadi, topilmasa yaratadi.

        Bazada «Boquv 1-filial» … «Boquv 7-filial» hisoblari oldindan
        yaratilgan. Nom bo'yicha qidiramiz, shunda mavjud xarajat tarixi
        yangi filial yozuviga bog'lanadi.
        """
        plan = self._boquv_filial_plan()
        if not plan:
            return
        Analytic = self.env['account.analytic.account'].sudo()
        for f in self.filtered(lambda r: not r.analytic_account_id):
            mavjud = Analytic.search([
                ('plan_id', '=', plan.id),
                ('name', '=ilike', f.name),
                ('company_id', 'in', [f.company_id.id, False]),
            ], limit=1)
            f.analytic_account_id = mavjud or Analytic.create({
                'name': f.name,
                'plan_id': plan.id,
                'company_id': f.company_id.id,
            })

    @api.model_create_multi
    def create(self, vals_list):
        filiallar = super().create(vals_list)
        filiallar._ensure_analytic_account()
        return filiallar

    @api.depends('name', 'code')
    def _compute_display_name(self):
        for f in self:
            f.display_name = "%s · %s" % (f.code, f.name) if f.code else f.name

    def action_open_binolar(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("«%s» binolari", self.name),
            'res_model': 'agronova.boquv.bino',
            'view_mode': 'list,form',
            'domain': [('filial_id', '=', self.id)],
            'context': {'default_filial_id': self.id},
        }
