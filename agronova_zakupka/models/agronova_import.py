# -*- coding: utf-8 -*-
"""Import hujjati — C1 (tovar) va C2 (uskuna) (TZ 4.6, 10-bo'lim).

Import asosiy zanjirdan tashqarida turadi: shartnoma, valyuta, GTD va
bojxona to'lovlari qo'shiladi, muddat normasi haftalar/oylar bilan
o'lchanadi.

Farqi bitta joyda hal bo'ladi:

* **C1 — tovar** omborga tushadi, zaxira sifatida hisobga olinadi,
  sotilganda xarajatga o'tadi;
* **C2 — uskuna** omborga tushmaydi, `account.asset` orqali asosiy vosita
  sifatida amortizatsiya qilinadi.

Tovar qachon balansga tushishi yetkazib berish shartiga (FOB/CIF/DAP)
bog'liq — bu masala har shartnoma bo'yicha buxgalter bilan kelishiladi,
shuning uchun **qattiq kodlanmaydi**: `balansga_olish_sanasi` qo'lda
kiritiladigan maydon, sharti esa hujjatda ko'rinib turadi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

YETKAZISH_SHARTI = [
    ('EXW', "EXW — zavoddan"),
    ('FCA', "FCA — tashuvchiga topshirilgan"),
    ('FOB', "FOB — bortda"),
    ('CFR', "CFR — narx va fraxt"),
    ('CIF', "CIF — narx, sug'urta, fraxt"),
    ('CPT', "CPT — tashish to'langan"),
    ('CIP', "CIP — tashish va sug'urta to'langan"),
    ('DAP', "DAP — joyda yetkazilgan"),
    ('DDP', "DDP — boj to'langan holda yetkazilgan"),
]
IMPORT_TURI = [
    ('C1_tovar', "C1 — tovar importi"),
    ('C2_uskuna', "C2 — uskuna importi"),
]


class AgroNovaImport(models.Model):
    _name = 'agronova.import'
    _description = "Import partiyasi"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'kutilayotgan_sana, id desc'

    name = fields.Char(
        "Hujjat raqami", default=lambda self: _("Yangi"),
        copy=False, readonly=True, index=True)
    import_turi = fields.Selection(
        IMPORT_TURI, string="Import turi", required=True, default='C1_tovar',
        tracking=True)
    kontragent_id = fields.Many2one(
        'res.partner', string="Yetkazib beruvchi", required=True,
        tracking=True, domain="[('zakupka_holati', '=', 'faol')]")
    zakupchik_id = fields.Many2one(
        'res.users', string="Mas'ul zakupchik", required=True,
        default=lambda self: self.env.user, tracking=True)
    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)

    # --- shartnoma
    shartnoma_raqami = fields.Char("Shartnoma raqami", required=True, tracking=True)
    shartnoma_sanasi = fields.Date("Shartnoma sanasi", required=True)
    yetkazib_berish_sharti = fields.Selection(
        YETKAZISH_SHARTI, string="Yetkazib berish sharti", required=True,
        default='CIF', tracking=True)
    valyuta_id = fields.Many2one(
        'res.currency', string="Shartnoma valyutasi", required=True,
        default=lambda self: self.env.company.currency_id)
    shartnoma_kursi = fields.Float(
        "Shartnoma kursi", digits=(16, 6),
        help="Shartnoma imzolangan paytdagi kurs — kurs farqi shundan "
             "hisoblanadi.")
    shartnoma_summasi = fields.Monetary(
        "Shartnoma summasi (valyutada)", currency_field='valyuta_id')

    # --- bojxona
    gtd_raqami = fields.Char(
        "GTD raqami", tracking=True,
        help="Bojxona yuk deklaratsiyasi — soliq hisoboti uchun majburiy.")
    gtd_sanasi = fields.Date("GTD sanasi")
    bojxona_bojji = fields.Monetary("Bojxona boji")
    bojxona_yigimi = fields.Monetary("Bojxona yig'imi")
    bojxona_qqsi = fields.Monetary(
        "Bojxona QQSi",
        help="Oddiy QQSdan alohida yuritiladi — zachyot boshqacha.")
    aksiz = fields.Monetary("Aksiz")

    # --- qo'shimcha xarajatlar (Landed Cost ga tushadi)
    transport_xalqaro = fields.Monetary("Xalqaro transport")
    transport_ichki = fields.Monetary("Ichki transport")
    sugurta = fields.Monetary("Sug'urta")
    broker_xizmati = fields.Monetary("Broker xizmati")
    qoshimcha_jami = fields.Monetary(
        "Qo'shimcha xarajat jami", compute='_compute_qoshimcha_jami', store=True,
        help="Barchasi tannarxga qo'shiladi (IAS 2) — alohida xarajat "
             "sifatida yozilmaydi.")

    # --- muddatlar
    kutilayotgan_sana = fields.Date("Kutilayotgan kelish sanasi", tracking=True)
    haqiqiy_kelish_sanasi = fields.Date("Haqiqiy kelish sanasi", tracking=True)
    kechikish_kuni = fields.Integer(
        "Kechikish (kun)", compute='_compute_kechikish_kuni', store=True)
    balansga_olish_sanasi = fields.Date(
        "Balansga olish sanasi", tracking=True,
        help="Yetkazib berish shartiga qarab buxgalter belgilaydi "
             "(FOB — bortga yuklanganda, DAP — yetkazilganda va h.k.). "
             "Qattiq kodlanmagan — TZ 10-bo'lim.")

    holat = fields.Selection(
        [('draft', "Qoralama"),
         ('yolda', "Yo'lda"),
         ('bojxonada', "Bojxonada"),
         ('keldi', "Keldi"),
         ('yopildi', "Yopildi")],
        string="Holati", default='draft', required=True, tracking=True, copy=False)

    kirim_ids = fields.One2many(
        'agronova.kirim', 'import_id', string="Kirim hujjatlari")
    kirim_soni = fields.Integer("Kirimlar", compute='_compute_kirim_soni')
    izoh = fields.Text("Izoh")

    @api.depends('transport_xalqaro', 'transport_ichki', 'sugurta',
                 'broker_xizmati', 'bojxona_bojji', 'bojxona_yigimi', 'aksiz')
    def _compute_qoshimcha_jami(self):
        for rec in self:
            rec.qoshimcha_jami = (
                rec.transport_xalqaro + rec.transport_ichki + rec.sugurta
                + rec.broker_xizmati + rec.bojxona_bojji + rec.bojxona_yigimi
                + rec.aksiz)

    @api.depends('kutilayotgan_sana', 'haqiqiy_kelish_sanasi')
    def _compute_kechikish_kuni(self):
        bugun = fields.Date.context_today(self)
        for rec in self:
            if not rec.kutilayotgan_sana:
                rec.kechikish_kuni = 0
                continue
            tugash = rec.haqiqiy_kelish_sanasi or bugun
            rec.kechikish_kuni = max((tugash - rec.kutilayotgan_sana).days, 0)

    def _compute_kirim_soni(self):
        for rec in self:
            rec.kirim_soni = len(rec.kirim_ids)

    @api.constrains('holat', 'gtd_raqami')
    def _check_gtd(self):
        for rec in self:
            if rec.holat in ('keldi', 'yopildi') and not rec.gtd_raqami:
                raise ValidationError(_(
                    "«%s»: bojxonadan chiqqan partiyada GTD raqami majburiy "
                    "— soliq hisoboti shunga tayanadi.", rec.display_name))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _("Yangi")) == _("Yangi"):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'agronova.import') or _("Yangi")
        return super().create(vals_list)

    def action_yolda(self):
        self.write({'holat': 'yolda'})
        return True

    def action_bojxonada(self):
        self.write({'holat': 'bojxonada'})
        return True

    def action_keldi(self):
        for rec in self:
            rec.write({
                'holat': 'keldi',
                'haqiqiy_kelish_sanasi': rec.haqiqiy_kelish_sanasi
                or fields.Date.context_today(rec),
            })
        return True

    def action_yopish(self):
        for rec in self:
            if not rec.kirim_ids:
                raise UserError(_(
                    "«%s»: kirim hujjati rasmiylashtirilmagan partiya "
                    "yopilmaydi.", rec.display_name))
            rec.holat = 'yopildi'
        return True

    def action_kirim_yaratish(self):
        """Import partiyasidan kirim hujjati ochadi."""
        self.ensure_one()
        if self.holat not in ('bojxonada', 'keldi'):
            raise UserError(_(
                "Kirim hujjati partiya bojxonaga yetgandan keyin ochiladi."))
        xarid_turi = ('C1_import_tovar' if self.import_turi == 'C1_tovar'
                      else 'C2_import_uskuna')
        return {
            'type': 'ir.actions.act_window',
            'name': _("Import kirim hujjati"),
            'res_model': 'agronova.kirim',
            'view_mode': 'form',
            'context': {
                'default_import_id': self.id,
                'default_xarid_turi': xarid_turi,
                'default_kontragent_id': self.kontragent_id.id,
                'default_zakupchik_id': self.zakupchik_id.id,
                'default_sotib_olingan_sana': (
                    self.balansga_olish_sanasi
                    or self.haqiqiy_kelish_sanasi
                    or fields.Date.context_today(self)),
                # Bojxona va yo'l xarajatlari Landed Cost orqali tannarxga.
                'default_transport_xarajati': (
                    self.transport_xalqaro + self.transport_ichki),
                'default_qoshimcha_xarajat': (
                    self.sugurta + self.broker_xizmati + self.bojxona_bojji
                    + self.bojxona_yigimi + self.aksiz),
            },
        }

    def action_kirimlarni_korish(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Kirim hujjatlari"),
            'res_model': 'agronova.kirim',
            'view_mode': 'list,form',
            'domain': [('import_id', '=', self.id)],
        }
