# -*- coding: utf-8 -*-
"""So'yish partiyasi (TZ 12-band).

Har kelgan tovuq partiyasi alohida identifikatsiya qilinadi va uning
harakati boshdan oxirigacha kuzatiladi:

    qayerdan keldi -> qancha tortildi -> qancha so'yildi ->
    qancha tayyor mahsulot olindi -> qancha sotildi

Eng muhim ko'rsatkich — **chiqim foizi**: tirik vazndan necha foiz tayyor
mahsulot chiqdi. Odooda bunday ko'rsatkich yo'q, shuning uchun shu yerda
hisoblanadi.

Ikki manba ikki xil moliyaviy mantiq beradi:

* **ichki** — tovuq bizniki, tannarxi partiyaga tushadi, tayyor mahsulot
  ham bizniki bo'lib omborga kiradi;
* **tashqi** — tovuq mijozniki, biz faqat **xizmat haqi** olamiz
  (so'yilgan dona × narx). Mahsulot mijozga qaytariladi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .agronova_soyish_qabul import MANBA


class AgroNovaSoyishPartiya(models.Model):
    _name = 'agronova.soyish.partiya'
    _description = "So'yish partiyasi"
    _inherit = ['agronova.analitik.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'sana desc, id desc'
    _rec_names_search = ['name', 'partner_id.name']

    _agronova_analytic_plan_name = "So'yish partiyasi"

    name = fields.Char(
        "Partiya raqami", default=lambda self: _("Yangi"), copy=False,
        readonly=True, index=True)
    sana = fields.Date(
        "Sana", required=True, default=fields.Date.context_today, tracking=True)
    qabul_id = fields.Many2one(
        'agronova.soyish.qabul', string="Qabul hujjati", readonly=True,
        ondelete='restrict')
    manba = fields.Selection(MANBA, string="Kelib chiqishi", required=True,
                             default='ichki', tracking=True)
    partner_id = fields.Many2one(
        'res.partner', string="Mijoz / ferma", tracking=True)
    product_id = fields.Many2one(
        'product.product', string="Tirik tovuq mahsuloti")
    # Korxona qabul hujjatidan keladi, foydalanuvchining joriy korxonasidan
    # emas. Poda Ona tovuq bo'limidan avtomat kelganda hujjatni yaratuvchi
    # kontekst Ona tovuqda bo'ladi — shunda partiya ham noto'g'ri korxonaga
    # tushib, tirik tovuqni So'yish omboridan topolmay qolardi.
    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True, readonly=True,
        store=True, precompute=True, compute='_compute_company_id')
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)

    @api.depends('qabul_id')
    def _compute_company_id(self):
        for p in self:
            p.company_id = p.qabul_id.company_id or self.env.company
    holat = fields.Selection(
        [('active', "Jarayonda"), ('closed', "Yakunlangan")],
        string="Holati", default='active', required=True, tracking=True,
        copy=False)

    # --- kirish
    tirik_son = fields.Integer("Kelgan tovuq (dona)", tracking=True)
    tirik_vazn_kg = fields.Float(
        "Kelgan tirik vazn (kg)", tracking=True, digits='Product Unit')

    # --- so'yish natijasi
    jarayon_ids = fields.One2many(
        'agronova.soyish.jarayon', 'partiya_id', string="So'yish jarayonlari")
    soyilgan_son = fields.Integer(
        "So'yilgan (dona)", compute='_compute_natija', store=True)
    nobud_son = fields.Integer(
        "Nobud / brak (dona)", compute='_compute_natija', store=True)
    tushka_vazn_kg = fields.Float(
        "Olingan tayyor mahsulot (kg)", compute='_compute_natija', store=True,
        digits='Product Unit')
    chiqim_foiz = fields.Float(
        "Chiqim foizi (%)", compute='_compute_natija', store=True,
        help="Tayyor mahsulot vazni / kelgan tirik vazn × 100. "
             "Sanoatda odatda 70–75%.")
    ortacha_tushka_kg = fields.Float(
        "1 dona tushka o'rtacha (kg)", compute='_compute_natija', store=True,
        digits='Product Unit')

    # --- moliya
    jami_xarajat = fields.Monetary("Jami xarajat", compute='_compute_moliya')
    jami_daromad = fields.Monetary("Jami daromad", compute='_compute_moliya')
    foyda = fields.Monetary("Foyda / zarar", compute='_compute_moliya')
    tannarx_1_kg = fields.Monetary(
        "1 kg tannarxi", compute='_compute_moliya',
        help="Ishlab chiqarish xarajati / olingan tayyor mahsulot. "
             "Faqat ichki partiyada ma'noga ega.")
    xizmat_summa = fields.Monetary(
        "Xizmat haqi", compute='_compute_xizmat', store=True,
        help="Tashqi mijoz uchun: so'yilgan dona × 1 dona narxi.")
    xizmat_narx = fields.Monetary(
        "1 dona so'yish narxi", tracking=True,
        help="Tashqi mijozdan olinadigan xizmat haqi (TZ 5-band).")

    izoh = fields.Text("Izoh")

    # ------------------------------------------------------------- compute
    @api.depends('jarayon_ids.soyilgan_son', 'jarayon_ids.nobud_son',
                 'jarayon_ids.tushka_vazn_kg', 'jarayon_ids.holat',
                 'tirik_vazn_kg')
    def _compute_natija(self):
        for p in self:
            bajarilgan = p.jarayon_ids.filtered(lambda j: j.holat == 'done')
            p.soyilgan_son = sum(bajarilgan.mapped('soyilgan_son'))
            p.nobud_son = sum(bajarilgan.mapped('nobud_son'))
            p.tushka_vazn_kg = sum(bajarilgan.mapped('tushka_vazn_kg'))
            p.chiqim_foiz = (p.tushka_vazn_kg / p.tirik_vazn_kg * 100.0
                             if p.tirik_vazn_kg else 0.0)
            p.ortacha_tushka_kg = (p.tushka_vazn_kg / p.soyilgan_son
                                   if p.soyilgan_son else 0.0)

    @api.depends('soyilgan_son', 'xizmat_narx')
    def _compute_xizmat(self):
        for p in self:
            p.xizmat_summa = (p.soyilgan_son * p.xizmat_narx
                              if p.manba == 'tashqi' else 0.0)

    def _compute_moliya(self):
        for p in self:
            xarajat = p._agronova_analytic_amount(sign='cost')
            daromad = p._agronova_analytic_amount(sign='income')
            p.jami_xarajat = xarajat
            p.jami_daromad = daromad
            p.foyda = daromad - xarajat
            # Tannarx faqat ishlab chiqarish xarajatidan — sotilgan
            # mahsulotning tannarx chiqimi bu bazaga kirmaydi.
            ishlab_chiqarish = p._agronova_analytic_amount(
                sign='cost', faqat_tannarx=True)
            p.tannarx_1_kg = (ishlab_chiqarish / p.tushka_vazn_kg
                              if p.tushka_vazn_kg else 0.0)

    def _agronova_analytic_vals(self):
        vals = super()._agronova_analytic_vals()
        vals['name'] = self.name if self.name != _("Yangi") else self.display_name
        return vals

    @api.depends('name', 'partner_id', 'manba')
    def _compute_display_name(self):
        turlar = dict(MANBA)
        for p in self:
            qism = [p.name or ""]
            if p.partner_id:
                qism.append(p.partner_id.name)
            else:
                qism.append(turlar.get(p.manba, ""))
            p.display_name = " · ".join(x for x in qism if x)

    # ------------------------------------------------------------- yaratish
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _("Yangi"):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'agronova.soyish.partiya') or _("Yangi")
        return super().create(vals_list)

    # --------------------------------------------------------------- qulf
    def _tekshir_ochiq(self, amal=None):
        for p in self:
            if p.holat == 'closed':
                raise UserError(_(
                    "«%(nom)s» partiyasi yakunlangan — unga yangi yozuv "
                    "qo'shilmaydi.%(amal)s",
                    nom=p.name, amal=(_(" (%s)", amal) if amal else "")))
        return True

    def _agronova_post_analytic(self, *args, **kwargs):
        """Yakunlangandan keyin tannarx o'zgarmaydi, sotuv esa davom etadi."""
        amount = kwargs.get('amount')
        if amount is None and len(args) >= 2:
            amount = args[1]
        if kwargs.get('tannarxga', True) and (amount or 0.0) < 0:
            self._tekshir_ochiq()
        return super()._agronova_post_analytic(*args, **kwargs)

    # -------------------------------------------------------------- holat
    def action_yakunlash(self):
        for p in self:
            if p.holat != 'active':
                raise UserError(_("Faqat jarayondagi partiya yakunlanadi."))
            qoralama = p.jarayon_ids.filtered(lambda j: j.holat == 'draft')
            if qoralama:
                raise UserError(_(
                    "«%s» partiyasida tasdiqlanmagan so'yish hujjati bor.",
                    p.name))
            p.holat = 'closed'
            p.message_post(body=_(
                "Partiya yakunlandi. So'yilgan %(s)s dona, tayyor mahsulot "
                "%(kg).1f kg, chiqim %(c).2f%%",
                s=p.soyilgan_son, kg=p.tushka_vazn_kg, c=p.chiqim_foiz))
        return True

    def action_qayta_ochish(self):
        for p in self:
            if p.holat != 'closed':
                raise UserError(_("Faqat yakunlangan partiya qayta ochiladi."))
            p.holat = 'active'
        return True
