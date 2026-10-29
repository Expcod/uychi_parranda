# -*- coding: utf-8 -*-
"""Bino (seh) — jo'ja boqiladigan obyekt.

Ona Tovuqdagi sexdan **ikkita muhim farqi** bor:

1. **Holat mexanizmi bor.** Yakuniy TZ da doimiy xarajatning binolarga
   tushishi holatga bog'liq:

   * `dizinfeksiya` — m² ulushi **to'liq** olinadi (koeffitsientsiz);
   * `aktiv` — m² ulushi olinadi;
   * `no_aktiv` — **xarajat kelmaydi** (bo'sh, quvvatdan chiqarilgan).

   Shuning uchun `_agronova_taqsimot_targets()` da bino holatiga qarab
   filtrlanadi. Veterinar ish haqi kabi ba'zi xarajatlar esa faqat
   **aktiv** binoga tushadi — dizinfeksiyadagi binoda jo'ja yo'q.

2. **Bir binoda bir necha aktiv partiya** bo'lishi mumkin. Mijoz izohi:
   «har sehda har xil yoshdagi jo'jalar bo'ladi». Ona Tovuqda bitta sexda
   bitta aktiv partiya, Boquvda bunday cheklov yo'q.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# Bino holati → doimiy xarajat ulushi koeffitsienti.
# Yakuniy TZ «Bino holatlari va doimiy xarajat» bo'limi.
HOLAT_KOEFFITSIENT = {
    'dizinfeksiya': 1.0,   # m² ulushi to'liq
    'aktiv': 1.0,          # m² ulushi
    'no_aktiv': 0.0,       # xarajat kelmaydi
}


class AgroNovaBoquvBino(models.Model):
    _name = 'agronova.boquv.bino'
    _description = "Boquv binosi (seh)"
    _inherit = ['agronova.analitik.mixin', 'mail.thread']
    _order = 'filial_id, code, name'

    # Ona Tovuq bilan bir xil kesim — bazada «Bino (seh)» rejasi mavjud.
    _agronova_analytic_plan_name = "Bino (seh)"

    _rec_names_search = ['name', 'code', 'filial_id.name']

    name = fields.Char("Bino nomi", required=True, tracking=True)
    code = fields.Char("Kod", required=True, tracking=True)
    filial_id = fields.Many2one(
        'agronova.boquv.filial', string="Filial", required=True, tracking=True,
        ondelete='restrict', index=True)
    maydoni = fields.Float(
        "Maydoni (m²)", required=True, tracking=True, digits=(12, 2),
        help="Ijara, elektr, isitish va filial xodimlari ish haqi shu maydon "
             "nisbatida taqsimlanadi — shuning uchun majburiy.")
    sigimi = fields.Integer(
        "Sig'imi (bosh)", tracking=True,
        help="Binoga sig'adigan maksimal bosh soni. TZ bo'yicha o'rtacha 20 000.")
    operator_id = fields.Many2one(
        'hr.employee', string="Bino operatori", tracking=True,
        help="Shu binoga biriktirilgan operator. Uning ish haqi to'g'ridan-"
             "to'g'ri shu binoning faol partiyalariga yoziladi.")
    brigadir_id = fields.Many2one(
        'hr.employee', string="Mas'ul brigader", tracking=True,
        help="Kunlik obxod va jurnal uchun mas'ul (TZ 9-band).")

    holat = fields.Selection(
        [('no_aktiv', "No aktiv (bo'sh)"),
         ('dizinfeksiya', "Dizinfeksiya"),
         ('aktiv', "Aktiv")],
        string="Bino holati", default='no_aktiv', required=True, tracking=True,
        help="Doimiy xarajatning binoga tushishi shu holatga bog'liq:\n"
             "• Dizinfeksiya — m² ulushi to'liq;\n"
             "• Aktiv — m² ulushi;\n"
             "• No aktiv — xarajat kelmaydi.")

    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True, readonly=True,
        store=True, precompute=True, compute='_compute_company_id',
        help="Filial qaysi korxonada bo'lsa — bino ham o'shanda.")
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)
    warehouse_id = fields.Many2one(
        'stock.warehouse', string="Ombor", related='filial_id.warehouse_id',
        store=True, readonly=True)
    location_id = fields.Many2one(
        'stock.location', string="Ombor lokatsiyasi", readonly=True, copy=False,
        help="Bino yaratilganda avtomat ochiladi. Yem, dori va vaksina shu "
             "joydan hisobdan chiqadi.")
    active = fields.Boolean("Faol", default=True)
    izoh = fields.Text("Izoh")

    # --- partiyalar
    partiya_ids = fields.One2many(
        'agronova.boquv.partiya', 'bino_id', string="Partiyalar")
    aktiv_partiya_ids = fields.Many2many(
        'agronova.boquv.partiya', string="Faol partiyalar",
        compute='_compute_aktiv',
        help="Binoda bir vaqtda bir necha partiya bo'lishi mumkin — "
             "har xil yoshdagi jo'jalar.")
    aktiv_partiya_soni = fields.Integer(
        "Faol partiyalar soni", compute='_compute_aktiv', store=True)
    joriy_son = fields.Integer(
        "Joriy bosh soni", compute='_compute_aktiv', store=True,
        help="Binodagi barcha faol partiyalarning jami tirik bosh soni.")
    band_foiz = fields.Float(
        "Bandlik (%)", compute='_compute_aktiv', store=True,
        help="Joriy bosh soni / sig'imi. Sexlar yuklamasi hisoboti uchun.")

    # --- moliya
    jami_xarajat = fields.Monetary("Jami xarajat", compute='_compute_moliya')
    jami_daromad = fields.Monetary("Jami daromad", compute='_compute_moliya')
    foyda = fields.Monetary("Foyda / zarar", compute='_compute_moliya')

    _code_uniq = models.Constraint(
        'UNIQUE(code, company_id)', "Bu kodli bino allaqachon mavjud.")
    _maydoni_musbat = models.Constraint(
        'CHECK (maydoni > 0)',
        "Bino maydoni (m²) noldan katta bo'lishi kerak — doimiy xarajat "
        "shu nisbatda taqsimlanadi.")

    # ------------------------------------------------------------- compute
    @api.depends('filial_id')
    def _compute_company_id(self):
        for b in self:
            b.company_id = b.filial_id.company_id or self.env.company

    @api.depends('name', 'code', 'filial_id')
    def _compute_display_name(self):
        for b in self:
            nom = "%s · %s" % (b.code, b.name) if b.code else b.name
            b.display_name = ("%s / %s" % (b.filial_id.code, nom)
                              if b.filial_id.code else nom)

    @api.depends('partiya_ids.holat', 'partiya_ids.joriy_son', 'sigimi')
    def _compute_aktiv(self):
        for b in self:
            aktiv = b.partiya_ids.filtered(lambda p: p.holat == 'active')
            b.aktiv_partiya_ids = [(6, 0, aktiv.ids)]
            b.aktiv_partiya_soni = len(aktiv)
            b.joriy_son = sum(aktiv.mapped('joriy_son'))
            b.band_foiz = (b.joriy_son / b.sigimi * 100.0) if b.sigimi else 0.0

    def _compute_moliya(self):
        for b in self:
            # Binoning o'z analitik hisobi (doimiy xarajat) va undagi
            # partiyalar yig'indisi.
            xarajat = b._agronova_analytic_amount(sign='cost')
            daromad = b._agronova_analytic_amount(sign='income')
            for p in b.partiya_ids:
                xarajat += p.jami_xarajat
                daromad += p.jami_daromad
            b.jami_xarajat = xarajat
            b.jami_daromad = daromad
            b.foyda = daromad - xarajat

    # ------------------------------------------------------- analitik hisob
    def _agronova_analytic_vals(self):
        vals = super()._agronova_analytic_vals()
        vals['name'] = self.display_name
        return vals

    def _ensure_analytic_account(self):
        """Mavjud analitik hisobni topib ulanadi (dublikat oldini olish).

        Ona Tovuqda bir sexga bir xil nomli hisob bir necha marta ochilib
        ketgan — bu yerda avval nom bo'yicha qidiramiz.
        """
        plan = self._agronova_analytic_plan()
        if not plan:
            return
        Analytic = self.env['account.analytic.account'].sudo()
        for b in self.filtered(lambda r: not r.analytic_account_id):
            mavjud = Analytic.search([
                ('plan_id', '=', plan.id),
                ('name', '=ilike', b.display_name),
                ('company_id', 'in', [b.company_id.id, False]),
            ], limit=1)
            if mavjud:
                b.analytic_account_id = mavjud
            else:
                vals = b._agronova_analytic_vals()
                vals['plan_id'] = plan.id
                b.analytic_account_id = Analytic.create(vals)

    # ------------------------------------------------------------ lokatsiya
    def _ensure_location(self):
        """Bino uchun ombor lokatsiyasi ochadi."""
        Location = self.env['stock.location'].sudo()
        for b in self.filtered(lambda r: not r.location_id and r.warehouse_id):
            parent = b.warehouse_id.lot_stock_id
            mavjud = Location.search([
                ('location_id', '=', parent.id),
                ('name', '=', b.code or b.name),
            ], limit=1)
            b.location_id = mavjud or Location.create({
                'name': b.code or b.name,
                'location_id': parent.id,
                'usage': 'internal',
                'company_id': b.company_id.id,
            })

    def _production_location(self):
        """Sarf hisobdan chiqadigan virtual «ishlab chiqarish» joyi.

        Odoo 19 da `stock.location_production` xmlid'i yo'q — bunday
        lokatsiya faqat MRP o'rnatilganda yoki qo'lda yaratiladi. Shuning
        uchun korxona bo'yicha qidiramiz, topilmasa o'zimiz ochamiz.
        Ona Tovuq moduli ham shu yondashuvni qo'llaydi.
        """
        self.ensure_one()
        Location = self.env['stock.location'].sudo()
        loc = Location.search([
            ('usage', '=', 'production'),
            ('company_id', 'in', [self.company_id.id, False]),
        ], limit=1)
        if not loc:
            loc = Location.create({
                'name': _("Boquv — sarf"),
                'usage': 'production',
                'company_id': self.company_id.id,
            })
        return loc

    @api.model_create_multi
    def create(self, vals_list):
        binolar = super().create(vals_list)
        binolar._ensure_location()
        return binolar

    def write(self, vals):
        res = super().write(vals)
        if vals.get('filial_id') or vals.get('code'):
            self._ensure_location()
        return res

    # --------------------------------------------------------------- holat
    def _holat_koeffitsient(self):
        """Doimiy xarajatdagi ulush koeffitsienti."""
        self.ensure_one()
        return HOLAT_KOEFFITSIENT.get(self.holat, 0.0)

    def action_dizinfeksiya(self):
        for b in self:
            if b.aktiv_partiya_soni:
                raise UserError(_(
                    "«%(bino)s» binosida %(son)s ta faol partiya bor — "
                    "dizinfeksiyaga o'tkazib bo'lmaydi. Avval partiyalarni "
                    "yoping yoki so'yishga topshiring.",
                    bino=b.display_name, son=b.aktiv_partiya_soni))
            b.holat = 'dizinfeksiya'
        return True

    def action_aktiv(self):
        self.write({'holat': 'aktiv'})
        return True

    def action_no_aktiv(self):
        for b in self:
            if b.aktiv_partiya_soni:
                raise UserError(_(
                    "«%(bino)s» binosida faol partiya bor — «No aktiv» "
                    "holatiga o'tkazib bo'lmaydi.", bino=b.display_name))
            b.holat = 'no_aktiv'
        return True

    def action_open_partiyalar(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("«%s» partiyalari", self.display_name),
            'res_model': 'agronova.boquv.partiya',
            'view_mode': 'list,form',
            'domain': [('bino_id', '=', self.id)],
            'context': {'default_bino_id': self.id,
                        'default_filial_id': self.filial_id.id},
        }
