# -*- coding: utf-8 -*-
"""Ishlab chiqarish rejasi (TZ 3.1).

Reja → qatorlar (mahsulot, kg, muddat, ustuvorlik, liniya) →
«Xomashyoni tekshirish» retseptura bo'yicha ehtiyojni ombor qoldig'i va
kutilayotgan xarid bilan solishtiradi → yetishmayotgani uchun xarid
talabi → «Buyurtmalar yaratish» har qator uchun ishlab chiqarish
buyurtmasi ochadi. Fakt yopilgan buyurtmalardan yig'iladi, shuning uchun
reja-fakt doim hujjatlarga mos.
"""
from collections import defaultdict
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

USTUVORLIK = [('0', "Oddiy"), ('1', "Yuqori"), ('2', "Shoshilinch")]


class AgroNovaYemReja(models.Model):
    _name = 'agronova.yem.reja'
    _description = "Yem zavodi — ishlab chiqarish rejasi"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sana_dan desc, id desc'

    name = fields.Char("Raqam", required=True, copy=False, readonly=True, default=lambda s: _("Yangi"))
    company_id = fields.Many2one('res.company', "Korxona", required=True, default=lambda s: s.env.company)
    davr = fields.Selection([('kunlik', "Kunlik"), ('haftalik', "Haftalik"), ('oylik', "Oylik")],
                            "Davr", required=True, default='kunlik', tracking=True)
    sana_dan = fields.Date("Boshlanishi", required=True, default=fields.Date.context_today, tracking=True)
    sana_gacha = fields.Date("Tugashi", required=True, default=fields.Date.context_today, tracking=True)
    warehouse_id = fields.Many2one('stock.warehouse', "Ombor", required=True,
                                   default=lambda s: s.env['stock.warehouse'].search(
                                       [('company_id', '=', s.env.company.id)], limit=1))
    state = fields.Selection([
        ('draft', "Loyiha"), ('tasdiqlangan', "Tasdiqlangan"), ('jarayonda', "Bajarilmoqda"),
        ('yakunlangan', "Yakunlangan"), ('bekor', "Bekor"),
    ], "Holat", default='draft', required=True, tracking=True, copy=False)
    qator_ids = fields.One2many('agronova.yem.reja.qator', 'reja_id', "Reja qatorlari", copy=True)
    ehtiyoj_ids = fields.One2many('agronova.yem.reja.ehtiyoj', 'reja_id', "Xomashyo ehtiyoji")
    ehtiyoj_tekshirildi = fields.Datetime("Xomashyo tekshirilgan", readonly=True, copy=False)
    izoh = fields.Text("Izoh")

    reja_kg = fields.Float("Reja (kg)", compute='_compute_jami', store=True, digits=(16, 0))
    fakt_kg = fields.Float("Fakt (kg)", compute='_compute_jami', store=True, digits=(16, 0))
    bajarilish = fields.Float("Bajarilish (%)", compute='_compute_jami', store=True, digits=(16, 1))
    yetishmaydi = fields.Boolean("Xomashyo yetishmaydi", compute='_compute_yetishmaydi', store=True)
    yuklama = fields.Float("Liniyalar yuklamasi (%)", compute='_compute_yuklama', digits=(16, 1),
                           help="Rejalashtirilgan hajm liniyalarning davrdagi quvvatiga nisbati "
                                "(smenalar soni × smena soati × quvvat t/soat).")
    kechikkan_soni = fields.Integer("Kechikkan qatorlar", compute='_compute_jami', store=True)

    @api.model_create_multi
    def create(self, vals_list):
        for v in vals_list:
            if v.get('name', _("Yangi")) == _("Yangi"):
                v['name'] = self.env['ir.sequence'].next_by_code('agronova.yem.reja') or _("Yangi")
        return super().create(vals_list)

    @api.onchange('davr', 'sana_dan')
    def _onchange_davr(self):
        if not self.sana_dan:
            return
        if self.davr == 'kunlik':
            self.sana_gacha = self.sana_dan
        elif self.davr == 'haftalik':
            self.sana_gacha = self.sana_dan + timedelta(days=6)
        else:
            self.sana_gacha = self.sana_dan + relativedelta(months=1, days=-1)

    @api.constrains('sana_dan', 'sana_gacha')
    def _check_sana(self):
        for r in self:
            if r.sana_gacha < r.sana_dan:
                raise UserError(_("Tugash sanasi boshlanishidan oldin bo'lishi mumkin emas."))

    @api.depends('qator_ids.miqdor_kg', 'qator_ids.fakt_kg', 'qator_ids.holat')
    def _compute_jami(self):
        for r in self:
            r.reja_kg = sum(r.qator_ids.mapped('miqdor_kg'))
            r.fakt_kg = sum(r.qator_ids.mapped('fakt_kg'))
            r.bajarilish = (r.fakt_kg / r.reja_kg * 100.0) if r.reja_kg else 0.0
            r.kechikkan_soni = len(r.qator_ids.filtered(lambda q: q.holat == 'kechikmoqda'))

    @api.depends('ehtiyoj_ids.yetishmaydi_kg')
    def _compute_yetishmaydi(self):
        for r in self:
            r.yetishmaydi = any(e.yetishmaydi_kg > 0 for e in r.ehtiyoj_ids)

    def _compute_yuklama(self):
        smena_soat = sum(self.env['agronova.yem.smena.turi'].search([]).mapped('davomiylik')) or 12.0
        for r in self:
            kunlar = (r.sana_gacha - r.sana_dan).days + 1 if r.sana_gacha and r.sana_dan else 1
            liniyalar = r.qator_ids.mapped('liniya_id') or self.env['agronova.yem.liniya'].search(
                [('company_id', '=', r.company_id.id)])
            quvvat_t = sum(liniyalar.mapped('quvvat_t_soat')) * smena_soat * kunlar
            r.yuklama = (r.reja_kg / 1000.0 / quvvat_t * 100.0) if quvvat_t else 0.0

    # ----------------------------------------------------------------- amallar
    def action_tasdiqlash(self):
        for r in self:
            if not r.qator_ids:
                raise UserError(_("Rejada qator yo'q."))
            r.action_xomashyo_tekshir()
            r.state = 'tasdiqlangan'
        return True

    def action_bekor(self):
        self.write({'state': 'bekor'})

    def action_loyiha(self):
        self.write({'state': 'draft'})

    def action_xomashyo_tekshir(self):
        """Retseptura bo'yicha xomashyo ehtiyoji va ombordagi holat."""
        P = self.env['product.product']
        for r in self:
            kerak = defaultdict(float)
            for q in r.qator_ids:
                bom = q.bom_id
                if not bom or not bom.product_qty:
                    continue
                bom_kg = P._agronova_kg(bom.product_qty, bom.product_uom_id) or bom.product_qty
                qolgan = max(q.miqdor_kg - q.fakt_kg, 0.0)
                for line in bom.bom_line_ids:
                    kerak[line.product_id] += \
                        P._agronova_kg(line.product_qty, line.product_uom_id) * qolgan / bom_kg
            loc = r.warehouse_id.lot_stock_id
            vals = [(5, 0, 0)]
            for product, kg in sorted(kerak.items(), key=lambda kv: -kv[1]):
                p = product.with_context(location=loc.id)
                mavjud = P._agronova_kg(p.free_qty, product.uom_id)
                kutilmoqda = P._agronova_kg(p.incoming_qty, product.uom_id)
                vals.append((0, 0, {
                    'product_id': product.id, 'kerak_kg': kg,
                    'mavjud_kg': mavjud, 'kutilayotgan_kg': kutilmoqda,
                }))
            r.write({'ehtiyoj_ids': vals, 'ehtiyoj_tekshirildi': fields.Datetime.now()})
        return True

    def action_buyurtmalar_yarat(self):
        Mrp = self.env['mrp.production']
        P = self.env['product.product']
        yaratildi = Mrp
        for r in self:
            if r.state not in ('tasdiqlangan', 'jarayonda'):
                raise UserError(_("Avval rejani tasdiqlang."))
            for q in r.qator_ids.filtered(lambda x: not x.production_ids):
                if not q.bom_id:
                    raise UserError(_("«%s» uchun tasdiqlangan retseptura yo'q.", q.product_id.display_name))
                qty = P._agronova_kg_dan(q.miqdor_kg, q.product_id.uom_id)
                muddat = fields.Datetime.to_datetime(q.muddat or r.sana_gacha)
                boshlanish = fields.Datetime.to_datetime(q.muddat or r.sana_dan)
                if q.smena_turi_id:
                    boshlanish = boshlanish.replace(hour=int(q.smena_turi_id.boshlanish))
                mo = Mrp.create({
                    'product_id': q.product_id.id,
                    'product_qty': qty,
                    'product_uom_id': q.product_id.uom_id.id,
                    'bom_id': q.bom_id.id,
                    'date_start': boshlanish,
                    'date_deadline': muddat.replace(hour=23, minute=0),
                    'priority': '1' if q.ustuvorlik != '0' else '0',
                    'agronova_liniya_id': q.liniya_id.id,
                    'agronova_smena_turi_id': q.smena_turi_id.id,
                    'agronova_reja_qator_id': q.id,
                    'origin': r.name,
                    'company_id': r.company_id.id,
                })
                yaratildi |= mo
            r.state = 'jarayonda'
        if yaratildi:
            yaratildi.action_confirm()
        return self.action_buyurtmalar()

    def action_buyurtmalar(self):
        action = self.env['ir.actions.act_window']._for_xml_id('mrp.mrp_production_action')
        action['domain'] = [('agronova_reja_qator_id.reja_id', 'in', self.ids)]
        action['context'] = {}
        return action

    def action_xarid_talabi(self):
        """Yetishmayotgan xomashyo uchun xarid so'rovi (RFQ) — asosiy
        yetkazib beruvchi bo'yicha guruhlab. Yetkazib beruvchisi yo'q
        mahsulotlar haqida xabar qoladi."""
        PO = self.env['purchase.order']
        P = self.env['product.product']
        yaratildi = PO
        for r in self:
            vendor_qator = defaultdict(list)
            sotuvchisiz = []
            for e in r.ehtiyoj_ids.filtered(lambda x: x.yetishmaydi_kg > 0):
                seller = e.product_id._select_seller(quantity=e.yetishmaydi_kg)
                if not seller:
                    sotuvchisiz.append(e.product_id.display_name)
                    continue
                vendor_qator[seller.partner_id].append(e)
            for partner, qatorlar in vendor_qator.items():
                po = PO.create({
                    'partner_id': partner.id,
                    'origin': r.name,
                    'company_id': r.company_id.id,
                    'picking_type_id': r.warehouse_id.in_type_id.id,
                    'order_line': [(0, 0, {
                        'product_id': e.product_id.id,
                        'product_qty': P._agronova_kg_dan(e.yetishmaydi_kg, e.product_id.uom_id),
                    }) for e in qatorlar],
                })
                yaratildi |= po
            if sotuvchisiz:
                r.message_post(body=_("Yetkazib beruvchisi ko'rsatilmagan xomashyo: %s",
                                      ", ".join(sotuvchisiz)))
        if not yaratildi:
            raise UserError(_("Xarid talabi yaratilmadi: yetishmayotgan xomashyo yo'q yoki "
                              "yetkazib beruvchilar ko'rsatilmagan."))
        return {
            'type': 'ir.actions.act_window', 'res_model': 'purchase.order', 'name': _("Xarid talablari"),
            'view_mode': 'list,form', 'domain': [('id', 'in', yaratildi.ids)],
        }

    @api.model
    def _cron_kechikish(self):
        """Muddati o'tgan, lekin bajarilmagan qatorlar bo'yicha boshliqqa vazifa."""
        guruh = self.env.ref('agronova_yem_zavodi.group_yem_boshliq', raise_if_not_found=False)
        users = guruh.user_ids[:3] if guruh else self.env['res.users']
        for r in self.search([('state', 'in', ('tasdiqlangan', 'jarayonda'))]):
            if r.kechikkan_soni and users and not r.activity_ids:
                for u in users:
                    r.activity_schedule('mail.mail_activity_data_todo', user_id=u.id,
                                        summary=_("Reja kechikmoqda: %s qator", r.kechikkan_soni))


