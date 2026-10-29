# -*- coding: utf-8 -*-
"""Yangi nomenklatura so'rovi (TZ 11-bo'lim).

Zakupchik bazada yo'q tovarni topsa, uni o'zi yaratmaydi — so'rov beradi.
Mas'ul xodim bazada o'xshash tovar bor-yo'qligini tekshiradi va tasdiqlaydi;
tasdiqlangandan keyingina `product.template` yaratiladi.

Takroriy nom yaratilmasligi uchun tizim o'xshash nomlarni ko'rsatadi.
Murakkab fuzzy-matching shart emas (TZ 11): so'zma-so'z `ilike` yetarli.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .res_partner import XARAJAT_TURI


class AgroNovaNomenklaturaSorovi(models.Model):
    _name = 'agronova.nomenklatura.sorovi'
    _description = "Yangi nomenklatura so'rovi"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    name = fields.Char(
        "So'rov raqami", default=lambda self: _("Yangi"),
        copy=False, readonly=True, index=True)
    nom = fields.Char("Tovar nomi", required=True, tracking=True)
    olchov_birligi_id = fields.Many2one(
        'uom.uom', string="O'lchov birligi", required=True, tracking=True)
    kategoriya_id = fields.Many2one(
        'product.category', string="Kategoriya", required=True, tracking=True)
    xarajat_turi = fields.Selection(
        XARAJAT_TURI, string="Xarajat turi", tracking=True)
    izoh = fields.Text("Izoh")
    surat = fields.Binary("Surat", attachment=True)
    surat_filename = fields.Char("Fayl nomi")
    sorovchi_id = fields.Many2one(
        'res.users', string="So'rovchi", required=True, tracking=True,
        default=lambda self: self.env.user)
    tekshiruvchi_id = fields.Many2one(
        'res.users', string="Tekshiruvchi", readonly=True, copy=False)
    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True,
        default=lambda self: self.env.company)

    holat = fields.Selection(
        [('draft', "Qoralama"),
         ('tekshirilmoqda', "Tekshirilmoqda"),
         ('tasdiqlandi', "Tasdiqlandi"),
         ('rad_etildi', "Rad etildi")],
        string="Holati", default='draft', required=True, tracking=True, copy=False)
    rad_sababi = fields.Text("Rad sababi", tracking=True)
    product_tmpl_id = fields.Many2one(
        'product.template', string="Yaratilgan tovar", readonly=True, copy=False)

    oxshash_ids = fields.Many2many(
        'product.template', string="O'xshash tovarlar",
        compute='_compute_oxshash_ids',
        help="Bazadagi shunga o'xshash nomlar — takror yaratmaslik uchun.")
    oxshash_soni = fields.Integer(
        "O'xshash soni", compute='_compute_oxshash_ids')

    @api.depends('nom')
    def _compute_oxshash_ids(self):
        Tmpl = self.env['product.template']
        for rec in self:
            if not rec.nom or len(rec.nom.strip()) < 3:
                rec.oxshash_ids = Tmpl
                rec.oxshash_soni = 0
                continue
            # Nomni so'zlarga bo'lib, har bir ma'noli so'z bo'yicha qidiramiz:
            # «kartoshka urug'i» ni «urug' kartoshka» dan ajratib bermaydi,
            # lekin takrorni ushlash uchun shu yetarli (TZ 11).
            sozlar = [s for s in rec.nom.replace(',', ' ').split() if len(s) >= 3]
            domain = ['|'] * (len(sozlar) - 1) if len(sozlar) > 1 else []
            domain += [('name', 'ilike', s) for s in sozlar] or [
                ('name', 'ilike', rec.nom)]
            oxshash = Tmpl.search(domain, limit=10)
            rec.oxshash_ids = oxshash
            rec.oxshash_soni = len(oxshash)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _("Yangi")) == _("Yangi"):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'agronova.nomenklatura.sorovi') or _("Yangi")
        return super().create(vals_list)

    def action_tekshirishga_yuborish(self):
        for rec in self:
            if rec.holat != 'draft':
                raise UserError(_("Faqat qoralama so'rov yuboriladi."))
            rec.holat = 'tekshirilmoqda'
            rec.message_post(body=_(
                "Tekshirishga yuborildi. Bazada %s ta o'xshash nom topildi.",
                rec.oxshash_soni))
        return True

    def action_tasdiqlash(self):
        # Tasdiqlash huquqi shu modulning ACL si bilan boshqariladi;
        # tovarni yaratish uchun alohida «Products/Create» guruhi
        # talab qilinmaydi — tasdiqning o'zi ruxsat.
        Tmpl = self.env['product.template'].sudo()
        for rec in self:
            if rec.holat != 'tekshirilmoqda':
                raise UserError(_("Faqat tekshirilayotgan so'rov tasdiqlanadi."))
            tmpl = Tmpl.create({
                'name': rec.nom,
                'uom_id': rec.olchov_birligi_id.id,
                'categ_id': rec.kategoriya_id.id,
                'xarajat_turi': rec.xarajat_turi or False,
                'is_storable': rec.xarajat_turi != 'xizmat',
                'type': 'service' if rec.xarajat_turi == 'xizmat' else 'consu',
                'purchase_ok': True,
                'description_purchase': rec.izoh or False,
                'image_1920': rec.surat or False,
            })
            rec.write({
                'holat': 'tasdiqlandi',
                'product_tmpl_id': tmpl.id,
                'tekshiruvchi_id': self.env.user.id,
            })
            rec.message_post(body=_(
                "Tasdiqlandi, nomenklaturaga qo'shildi: %s", tmpl.display_name))
        return True

    def action_rad_etish(self):
        for rec in self:
            if not rec.rad_sababi:
                raise UserError(_("Rad etish sababini yozing."))
            rec.write({'holat': 'rad_etildi',
                       'tekshiruvchi_id': self.env.user.id})
        return True

    @api.constrains('holat', 'product_tmpl_id')
    def _check_tasdiq(self):
        for rec in self:
            if rec.holat == 'tasdiqlandi' and not rec.product_tmpl_id:
                raise ValidationError(_(
                    "Tasdiqlangan so'rovda yaratilgan tovar bo'lishi shart."))
