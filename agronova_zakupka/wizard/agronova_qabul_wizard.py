# -*- coding: utf-8 -*-
"""Omborchi qabuli va uch o'lchovli baholash (TZ 7-bo'lim).

Baho **bitta raqam emas** — uchta o'lcham alohida qo'yiladi:

* to'liqlik — miqdor to'g'ri keldimi (10 ta so'ralib 9 tasi kelsa 9 ball);
* muddat — vaqtida keldimi;
* sifat — talabga mos keldimi.

Har bir ballga **sabab majburiy**: zakupchik aybi (KPI ga salbiy ta'sir),
obyektiv sabab (ta'sir yo'q) yoki nizoli (bo'lim rahbari hal qiladi).
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.agronova_zakupka.models.agronova_kirim import BALL_SABABI


class AgroNovaQabulWizard(models.TransientModel):
    _name = 'agronova.qabul.wizard'
    _description = "Tovarni qabul qilish va baholash"

    kirim_id = fields.Many2one(
        'agronova.kirim', string="Kirim hujjati", required=True,
        ondelete='cascade')
    zakupchik_id = fields.Many2one(
        'res.users', related='kirim_id.zakupchik_id', readonly=True)
    maqsad_ombor_id = fields.Many2one(
        'stock.warehouse', related='kirim_id.maqsad_ombor_id', readonly=True)
    qator_ids = fields.One2many(
        'agronova.qabul.wizard.qatori', 'wizard_id', string="Qatorlar")

    ball_toliqlik = fields.Integer(
        "To'liqlik (0..10)", default=10,
        compute='_compute_ball_toliqlik', store=True, readonly=False,
        help="Miqdor bo'yicha baho. So'ralgan va kelgan miqdor nisbatidan "
             "avtomat taklif qilinadi, omborchi o'zgartirishi mumkin.")
    ball_muddat = fields.Integer("Muddat (0..10)", required=True, default=10)
    ball_sifat = fields.Integer("Sifat (0..10)", required=True, default=10)
    ball_sababi = fields.Selection(
        BALL_SABABI, string="Ball sababi", required=True,
        default='obyektiv_sabab',
        help="Har bir ballga sabab majburiy — TZ 7-bo'lim.")
    ball_izohi = fields.Text("Izoh")

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        kirim_id = vals.get('kirim_id') or self.env.context.get(
            'default_kirim_id')
        if kirim_id and 'qator_ids' in fields_list:
            kirim = self.env['agronova.kirim'].browse(kirim_id)
            vals['qator_ids'] = [(0, 0, {
                'kirim_qatori_id': q.id,
                'product_id': q.product_id.id,
                'soralgan_miqdor': q.miqdor,
                'qabul_miqdor': q.miqdor,
                'lot_nomi': q.lot_nomi,
                'yaroqlilik_sanasi': q.yaroqlilik_sanasi,
            }) for q in kirim.qator_ids]
        return vals

    @api.depends('qator_ids.soralgan_miqdor', 'qator_ids.qabul_miqdor')
    def _compute_ball_toliqlik(self):
        for wiz in self:
            soralgan = sum(wiz.qator_ids.mapped('soralgan_miqdor'))
            qabul = sum(wiz.qator_ids.mapped('qabul_miqdor'))
            wiz.ball_toliqlik = round(
                10.0 * min(qabul, soralgan) / soralgan) if soralgan else 10

    @api.constrains('ball_toliqlik', 'ball_muddat', 'ball_sifat', 'ball_izohi',
                    'ball_sababi')
    def _check_ballar(self):
        for wiz in self:
            for ball in (wiz.ball_toliqlik, wiz.ball_muddat, wiz.ball_sifat):
                if not 0 <= ball <= 10:
                    raise ValidationError(_(
                        "Ball 0 dan 10 gacha bo'lishi kerak."))
            toliq = (wiz.ball_toliqlik == 10 and wiz.ball_muddat == 10
                     and wiz.ball_sifat == 10)
            if not toliq and not wiz.ball_izohi:
                raise ValidationError(_(
                    "To'liq bo'lmagan ballga izoh majburiy — zakupchik nima "
                    "uchun ball yo'qotganini bilishi kerak (TZ 7-bo'lim)."))

    def action_qabul_qilish(self):
        self.ensure_one()
        if not self.qator_ids.filtered(lambda q: q.qabul_miqdor > 0):
            raise UserError(_(
                "Hech bo'lmasa bitta qatorda qabul miqdori bo'lishi kerak."))
        for qator in self.qator_ids:
            qator.kirim_qatori_id.write({
                'qabul_miqdor': qator.qabul_miqdor,
                'lot_nomi': qator.lot_nomi,
                'yaroqlilik_sanasi': qator.yaroqlilik_sanasi,
            })
        self.kirim_id._agronova_qabul_yakunlash({
            'ball_toliqlik': self.ball_toliqlik,
            'ball_muddat': self.ball_muddat,
            'ball_sifat': self.ball_sifat,
            'ball_sababi': self.ball_sababi,
            'ball_izohi': self.ball_izohi,
        })
        return {'type': 'ir.actions.act_window_close'}


class AgroNovaQabulWizardQatori(models.TransientModel):
    _name = 'agronova.qabul.wizard.qatori'
    _description = "Qabul qilish qatori"

    wizard_id = fields.Many2one(
        'agronova.qabul.wizard', string="Wizard", required=True, ondelete='cascade')
    kirim_qatori_id = fields.Many2one(
        'agronova.kirim.qatori', string="Kirim qatori", required=True)
    product_id = fields.Many2one(
        'product.product', string="Tovar", readonly=True)
    soralgan_miqdor = fields.Float("Sotib olingan", readonly=True)
    qabul_miqdor = fields.Float("Qabul qilinadi", required=True)
    lot_nomi = fields.Char("Lot / seriya")
    yaroqlilik_sanasi = fields.Datetime("Yaroqlilik muddati")
    kuzatuv_shart = fields.Boolean(
        "Kuzatuv majburiy", related='product_id.seriya_kuzatuv_shart',
        readonly=True)

    @api.constrains('qabul_miqdor', 'soralgan_miqdor')
    def _check_miqdor(self):
        for qator in self:
            if qator.qabul_miqdor < 0:
                raise ValidationError(_("Qabul miqdori manfiy bo'lmaydi."))
            if qator.qabul_miqdor > qator.soralgan_miqdor:
                raise ValidationError(_(
                    "«%s»: sotib olingandan ko'p qabul qilib bo'lmaydi.",
                    qator.product_id.display_name))
