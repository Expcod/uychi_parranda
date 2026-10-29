# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .utils import uz_today


class AgroNovaKassaKun(models.Model):
    """Kassa kitobining bir kunlik varag'i.

    Har kuni birinchi yozuv kiritilganda avtomatik ochiladi. Smena oxirida
    kassir sanab olgan naqd pulni kiritib kunni yopadi — farq darhol
    ko'rinadi va chatterga yoziladi.

    TZ M04 «kun yopish majburiyati»: yopilmagan kun turgan bo'lsa kassir
    keyingi kunga yozuv kirita olmaydi. Shu qoida `_oldingi_kun_tekshir`
    da amalga oshirilgan — avtomatik yozuvlarni (to'lov, transfer) esa
    bloklamaydi, chunki ular buxgalteriyada allaqachon bo'lib o'tgan.
    """
    _name = 'agronova.kassa.kun'
    _description = "Kassa kitobi (kunlik varaq)"
    _order = 'date desc, kassa_id'
    _inherit = ['mail.thread']

    kassa_id = fields.Many2one(
        'agronova.kassa', string="Kassa", required=True, ondelete='cascade',
        index=True,
    )
    date = fields.Date(
        string="Sana", required=True, default=lambda self: uz_today(), index=True,
    )
    company_id = fields.Many2one(
        related='kassa_id.company_id', string="Korxona", store=True,
    )
    currency_id = fields.Many2one(
        related='kassa_id.currency_id', string="Valyuta",
    )
    state = fields.Selection([
        ('open', "Ochiq"),
        ('closed', "Yopilgan"),
    ], string="Holat", default='open', required=True, tracking=True, copy=False)

    harakat_ids = fields.One2many(
        'agronova.kassa.harakat', 'kun_id', string="Kunlik harakatlar",
    )

    opening = fields.Monetary(
        string="Kun boshidagi qoldiq", compute='_compute_summa',
        currency_field='currency_id',
    )
    total_kirim = fields.Monetary(
        string="Kunlik kirim", compute='_compute_summa',
        currency_field='currency_id',
    )
    total_chiqim = fields.Monetary(
        string="Kunlik chiqim", compute='_compute_summa',
        currency_field='currency_id',
    )
    closing = fields.Monetary(
        string="Kun oxiridagi qoldiq", compute='_compute_summa',
        currency_field='currency_id',
        help="Kun boshidagi qoldiq + kirim − chiqim. Kassada shuncha pul "
             "bo'lishi kerak.",
    )
    sanoq = fields.Monetary(
        string="Sanab olindi", currency_field='currency_id', copy=False,
        help="Smena oxirida kassada REAL sanab olingan naqd pul.",
    )
    farq = fields.Monetary(
        string="Farq", compute='_compute_summa', currency_field='currency_id',
        help="Sanab olingan pul − hisoblangan qoldiq. Manfiy = kamomad.",
    )
    closed_by_id = fields.Many2one(
        'res.users', string="Kim yopdi", readonly=True, copy=False,
    )
    closed_at = fields.Datetime(string="Yopilgan vaqt", readonly=True, copy=False)
    note = fields.Text(string="Izoh")

    _kassa_date_uniq = models.Constraint(
        "UNIQUE (kassa_id, date)",
        "Bu kassa va sana uchun kassa kitobi varag'i allaqachon mavjud.",
    )

    # ------------------------------------------------------------------
    # COMPUTE
    # ------------------------------------------------------------------

    @api.depends('kassa_id', 'date', 'sanoq', 'harakat_ids.amount',
                 'harakat_ids.direction', 'harakat_ids.state')
    def _compute_summa(self):
        for kun in self:
            ochilish = self._ochilish_qoldiq(kun.kassa_id, kun.date)
            harakatlar = kun.harakat_ids.filtered(lambda h: h.state == 'posted')
            kirim = sum(harakatlar.filtered(
                lambda h: h.direction == 'in').mapped('amount'))
            chiqim = sum(harakatlar.filtered(
                lambda h: h.direction == 'out').mapped('amount'))
            kun.opening = ochilish
            kun.total_kirim = kirim
            kun.total_chiqim = chiqim
            kun.closing = ochilish + kirim - chiqim
            kun.farq = (kun.sanoq or 0.0) - kun.closing

    @api.model
    def _ochilish_qoldiq(self, kassa, sana):
        """Kassaning `sana` kuni BOSHIDAGI qoldig'i."""
        if not kassa or not sana:
            return 0.0
        groups = self.env['agronova.kassa.harakat'].sudo()._read_group(
            [('kassa_id', '=', kassa.id), ('state', '=', 'posted'),
             ('date_day', '<', sana)],
            [], ['signed_amount:sum'],
        )
        oldingi = groups[0][0] if groups else 0.0
        return (kassa.opening_balance or 0.0) + (oldingi or 0.0)

    @api.depends('kassa_id', 'date')
    def _compute_display_name(self):
        for kun in self:
            kun.display_name = "%s — %s" % (kun.kassa_id.name or '', kun.date or '')

    # ------------------------------------------------------------------
    # YORDAMCHI
    # ------------------------------------------------------------------

    @api.model
    def _kun_topish(self, kassa, sana, yaratish=True):
        """Kassa+sana uchun kunlik varaqni topadi (kerak bo'lsa yaratadi)."""
        if not kassa or not sana:
            return self.browse()
        kun = self.sudo().search([
            ('kassa_id', '=', kassa.id), ('date', '=', sana),
        ], limit=1)
        if not kun and yaratish:
            kun = self.sudo().create({'kassa_id': kassa.id, 'date': sana})
        return kun

    @api.model
    def _oldingi_ochiq_kun(self, kassa, sana):
        """`sana` dan oldingi yopilmagan kun (bo'lmasa — bo'sh recordset)."""
        if not kassa or not sana:
            return self.browse()
        return self.sudo().search([
            ('kassa_id', '=', kassa.id),
            ('date', '<', sana),
            ('state', '=', 'open'),
        ], order='date', limit=1)

    # ------------------------------------------------------------------
    # ACTIONS
    # ------------------------------------------------------------------

    def action_yopish(self):
        for kun in self:
            if kun.state == 'closed':
                raise UserError(_("«%s» kuni allaqachon yopilgan.", kun.date))
            qoralama = kun.harakat_ids.filtered(lambda h: h.state == 'draft')
            if qoralama:
                raise UserError(_(
                    "Kunni yopishdan oldin %(soni)s ta qoralama yozuvni "
                    "tasdiqlang yoki o'chiring: %(royxat)s",
                    soni=len(qoralama),
                    royxat=', '.join(qoralama.mapped('name'))))
            kun.write({
                'state': 'closed',
                'closed_by_id': self.env.user.id,
                'closed_at': fields.Datetime.now(),
            })
            kun.message_post(body=_(
                "Kun yopildi. Hisob bo'yicha: %(hisob)s, sanab olindi: "
                "%(sanoq)s, farq: %(farq)s.",
                hisob=kun.closing, sanoq=kun.sanoq, farq=kun.farq))
            if not kun.currency_id.is_zero(kun.farq):
                kun.message_post(body=_(
                    "⚠ Kassada farq chiqdi (%(farq)s). Sabab: %(izoh)s",
                    farq=kun.farq, izoh=kun.note or _("ko'rsatilmagan")))
        return True

    def action_ochish(self):
        """Yopilgan kunni qayta ochish — faqat menejer yoki bosh buxgalter."""
        if not (self.env.user.has_group('agronova_kassa.group_agronova_kassa_menejer')
                or self.env.user.has_group('agronova_base.group_agronova_bosh_buxgalter')):
            raise UserError(_(
                "Yopilgan kunni faqat kassa menejeri yoki bosh buxgalter "
                "qayta ocha oladi."))
        for kun in self:
            kun.write({'state': 'open', 'closed_by_id': False, 'closed_at': False})
            kun.message_post(body=_("Kun qayta ochildi."))
        return True

    def action_open_harakat(self):
        self.ensure_one()
        return {
            'name': _("%(kassa)s — %(sana)s", kassa=self.kassa_id.name,
                      sana=self.date),
            'type': 'ir.actions.act_window',
            'res_model': 'agronova.kassa.harakat',
            'views': [(False, 'list'), (False, 'form')],
            'domain': [('kun_id', '=', self.id)],
            'context': {'default_kassa_id': self.kassa_id.id},
        }

    def action_print_kitob(self):
        return self.env.ref(
            'agronova_kassa.action_report_kassa_kitobi').report_action(self)

    # ------------------------------------------------------------------
    # HISOBOT UCHUN
    # ------------------------------------------------------------------

    def _kitob_qatorlari(self):
        """Kassa kitobi shakli uchun tartiblangan qatorlar."""
        self.ensure_one()
        return self.harakat_ids.filtered(
            lambda h: h.state == 'posted').sorted(key=lambda h: (h.date, h.id))
