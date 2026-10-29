# -*- coding: utf-8 -*-
"""Narx normasi — uch qatlamli mexanizm (TZ 6-bo'lim).

    1-qatlam: oxirgi N xaridning o'rtacha narxi (xarid tarixi)
       -> (tarix yo'q)
    2-qatlam: kategoriya limit narxi (admin qo'ygan chegara)
       -> (ikkalasi ham yo'q)
    3-qatlam: «Birinchi xarid» rejimi — kamida 3 ta taklif solishtiriladi,
              tasdiqlangan narx avtomat norma narxga aylanadi.

Norma narx **yozib qo'yiladi** (`agronova.narx.normasi`), chunki:
* «birinchi xarid» natijasini boshqa saqlaydigan joy yo'q;
* narxning qachon o'rnatilgani kerak — eskirganda ogohlantirish shundan;
* tarix qatlami har safar qayta hisoblanadi va yozuvni yangilab turadi.
"""
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models

MANBA = [
    ('xarid_tarixi', "Xarid tarixi"),
    ('kategoriya_limiti', "Kategoriya limiti"),
    ('birinchi_xarid', "Birinchi xarid (taklif solishtirildi)"),
    ('qolda', "Qo'lda kiritilgan"),
]


class AgroNovaNarxNormasi(models.Model):
    _name = 'agronova.narx.normasi'
    _description = "Xarid — norma narx"
    _inherit = ['mail.thread']
    _order = 'sana desc, id desc'
    _rec_name = 'product_id'

    product_id = fields.Many2one(
        'product.product', string="Tovar", required=True,
        ondelete='cascade', index=True)
    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)
    norma_narx = fields.Monetary("Norma narx", required=True, tracking=True)
    sana = fields.Date(
        "O'rnatilgan sana", required=True, tracking=True,
        default=fields.Date.context_today)
    manba = fields.Selection(
        MANBA, string="Manba", required=True, default='xarid_tarixi',
        tracking=True)
    manba_izoh = fields.Char("Manba izohi")
    eski = fields.Boolean(
        "Eskirgan", compute='_compute_eski', search='_search_eski',
        help="Sozlamadagi muddatdan (masalan 6 oy) eski — qayta "
             "tekshirilishi kerak.")

    _product_company_uniq = models.Constraint(
        'UNIQUE(product_id, company_id)',
        "Bir tovar uchun bitta amaldagi norma narx bo'ladi.",
    )

    # ---------------------------------------------------------------- eski
    @api.model
    def _agronova_eskirish_sanasi(self):
        oy = int(self.env['ir.config_parameter'].sudo().get_param(
            'agronova_zakupka.narx_eskirish_oy', 6) or 6)
        return fields.Date.context_today(self) - relativedelta(months=oy)

    def _compute_eski(self):
        chegara = self._agronova_eskirish_sanasi()
        for rec in self:
            rec.eski = bool(rec.sana and rec.sana < chegara)

    def _search_eski(self, operator, value):
        if operator not in ('=', '!=') or not isinstance(value, bool):
            raise NotImplementedError(_("Bu filtr faqat ha/yo'q bilan ishlaydi."))
        chegara = self._agronova_eskirish_sanasi()
        if (operator == '=') == value:
            return [('sana', '<', chegara)]
        return [('sana', '>=', chegara)]

    # --------------------------------------------------------- 1-qatlam
    @api.model
    def _agronova_tarix_narxi(self, product):
        """Oxirgi N tasdiqlangan xaridning o'rtacha narxi.

        Manba — o'z kirim hujjatlarimiz; ular bo'lmasa Odoo standart
        xarid buyurtmalari (Vendor Pricelist ham shulardan quriladi).
        """
        soni = int(self.env['ir.config_parameter'].sudo().get_param(
            'agronova_zakupka.narx_tarixi_soni', 5) or 5)
        qatorlar = self.env['agronova.kirim.qatori'].sudo().search([
            ('product_id', '=', product.id),
            ('kirim_id.holat', 'in', ('tasdiqlangan', 'qabul_qilindi')),
        ], order='id desc', limit=soni)
        narxlar = [q.narx for q in qatorlar if q.narx > 0]
        if not narxlar:
            po_lines = self.env['purchase.order.line'].sudo().search([
                ('product_id', '=', product.id),
                ('state', 'in', ('purchase', 'done')),
            ], order='id desc', limit=soni)
            narxlar = [line.price_unit for line in po_lines if line.price_unit > 0]
        if not narxlar:
            return 0.0
        return sum(narxlar) / len(narxlar)

    # ------------------------------------------------------------- yadro
    @api.model
    def _agronova_norma(self, product):
        """Tovarning amaldagi norma narxi.

        Qaytaradi: `{'narx', 'manba', 'manba_nomi', 'sana', 'eski',
        'birinchi_xarid'}`. `birinchi_xarid=True` bo'lsa norma narx yo'q va
        ruxsat hujjatida kamida 3 ta taklif talab qilinadi.
        """
        if product and product._name == 'product.template':
            product = product.product_variant_id
        bosh = {'narx': 0.0, 'manba': False, 'manba_nomi': '',
                'sana': False, 'eski': False, 'birinchi_xarid': True}
        if not product:
            return bosh

        # 1-qatlam — xarid tarixi. Har safar qayta hisoblanadi: yangi xarid
        # bo'lgach norma o'zidan-o'zi siljiydi.
        tarix = self._agronova_tarix_narxi(product)
        if tarix:
            yozuv = self._agronova_yozuvni_yangilash(product, tarix, 'xarid_tarixi')
            return {'narx': tarix, 'manba': 'xarid_tarixi',
                    'manba_nomi': dict(MANBA)['xarid_tarixi'],
                    'sana': yozuv.sana, 'eski': yozuv.eski,
                    'birinchi_xarid': False}

        # Tarix yo'q — «birinchi xarid» natijasi yozilgan bo'lsa o'sha.
        yozuv = self.sudo().search([
            ('product_id', '=', product.id),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        if yozuv and yozuv.manba in ('birinchi_xarid', 'qolda'):
            return {'narx': yozuv.norma_narx, 'manba': yozuv.manba,
                    'manba_nomi': dict(MANBA)[yozuv.manba],
                    'sana': yozuv.sana, 'eski': yozuv.eski,
                    'birinchi_xarid': False}

        # 2-qatlam — kategoriya limiti.
        limit = product.categ_id._agronova_limit_narx()
        if limit:
            return {'narx': limit, 'manba': 'kategoriya_limiti',
                    'manba_nomi': dict(MANBA)['kategoriya_limiti'],
                    'sana': fields.Date.context_today(self), 'eski': False,
                    'birinchi_xarid': False}

        # 3-qatlam — norma yo'q, «birinchi xarid» rejimi.
        return bosh

    @api.model
    def _agronova_yozuvni_yangilash(self, product, narx, manba, izoh=None):
        """Norma yozuvini yaratadi yoki yangilaydi."""
        if product and product._name == 'product.template':
            product = product.product_variant_id
        yozuv = self.sudo().search([
            ('product_id', '=', product.id),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        vals = {
            'norma_narx': narx,
            'manba': manba,
            'sana': fields.Date.context_today(self),
            'manba_izoh': izoh or False,
        }
        if yozuv:
            # Tarix qatlami «birinchi xarid» yozuvining ustiga yozadi —
            # bu to'g'ri: real xarid bo'lgach taxminiy narx kerak emas.
            if yozuv.norma_narx != narx or yozuv.manba != manba:
                yozuv.write(vals)
        else:
            yozuv = self.sudo().create(dict(
                vals, product_id=product.id, company_id=self.env.company.id))
        return yozuv

    # -------------------------------------------------------------- cron
    @api.model
    def _cron_narx_eskirish(self):
        """Eskirgan norma narxlar bo'yicha xarid boshlig'iga eslatma."""
        eskilar = self.sudo().search(
            [('sana', '<', self._agronova_eskirish_sanasi())])
        if not eskilar:
            return True
        guruh = self.env.ref(
            'agronova_zakupka.group_zakupka_bolim_boshligi', raise_if_not_found=False)
        userlar = guruh.sudo().all_user_ids if guruh else self.env['res.users']
        for rec in eskilar:
            for user in userlar:
                rec.activity_schedule(
                    'mail.mail_activity_data_todo', user_id=user.id,
                    summary=_("Norma narx eskirdi: %s",
                              rec.product_id.display_name),
                    note=_("«%(tovar)s» norma narxi %(sana)s da o'rnatilgan "
                           "va eskirdi. Qayta tekshiring.",
                           tovar=rec.product_id.display_name, sana=rec.sana))
        return True
