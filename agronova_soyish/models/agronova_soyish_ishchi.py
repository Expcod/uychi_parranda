# -*- coding: utf-8 -*-
"""Xodimlar ishi — kim qaysi bosqichda nechta tovuq ishladi.

Patdan tozalash, kalla-oyoqni olish va ichini tozalashni **apparat**
qiladi — u yerda xodim ishi hisoblanmaydi. Qo'l mehnati bo'laklashda:
tushka qismlarga ajratiladi — file, qanot, oyoq, bel...

Bosqichlar ro'yxati kodga yozilmagan — ma'lumotnoma. Boshida bitta
«Bo'laklash» bor; kerak bo'lsa bo'linadi (masalan «File ajratish»,
«Qanot-oyoq») yoki qadoqlash kabi yangi qo'l bosqichi qo'shiladi. Har bosqichda
ishbay narx bor: xodimning ishlagan donasi (yoki kg) × narx.

Har qator so'yish hujjatiga bog'langan. Shunda bitta manbadan:

* har bir xodim jami / kunlik nechta tovuq ishlagani;
* soatiga necha dona (unumdorlik) va qancha brak qilgani;
* ishbay ish haqi summasi chiqadi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

OLCHOV = [
    ('dona', "Dona"),
    ('kg', "Kilogramm"),
]


class AgroNovaSoyishBosqich(models.Model):
    _name = 'agronova.soyish.bosqich'
    _description = "So'yish — ish bosqichi"
    _order = 'sequence, id'

    name = fields.Char("Bosqich", required=True, translate=True)
    sequence = fields.Integer("Tartib", default=10)
    olchov = fields.Selection(
        OLCHOV, string="Ish o'lchovi", required=True, default='dona',
        help="Ishbay haqi nimadan hisoblanadi: ishlangan tovuq donasidan "
             "yoki kilogrammidan.")
    narx = fields.Monetary(
        "Ishbay narx", help="1 dona (yoki 1 kg) uchun xodimga to'lanadigan "
                            "haq. Yangi qatorlarga avtomat qo'yiladi, eski "
                            "qatorlar o'zgarmaydi.")
    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)
    active = fields.Boolean(default=True)
    izoh = fields.Text("Izoh")


class AgroNovaSoyishIshchi(models.Model):
    _name = 'agronova.soyish.ishchi'
    _description = "So'yish — xodim ishi"
    _order = 'sana desc, jarayon_id, bosqich_sequence, id'

    jarayon_id = fields.Many2one(
        'agronova.soyish.jarayon', string="So'yish hujjati", required=True,
        ondelete='cascade', index=True)
    employee_id = fields.Many2one(
        'hr.employee', string="Xodim", required=True, index=True,
        ondelete='restrict')
    bosqich_id = fields.Many2one(
        'agronova.soyish.bosqich', string="Bosqich", required=True,
        ondelete='restrict')
    bosqich_sequence = fields.Integer(
        related='bosqich_id.sequence', store=True, readonly=True)
    olchov = fields.Selection(related='bosqich_id.olchov', readonly=True)

    dona = fields.Integer("Tovuq (dona)", required=True, default=0)
    kg = fields.Float("Vazn (kg)", digits='Product Unit',
                      help="Bo'laklashda — xodim ajratgan go'sht vazni.")
    brak_son = fields.Integer(
        "Brak (dona)",
        help="Xodim aybi bilan yaroqsiz bo'lgan tushka: noto'g'ri kesilgan, "
             "o't pufagi yorilgan va hokazo.")
    soat = fields.Float("Ishlagan soat",
                        help="Unumdorlik (dona/soat) shundan hisoblanadi.")
    dona_soat = fields.Float(
        "Dona / soat", compute='_compute_korsatkich', store=True,
        aggregator='avg', digits=(16, 1))
    brak_foiz = fields.Float(
        "Brak (%)", compute='_compute_korsatkich', store=True,
        aggregator='avg', digits=(16, 2))

    narx = fields.Monetary(
        "Ishbay narx", compute='_compute_narx', store=True, readonly=False,
        precompute=True)
    summa = fields.Monetary(
        "Ishbay haqi", compute='_compute_summa', store=True)

    # Hisobotda filtr va guruhlash uchun — hujjatdan nusxa
    sana = fields.Date(related='jarayon_id.sana', store=True, index=True,
                       string="Sana")
    partiya_id = fields.Many2one(related='jarayon_id.partiya_id', store=True,
                                 string="Partiya")
    manba = fields.Selection(related='jarayon_id.manba', store=True,
                             string="Kelib chiqishi")
    holat = fields.Selection(related='jarayon_id.holat', store=True,
                             string="Hujjat holati")
    company_id = fields.Many2one(related='jarayon_id.company_id', store=True,
                                 string="Korxona")
    currency_id = fields.Many2one(related='jarayon_id.currency_id',
                                  readonly=True)
    izoh = fields.Char("Izoh")

    _dona_manfiy_emas = models.Constraint(
        'CHECK (dona >= 0 AND brak_son >= 0 AND kg >= 0 AND soat >= 0)',
        "Dona, vazn, brak va soat manfiy bo'lmaydi.")

    @api.depends('dona', 'soat', 'brak_son')
    def _compute_korsatkich(self):
        for q in self:
            q.dona_soat = q.dona / q.soat if q.soat else 0.0
            jami = q.dona + q.brak_son
            q.brak_foiz = q.brak_son / jami * 100.0 if jami else 0.0

    @api.depends('bosqich_id')
    def _compute_narx(self):
        for q in self:
            q.narx = q.bosqich_id.narx

    @api.depends('narx', 'dona', 'kg', 'bosqich_id.olchov')
    def _compute_summa(self):
        for q in self:
            miqdor = q.kg if q.bosqich_id.olchov == 'kg' else q.dona
            q.summa = miqdor * q.narx

    @api.constrains('dona', 'brak_son', 'bosqich_id', 'jarayon_id')
    def _check_dona(self):
        self.jarayon_id._check_ishchi_son()

    @api.depends('employee_id', 'bosqich_id', 'dona')
    def _compute_display_name(self):
        for q in self:
            q.display_name = "%s · %s · %s" % (
                q.employee_id.name or '', q.bosqich_id.name or '', q.dona)


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    agronova_soyish_ishchi_ids = fields.One2many(
        'agronova.soyish.ishchi', 'employee_id', string="So'yishdagi ishi",
        groups="agronova_soyish.group_soyish_operator")
    agronova_soyish_jami_dona = fields.Integer(
        "So'yishda ishlagan tovuq", compute='_compute_agronova_soyish',
        groups="agronova_soyish.group_soyish_operator")

    def _compute_agronova_soyish(self):
        guruh = self.env['agronova.soyish.ishchi'].sudo()._read_group(
            [('employee_id', 'in', self.ids), ('holat', '=', 'done')],
            ['employee_id'], ['dona:sum'])
        jami = {emp.id: dona for emp, dona in guruh}
        for emp in self:
            emp.agronova_soyish_jami_dona = jami.get(emp.id, 0)

    def action_agronova_soyish_ishi(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'agronova_soyish.action_soyish_ishchi_hisobot')
        action['domain'] = [('employee_id', '=', self.id)]
        action['context'] = {'search_default_tasdiqlangan': 1,
                             'search_default_g_bosqich': 1}
        action['name'] = _("%s — so'yishdagi ishi", self.name)
        return action
