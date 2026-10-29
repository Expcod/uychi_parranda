# -*- coding: utf-8 -*-
"""Smena hisoboti (TZ 3.5).

Smena boshlig'i raqamlarni qaytadan yozmaydi: fakt, xomashyo, qadoq,
yo'qotish va to'xtashlar shu smenaga bog'langan hujjatlardan yig'iladi.
Qo'lda kiritiladigani — reja, ishchilar, izoh.

Tasdiqlangan hisobot o'zgartirilmaydi. Xato topilsa boshliq «Tuzatish
uchun ochish» tugmasini sabab bilan bosadi — sabab va kim ochgani
chatterda qoladi, hisobot qayta tasdiqlanadi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

ERKIN = {'state', 'tasdiqlagan_id', 'tasdiq_vaqt', 'tuzatish_sabab', 'tuzatish_soni',
         'message_main_attachment_id', 'activity_ids'}


class AgroNovaYemSmena(models.Model):
    _name = 'agronova.yem.smena'
    _description = "Yem zavodi — smena hisoboti"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sana desc, smena_turi_id, liniya_id'

    name = fields.Char("Nomi", compute='_compute_name', store=True)
    company_id = fields.Many2one('res.company', "Korxona", required=True, default=lambda s: s.env.company)
    sana = fields.Date("Sana", required=True, default=fields.Date.context_today, tracking=True)
    smena_turi_id = fields.Many2one('agronova.yem.smena.turi', "Smena", required=True, tracking=True)
    liniya_id = fields.Many2one('agronova.yem.liniya', "Liniya", required=True, tracking=True)
    boshliq_id = fields.Many2one('hr.employee', "Smena boshlig'i", tracking=True)
    ishchi_ids = fields.Many2many('hr.employee', string="Ishchilar")
    state = fields.Selection([('draft', "Ochiq"), ('tasdiqlangan', "Tasdiqlangan")],
                             "Holat", default='draft', required=True, tracking=True)
    tasdiqlagan_id = fields.Many2one('res.users', "Tasdiqlagan", readonly=True)
    tasdiq_vaqt = fields.Datetime("Tasdiq vaqti", readonly=True)
    tuzatish_sabab = fields.Text("Tuzatish sababi")
    tuzatish_soni = fields.Integer("Tuzatishlar", readonly=True)
    izoh = fields.Text("Izoh")
    bot_kiritdi = fields.Boolean("Botdan kiritilgan", readonly=True)

    reja_kg = fields.Float("Reja (kg)", digits=(16, 0), tracking=True,
                           help="Bo'sh qoldirilsa smenaga biriktirilgan buyurtmalar rejasidan olinadi.")
    production_ids = fields.One2many('mrp.production', 'agronova_smena_id', "Buyurtmalar")
    qadoqlash_ids = fields.One2many('agronova.yem.qadoqlash', 'smena_id', "Qadoqlash")
    yoqotish_ids = fields.One2many('agronova.yem.yoqotish', 'smena_id', "Yo'qotishlar")
    toxtash_ids = fields.One2many('agronova.yem.toxtash', 'smena_id', "To'xtashlar")
    energiya_ids = fields.One2many('agronova.yem.energiya', 'smena_id', "Energiya")

    rejadagi_kg = fields.Float("Buyurtmalar rejasi (kg)", compute='_compute_korsatkich', store=True,
                               digits=(16, 0))
    fakt_kg = fields.Float("Ishlab chiqarildi (kg)", compute='_compute_korsatkich', store=True, digits=(16, 0))
    xomashyo_kg = fields.Float("Xomashyo sarfi (kg)", compute='_compute_korsatkich', store=True,
                               digits=(16, 0))
    qadoqlangan_kg = fields.Float("Qadoqlandi (kg)", compute='_compute_korsatkich', store=True, digits=(16, 0))
    qop_soni = fields.Integer("Qoplar", compute='_compute_korsatkich', store=True)
    yoqotish_kg = fields.Float("Yo'qotish (kg)", compute='_compute_korsatkich', store=True, digits=(16, 1))
    brak_kg = fields.Float("Brak (kg)", compute='_compute_korsatkich', store=True, digits=(16, 1))
    toxtash_min = fields.Integer("To'xtash (daq.)", compute='_compute_korsatkich', store=True)
    bajarilish = fields.Float("Rejaning bajarilishi (%)", compute='_compute_korsatkich', store=True,
                              digits=(16, 1))
    farq_kg = fields.Float("Rejadan farq (kg)", compute='_compute_korsatkich', store=True, digits=(16, 0))
    samaradorlik = fields.Float("Liniya samaradorligi (%)", compute='_compute_korsatkich', store=True,
                                digits=(16, 1),
                                help="Fakt / (liniya quvvati × smena soati). To'xtashlar shuni pasaytiradi.")
    ochiq_buyurtma = fields.Integer("Yopilmagan buyurtmalar", compute='_compute_korsatkich', store=True)

    _smena_uniq = models.Constraint('unique(sana, smena_turi_id, liniya_id, company_id)',
                                    "Shu kun, smena va liniya uchun hisobot allaqachon bor.")

    @api.depends('sana', 'smena_turi_id', 'liniya_id')
    def _compute_name(self):
        for s in self:
            s.name = " · ".join(x for x in (
                s.liniya_id.name, s.sana and s.sana.strftime('%d.%m.%Y'), s.smena_turi_id.name) if x)

    @api.depends('reja_kg', 'production_ids.state', 'production_ids.product_qty',
                 'production_ids.agronova_miqdor_kg', 'production_ids.agronova_kirim_kg',
                 'qadoqlash_ids.state', 'qadoqlash_ids.netto_kg', 'qadoqlash_ids.qop_soni',
                 'yoqotish_ids.state', 'yoqotish_ids.miqdor_kg', 'yoqotish_ids.turi',
                 'toxtash_ids.davomiylik_min', 'liniya_id.quvvat_t_soat', 'smena_turi_id.davomiylik')
    def _compute_korsatkich(self):
        P = self.env['product.product']
        for s in self:
            mos = s.production_ids.filtered(lambda m: m.state != 'cancel')
            done = mos.filtered(lambda m: m.state == 'done')
            rejadagi = sum(P._agronova_kg(m.product_qty, m.product_uom_id) for m in mos)
            s.rejadagi_kg = rejadagi
            s.fakt_kg = sum(done.mapped('agronova_miqdor_kg'))
            s.xomashyo_kg = sum(mos.mapped('agronova_kirim_kg'))
            q = s.qadoqlash_ids.filtered(lambda r: r.state == 'tasdiqlangan')
            s.qadoqlangan_kg = sum(q.mapped('netto_kg'))
            s.qop_soni = sum(q.mapped('qop_soni'))
            y = s.yoqotish_ids.filtered(lambda r: r.state != 'rad')
            s.yoqotish_kg = sum(y.mapped('miqdor_kg'))
            s.brak_kg = sum(y.filtered(lambda r: r.turi == 'brak').mapped('miqdor_kg'))
            s.toxtash_min = int(sum(s.toxtash_ids.mapped('davomiylik_min')))
            reja = s.reja_kg or rejadagi
            s.bajarilish = (s.fakt_kg / reja * 100.0) if reja else 0.0
            s.farq_kg = s.fakt_kg - reja
            quvvat_kg = (s.liniya_id.quvvat_t_soat or 0.0) * 1000.0 * (s.smena_turi_id.davomiylik or 0.0)
            s.samaradorlik = (s.fakt_kg / quvvat_kg * 100.0) if quvvat_kg else 0.0
            s.ochiq_buyurtma = len(mos.filtered(lambda m: m.state not in ('done', 'cancel')))

    # ------------------------------------------------------------------ himoya
    def write(self, vals):
        if set(vals) - ERKIN and not self.env.context.get('agronova_smena_ruxsat'):
            for s in self:
                if s.state == 'tasdiqlangan':
                    raise UserError(_("«%s» smena hisoboti tasdiqlangan — o'zgartirish uchun "
                                      "boshliq uni tuzatishga ochishi kerak.", s.name))
        return super().write(vals)

    def unlink(self):
        if any(s.state == 'tasdiqlangan' for s in self):
            raise UserError(_("Tasdiqlangan smena hisobotini o'chirib bo'lmaydi."))
        return super().unlink()

    @api.model_create_multi
    def create(self, vals_list):
        smenalar = super().create(vals_list)
        smenalar._buyurtmalarni_bogla()
        return smenalar

    def _buyurtmalarni_bogla(self):
        """Shu kun/liniya/smenadagi bog'lanmagan buyurtmalarni biriktiradi."""
        Mrp = self.env['mrp.production']
        for s in self:
            for mo in Mrp.search([
                ('agronova_liniya_id', '=', s.liniya_id.id),
                ('agronova_smena_turi_id', '=', s.smena_turi_id.id),
                ('agronova_smena_id', '=', False), ('state', '!=', 'cancel'),
            ]):
                if mo._agronova_sana() == s.sana:
                    mo.with_context(agronova_smena_bogla=True).agronova_smena_id = s

    # ---------------------------------------------------------------- amallar
    def action_tasdiqlash(self):
        if not self.env.user.has_group('agronova_yem_zavodi.group_yem_smena_boshligi'):
            raise UserError(_("Smena hisobotini smena boshlig'i tasdiqlaydi."))
        for s in self:
            if s.ochiq_buyurtma:
                raise UserError(_("%(n)s: %(k)s ta buyurtma hali yopilmagan. Avval buyurtmalarni "
                                  "yakunlang yoki keyingi smenaga o'tkazing.", n=s.name, k=s.ochiq_buyurtma))
            s.write({'state': 'tasdiqlangan', 'tasdiqlagan_id': self.env.user.id,
                     'tasdiq_vaqt': fields.Datetime.now()})
            s.message_post(body=_(
                "Smena tasdiqlandi: fakt %(f)s kg (reja %(r)s%%), qadoqlandi %(q)s kg, "
                "to'xtash %(t)s daq.", f=round(s.fakt_kg), r=round(s.bajarilish, 1),
                q=round(s.qadoqlangan_kg), t=s.toxtash_min))
        return True

    def action_tuzatishga_ochish(self):
        if not self.env.user.has_group('agronova_yem_zavodi.group_yem_boshliq'):
            raise UserError(_("Tasdiqlangan smenani faqat ishlab chiqarish boshlig'i ochadi."))
        for s in self:
            if not (s.tuzatish_sabab or '').strip():
                raise UserError(_("Tuzatish sababini yozing."))
            s.write({'state': 'draft', 'tuzatish_soni': s.tuzatish_soni + 1})
            s.message_post(body=_("Tuzatish uchun ochildi (%(kim)s). Sabab: %(s)s",
                                  kim=self.env.user.name, s=s.tuzatish_sabab))
            s.tuzatish_sabab = False
        return True

    def action_buyurtmalarni_bogla(self):
        self._buyurtmalarni_bogla()
        return True