class AgroNovaYemRejaQator(models.Model):
    _name = 'agronova.yem.reja.qator'
    _description = "Ishlab chiqarish rejasi qatori"
    _order = 'ustuvorlik desc, muddat, id'

    reja_id = fields.Many2one('agronova.yem.reja', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='reja_id.company_id', store=True)
    product_id = fields.Many2one('product.product', "Yem", required=True,
                                 domain="[('agronova_yem_turi', '=', 'yem')]")
    product_tmpl_id = fields.Many2one(related='product_id.product_tmpl_id')
    bom_id = fields.Many2one('mrp.bom', "Retseptura", compute='_compute_bom', store=True, readonly=False,
                             domain="[('product_tmpl_id', '=', product_tmpl_id),"
                                    " ('agronova_holat', '=', 'tasdiqlangan')]")
    miqdor_kg = fields.Float("Reja (kg)", required=True, digits=(16, 0))
    muddat = fields.Date("Muddat")
    ustuvorlik = fields.Selection(USTUVORLIK, "Ustuvorlik", default='0', required=True)
    liniya_id = fields.Many2one('agronova.yem.liniya', "Liniya")
    smena_turi_id = fields.Many2one('agronova.yem.smena.turi', "Smena")
    production_ids = fields.One2many('mrp.production', 'agronova_reja_qator_id', "Buyurtmalar")
    fakt_kg = fields.Float("Fakt (kg)", compute='_compute_fakt', store=True, digits=(16, 0))
    bajarilish = fields.Float("Bajarilish (%)", compute='_compute_fakt', store=True, digits=(16, 1))
    holat = fields.Selection([
        ('rejada', "Rejada"), ('jarayonda', "Jarayonda"), ('toxtatilgan', "To'xtatilgan"),
        ('bajarildi', "Bajarildi"), ('kechikmoqda', "Kechikmoqda"),
    ], "Holati", compute='_compute_fakt', store=True)
    soat = fields.Float("Kerakli vaqt (soat)", compute='_compute_soat', digits=(16, 1))

    @api.depends('product_id')
    def _compute_bom(self):
        for q in self:
            q.bom_id = self.env['mrp.bom'].search([
                ('product_tmpl_id', '=', q.product_id.product_tmpl_id.id),
                ('agronova_holat', '=', 'tasdiqlangan'),
            ], limit=1) if q.product_id else False

    @api.depends('production_ids.state', 'production_ids.agronova_miqdor_kg', 'miqdor_kg', 'muddat')
    def _compute_fakt(self):
        bugun = fields.Date.context_today(self)
        for q in self:
            mos = q.production_ids.filtered(lambda m: m.state != 'cancel')
            fakt = sum(mos.filtered(lambda m: m.state == 'done').mapped('agronova_miqdor_kg'))
            q.fakt_kg = fakt
            q.bajarilish = (fakt / q.miqdor_kg * 100.0) if q.miqdor_kg else 0.0
            if q.miqdor_kg and fakt >= q.miqdor_kg * 0.98:
                q.holat = 'bajarildi'
            elif q.muddat and q.muddat < bugun:
                q.holat = 'kechikmoqda'
            elif mos.filtered(lambda m: m.state in ('progress', 'to_close')):
                q.holat = 'jarayonda'
            elif mos and all(m.state == 'draft' for m in mos):
                q.holat = 'toxtatilgan'
            elif mos.filtered(lambda m: m.state == 'confirmed') or fakt:
                q.holat = 'jarayonda'
            else:
                q.holat = 'rejada'

    @api.depends('miqdor_kg', 'liniya_id.quvvat_t_soat')
    def _compute_soat(self):
        for q in self:
            quvvat = q.liniya_id.quvvat_t_soat
            q.soat = (q.miqdor_kg / 1000.0 / quvvat) if quvvat else 0.0


