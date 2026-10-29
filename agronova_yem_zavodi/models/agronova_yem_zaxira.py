# -*- coding: utf-8 -*-
"""Xomashyo zaxirasi holati (TZ 6.3).

Minimum va maksimum Odoo'ning standart «qayta buyurtma qoidalari»da
(`stock.warehouse.orderpoint`) turadi — xarid moduli ham shu qoidalardan
foydalanadi. Bu yerda ular **o'rtacha sarf** bilan birlashtiriladi:
qoldiq necha kunga yetadi, rejadagi buyurtmalar qancha oladi, xarid
qachon kelishi kerak.

Jadval har soatda (cron) va «Yangilash» tugmasida qayta hisoblanadi —
hisobot tez ochilishi uchun natija saqlanadi.
"""
from datetime import timedelta

from odoo import _, api, fields, models

KUN = 30


class AgroNovaYemZaxira(models.Model):
    _name = 'agronova.yem.zaxira'
    _description = "Yem zavodi — xomashyo zaxirasi"
    _order = 'holat_tartib, yetadi_kun, id'

    company_id = fields.Many2one('res.company', "Korxona", required=True, default=lambda s: s.env.company)
    warehouse_id = fields.Many2one('stock.warehouse', "Ombor", required=True)
    product_id = fields.Many2one('product.product', "Xomashyo", required=True)
    yem_turi = fields.Selection(related='product_id.agronova_yem_turi', store=True)
    qoldiq_kg = fields.Float("Qoldiq (kg)", digits=(16, 0))
    min_kg = fields.Float("Minimum (kg)", digits=(16, 0))
    max_kg = fields.Float("Maksimum (kg)", digits=(16, 0))
    sarf_kg = fields.Float("Sarf, 30 kun (kg)", digits=(16, 0))
    kunlik_kg = fields.Float("O'rtacha kunlik (kg)", digits=(16, 0))
    yetadi_kun = fields.Float("Yetadi (kun)", digits=(16, 1))
    rejadagi_kg = fields.Float("Rejadagi buyurtmalarga (kg)", digits=(16, 0),
                               help="Tasdiqlangan, lekin hali yopilmagan buyurtmalar uchun kerak.")
    kutilayotgan_kg = fields.Float("Kutilayotgan xarid (kg)", digits=(16, 0))
    xarid_kerak_kg = fields.Float("Xarid kerak (kg)", digits=(16, 0),
                                  help="Maksimumgacha to'ldirish uchun: max − (qoldiq + kutilayotgan − rejadagi).")
    holat = fields.Selection([
        ('kritik', "Minimumdan past"), ('kam', "Tugash arafasida"),
        ('normal', "Me'yorda"), ('ortiqcha', "Maksimumdan ortiq"),
    ], "Holati")
    holat_tartib = fields.Integer()
    yangilangan = fields.Datetime("Yangilangan")

    @api.model
    def action_yangilash(self):
        """Jadvalni qayta hisoblaydi (barcha korxonalar, cron uchun ham)."""
        P = self.env['product.product']
        Move = self.env['stock.move'].sudo()
        now = fields.Datetime.now()
        dan = now - timedelta(days=KUN)
        tartib = {'kritik': 0, 'kam': 1, 'normal': 2, 'ortiqcha': 3}
        for company in self.env['res.company'].sudo().search([]):
            mahsulotlar = P.sudo().search([
                ('agronova_yem_turi', 'in', ('xomashyo', 'premiks', 'qadoq')),
                ('is_storable', '=', True),
                ('company_id', 'in', [False, company.id]),
            ])
            vals = []
            for wh in self.env['stock.warehouse'].sudo().search([('company_id', '=', company.id)]):
                loc = wh.lot_stock_id
                for p in mahsulotlar:
                    pc = p.with_context(location=loc.id)
                    op = self.env['stock.warehouse.orderpoint'].sudo().search([
                        ('product_id', '=', p.id), ('warehouse_id', '=', wh.id)], limit=1)
                    qoldiq = P._agronova_kg(pc.qty_available, p.uom_id)
                    kutil = P._agronova_kg(pc.incoming_qty, p.uom_id)
                    minimum = P._agronova_kg(op.product_min_qty, op.product_uom) if op else 0.0
                    maksimum = P._agronova_kg(op.product_max_qty, op.product_uom) if op else 0.0
                    sarf_moves = Move.search([
                        ('product_id', '=', p.id), ('state', '=', 'done'),
                        ('raw_material_production_id', '!=', False),
                        ('date', '>=', dan), ('location_id', 'child_of', wh.view_location_id.id),
                    ])
                    sarf = sum(P._agronova_kg(m.quantity, m.product_uom) for m in sarf_moves)
                    reja_moves = Move.search([
                        ('product_id', '=', p.id), ('state', 'not in', ('done', 'cancel', 'draft')),
                        ('raw_material_production_id', '!=', False),
                        ('location_id', 'child_of', wh.view_location_id.id),
                    ])
                    rejadagi = sum(P._agronova_kg(m.product_uom_qty - m.quantity, m.product_uom)
                                   for m in reja_moves if m.product_uom_qty > m.quantity)
                    if not (qoldiq or sarf or minimum or rejadagi or kutil):
                        continue
                    kunlik = sarf / KUN
                    yetadi = (qoldiq / kunlik) if kunlik else 999.0
                    erkin = qoldiq + kutil - rejadagi
                    if minimum and qoldiq < minimum:
                        holat = 'kritik'
                    elif (minimum and qoldiq < minimum * 1.25) or (kunlik and yetadi < 7):
                        holat = 'kam'
                    elif maksimum and qoldiq > maksimum:
                        holat = 'ortiqcha'
                    else:
                        holat = 'normal'
                    vals.append({
                        'company_id': company.id, 'warehouse_id': wh.id, 'product_id': p.id,
                        'qoldiq_kg': qoldiq, 'min_kg': minimum, 'max_kg': maksimum,
                        'sarf_kg': sarf, 'kunlik_kg': kunlik, 'yetadi_kun': min(yetadi, 999.0),
                        'rejadagi_kg': rejadagi, 'kutilayotgan_kg': kutil,
                        'xarid_kerak_kg': max((maksimum or minimum) - erkin, 0.0) if (maksimum or minimum) else 0.0,
                        'holat': holat, 'holat_tartib': tartib[holat], 'yangilangan': now,
                    })
            self.sudo().search([('company_id', '=', company.id)]).unlink()
            self.sudo().create(vals)
        return True

    def action_yangilash_btn(self):
        self.action_yangilash()
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    @api.model
    def _cron_yangilash(self):
        oldingi_kritik = set(self.search([('holat', '=', 'kritik')]).mapped('product_id').ids)
        self.action_yangilash()
        yangi = self.search([('holat', '=', 'kritik'), ('product_id', 'not in', list(oldingi_kritik))])
        if yangi:
            yangi._ogohlantir()

    def _ogohlantir(self):
        """Minimumdan pastga tushgan xomashyo — omborchi va boshliqqa vazifa."""
        guruhlar = [self.env.ref(x, raise_if_not_found=False) for x in (
            'agronova_yem_zavodi.group_yem_omborchi', 'agronova_yem_zavodi.group_yem_boshliq')]
        users = self.env['res.users']
        for g in guruhlar:
            if g:
                users |= g.user_ids
        if not users:
            return
        model_id = self.env['ir.model']._get_id('product.product')
        for z in self:
            for u in users[:5]:
                self.env['mail.activity'].sudo().create({
                    'res_model_id': model_id, 'res_id': z.product_id.id,
                    'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                    'user_id': u.id,
                    'summary': _("Xomashyo minimumdan past: %s", z.product_id.display_name),
                    'note': _("Qoldiq %(q)s kg, minimum %(m)s kg, %(k)s kunga yetadi.",
                              q=round(z.qoldiq_kg), m=round(z.min_kg), k=round(z.yetadi_kun, 1)),
                })

    def action_xarid_talabi(self):
        """Tanlangan xomashyo uchun RFQ — asosiy yetkazib beruvchi bo'yicha."""
        P = self.env['product.product']
        PO = self.env['purchase.order']
        guruh = {}
        for z in self.filtered(lambda r: r.xarid_kerak_kg > 0):
            seller = z.product_id._select_seller(quantity=z.xarid_kerak_kg)
            if seller:
                guruh.setdefault((seller.partner_id, z.warehouse_id), []).append(z)
        pos = PO
        for (partner, wh), qatorlar in guruh.items():
            pos |= PO.create({
                'partner_id': partner.id, 'picking_type_id': wh.in_type_id.id,
                'origin': _("Zaxira nazorati"),
                'order_line': [(0, 0, {
                    'product_id': z.product_id.id,
                    'product_qty': P._agronova_kg_dan(z.xarid_kerak_kg, z.product_id.uom_id),
                }) for z in qatorlar],
            })
        return {
            'type': 'ir.actions.act_window', 'res_model': 'purchase.order', 'name': _("Xarid talablari"),
            'view_mode': 'list,form', 'domain': [('id', 'in', pos.ids)],
        }
