# -*- coding: utf-8 -*-
"""Partiyalararo o'tkazma — jo'jani boshqa binoga ko'chirish.

Mijoz izohi (2026-08-08): «sehdan sehga kirim/chiqim tranzaksiyalari»,
«har sehda har xil yoshdagi jo'jalar bo'ladi».

Amalda bu quyidagi hollarda kerak bo'ladi:

* podani siyraklashtirish — bino to'lib ketgan, bir qismi bo'sh binoga;
* birlashtirish — ikki kichik qoldiq bitta binoga yig'iladi;
* saralash — kasal yoki orqada qolgan boshlar alohida binoga.

**Tannarx bilan ishlash.** O'tkazilgan boshlar o'zi bilan tannarxini olib
ketadi: manba partiyada teskari qator (tannarx chiqadi), qabul qiluvchi
partiyada xarajat qatori (tannarx kiradi). Shunda ikkala partiyaning
birlik tannarxi to'g'ri qoladi — o'tkazma foyda ham, zarar ham keltirmaydi.

Bu **jo'natma** (`agronova.boquv.jonatma`) dan farq qiladi: u yerda bo'lim
daromadi shakllanadi (so'yishga sotilyapti), bu yerda esa faqat ichki
ko'chirish — daromad yo'q.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class AgroNovaBoquvOtkazma(models.Model):
    _name = 'agronova.boquv.otkazma'
    _description = "Boquv — partiyalararo o'tkazma"
    _inherit = ['mail.thread']
    _order = 'sana desc, id desc'

    name = fields.Char(
        "Hujjat raqami", default=lambda self: _("Yangi"),
        copy=False, readonly=True, index=True)
    sana = fields.Date(
        "O'tkazma sanasi", required=True, index=True, tracking=True,
        default=fields.Date.context_today)
    sabab = fields.Selection(
        [('siyraklashtirish', "Siyraklashtirish (bino to'lgan)"),
         ('birlashtirish', "Qoldiqlarni birlashtirish"),
         ('saralash', "Saralash (kasal / orqada qolgan)"),
         ('boshqa', "Boshqa")],
        string="Sabab", required=True, default='siyraklashtirish',
        tracking=True)

    manba_partiya_id = fields.Many2one(
        'agronova.boquv.partiya', string="Manba partiya", required=True,
        tracking=True, ondelete='restrict', index=True,
        domain="[('holat', '=', 'active')]")
    qabul_partiya_id = fields.Many2one(
        'agronova.boquv.partiya', string="Qabul qiluvchi partiya", required=True,
        tracking=True, ondelete='restrict', index=True,
        domain="[('holat', '=', 'active')]")
    manba_bino_id = fields.Many2one(
        related='manba_partiya_id.bino_id', string="Manba bino",
        store=True, readonly=True)
    qabul_bino_id = fields.Many2one(
        related='qabul_partiya_id.bino_id', string="Qabul qiluvchi bino",
        store=True, readonly=True)
    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True, readonly=True,
        store=True, precompute=True, compute='_compute_company_id')
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)

    bosh_soni = fields.Integer("Bosh soni", required=True, tracking=True)
    ortacha_vazn = fields.Float(
        "O'rtacha vazn (kg)", digits='Product Unit',
        help="Bo'sh qoldirilsa manba partiyaning o'rtacha vazni olinadi.")
    tannarx_summa = fields.Monetary(
        "Ko'chirilgan tannarx", readonly=True, copy=False,
        help="Manba partiyaning 1 bosh tannarxi × bosh soni. "
             "Qo'lda kiritilmaydi.")

    holat = fields.Selection(
        [('draft', "Qoralama"), ('done', "O'tkazilgan")],
        string="Holati", default='draft', required=True, tracking=True,
        copy=False)
    mas_ul_id = fields.Many2one('hr.employee', string="Mas'ul xodim")
    izoh = fields.Text("Izoh")

    _bosh_musbat = models.Constraint(
        'CHECK (bosh_soni > 0)', "Bosh soni noldan katta bo'lishi kerak.")

    # ------------------------------------------------------------- compute
    @api.depends('manba_partiya_id')
    def _compute_company_id(self):
        for o in self:
            o.company_id = o.manba_partiya_id.company_id or self.env.company

    # ----------------------------------------------------------- validatsiya
    @api.constrains('manba_partiya_id', 'qabul_partiya_id')
    def _check_partiyalar(self):
        for o in self:
            if o.manba_partiya_id == o.qabul_partiya_id:
                raise ValidationError(_(
                    "«%s»: manba va qabul qiluvchi partiya bir xil bo'lmaydi.",
                    o.display_name))
            if o.manba_partiya_id.company_id != o.qabul_partiya_id.company_id:
                raise ValidationError(_(
                    "«%s»: partiyalar turli korxonalarga tegishli — "
                    "o'tkazma qilib bo'lmaydi.", o.display_name))

    @api.constrains('bosh_soni', 'manba_partiya_id')
    def _check_bosh_soni(self):
        for o in self:
            if o.holat == 'draft' and o.bosh_soni > o.manba_partiya_id.joriy_son:
                raise ValidationError(_(
                    "«%(nom)s»: o'tkazilayotgan bosh soni (%(otk)s) manba "
                    "partiyadagi tirik sondan (%(tirik)s) ko'p.",
                    nom=o.display_name, otk=o.bosh_soni,
                    tirik=o.manba_partiya_id.joriy_son))

    @api.onchange('manba_partiya_id')
    def _onchange_manba(self):
        if self.manba_partiya_id and not self.ortacha_vazn:
            self.ortacha_vazn = self.manba_partiya_id.ortacha_vazn

    # ------------------------------------------------------------ yaratish
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _("Yangi"):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'agronova.boquv.otkazma') or _("Yangi")
        return super().create(vals_list)

    # ----------------------------------------------------------- o'tkazish
    def action_otkazish(self):
        """Bosh sonini va tannarxni ikkala partiya orasida ko'chiradi."""
        for o in self:
            if o.holat != 'draft':
                raise UserError(_("Faqat qoralama o'tkazma bajariladi."))
            manba, qabul = o.manba_partiya_id, o.qabul_partiya_id
            manba._tekshir_ochiq(_("o'tkazma (chiqim)"))
            qabul._tekshir_ochiq(_("o'tkazma (kirim)"))

            # Tannarx — manba partiyaning joriy birlik tannarxidan.
            manba.invalidate_recordset(['tannarx_1_bosh'])
            o.tannarx_summa = manba.tannarx_1_bosh * o.bosh_soni

            # Bosh soni: manbadan chiqadi, qabul qiluvchiga qo'shiladi.
            manba.chiqim_son += o.bosh_soni
            qabul.boshlangich_son += o.bosh_soni

            if o.tannarx_summa:
                # Manbada teskari — tannarx chiqib ketdi.
                manba._agronova_post_analytic(
                    name=_("O'tkazma → %(bino)s: %(bosh)s bosh",
                           bino=qabul.bino_id.display_name, bosh=o.bosh_soni),
                    amount=abs(o.tannarx_summa),
                    date=o.sana,
                    tannarxga=False,
                )
                # Qabul qiluvchida xarajat — tannarx kirdi.
                qabul._agronova_post_analytic(
                    name=_("O'tkazma ← %(bino)s: %(bosh)s bosh",
                           bino=manba.bino_id.display_name, bosh=o.bosh_soni),
                    amount=-abs(o.tannarx_summa),
                    date=o.sana,
                    unit_amount=o.bosh_soni,
                )

            o.holat = 'done'
            xabar = _(
                "O'tkazma: %(bosh)s bosh, tannarx %(summa)s. "
                "%(manba)s → %(qabul)s.",
                bosh=o.bosh_soni, summa=o.tannarx_summa,
                manba=manba.display_name, qabul=qabul.display_name)
            o.message_post(body=xabar)
            manba.message_post(body=xabar)
            qabul.message_post(body=xabar)
        return True

    def action_storno(self):
        for o in self:
            if o.holat != 'done':
                raise UserError(_("Faqat o'tkazilgan hujjat storno qilinadi."))
            manba, qabul = o.manba_partiya_id, o.qabul_partiya_id
            bugun = fields.Date.context_today(o)
            manba.chiqim_son -= o.bosh_soni
            qabul.boshlangich_son -= o.bosh_soni
            if o.tannarx_summa:
                manba._agronova_post_analytic(
                    name=_("STORNO: o'tkazma %s", o.name),
                    amount=-abs(o.tannarx_summa),
                    date=bugun, tannarxga=False)
                qabul._agronova_post_analytic(
                    name=_("STORNO: o'tkazma %s", o.name),
                    amount=abs(o.tannarx_summa),
                    date=bugun, tannarxga=False)
            o.holat = 'draft'
            o.message_post(body=_("O'tkazma storno qilindi."))
        return True

    def write(self, vals):
        qulf_tashqari = {'holat', 'tannarx_summa', 'izoh',
                         'message_follower_ids', 'message_ids'}
        if set(vals) - qulf_tashqari:
            for o in self:
                if o.holat == 'done':
                    raise UserError(_(
                        "«%s» o'tkazmasi bajarilgan — tahrirlanmaydi. "
                        "Storno qiling.", o.display_name))
        return super().write(vals)

    def unlink(self):
        if any(o.holat != 'draft' for o in self):
            raise UserError(_("Faqat qoralama o'tkazma o'chiriladi."))
        return super().unlink()