class AgroNovaYemRejaEhtiyoj(models.Model):
    _name = 'agronova.yem.reja.ehtiyoj'
    _description = "Reja bo'yicha xomashyo ehtiyoji"
    _order = 'yetishmaydi_kg desc, kerak_kg desc'

    reja_id = fields.Many2one('agronova.yem.reja', required=True, ondelete='cascade', index=True)
    product_id = fields.Many2one('product.product', "Xomashyo", required=True)
    kerak_kg = fields.Float("Kerak (kg)", digits=(16, 1))
    mavjud_kg = fields.Float("Omborda bo'sh (kg)", digits=(16, 1))
    kutilayotgan_kg = fields.Float("Kutilayotgan xarid (kg)", digits=(16, 1))
    yetishmaydi_kg = fields.Float("Yetishmaydi (kg)", compute='_compute_holat', store=True, digits=(16, 1))
    holat = fields.Selection([('yetarli', "Yetarli"), ('xarid', "Xarid kutilmoqda"), ('yoq', "Yetishmaydi")],
                             "Holati", compute='_compute_holat', store=True)

    @api.depends('kerak_kg', 'mavjud_kg', 'kutilayotgan_kg')
    def _compute_holat(self):
        for e in self:
            kam = e.kerak_kg - e.mavjud_kg
            if kam <= 0:
                e.holat, e.yetishmaydi_kg = 'yetarli', 0.0
            elif kam <= e.kutilayotgan_kg:
                e.holat, e.yetishmaydi_kg = 'xarid', 0.0
            else:
                e.holat, e.yetishmaydi_kg = 'yoq', kam - e.kutilayotgan_kg
