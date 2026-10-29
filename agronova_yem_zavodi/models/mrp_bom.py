# -*- coding: utf-8 -*-
"""Retseptura versiyalari (TZ 3.2).

Qoida oddiy: **tasdiqlangan retseptura o'zgarmaydi.** Me'yor o'zgarsa
texnolog «Yangi versiya» tugmasini bosadi — nusxa `loyiha` holatida
ochiladi, tahrirlanadi va tasdiqlanadi. Yangi versiya tasdiqlanganda
eskisi arxivga tushadi (o'chirilmaydi). Shunda:

* o'tgan buyurtmalar qaysi me'yor bilan ishlanganini hech qachon
  yo'qotmaydi (buyurtma o'z `bom_id` siga bog'liq);
* «kim, qachon, nimani o'zgartirdi» savoliga javob — versiyalar ro'yxati
  va chatter.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

TAHRIR_ERKIN = {'agronova_holat', 'active', 'sequence', 'agronova_tasdiqlagan_id',
                'agronova_tasdiq_sana', 'message_main_attachment_id'}


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    agronova_versiya = fields.Integer("Versiya", default=1, copy=False, tracking=True)
    agronova_versiya_nomi = fields.Char("Versiya", compute='_compute_agronova_versiya_nomi')
    agronova_holat = fields.Selection([
        ('loyiha', "Loyiha"),
        ('tasdiqlangan', "Tasdiqlangan"),
        ('arxiv', "Arxiv"),
    ], "Retseptura holati", default='loyiha', required=True, copy=False, tracking=True)
    agronova_tasdiqlagan_id = fields.Many2one('res.users', "Tasdiqlagan", readonly=True, copy=False,
                                              tracking=True)
    agronova_tasdiq_sana = fields.Datetime("Tasdiq sanasi", readonly=True, copy=False)
    agronova_avvalgi_id = fields.Many2one('mrp.bom', "Avvalgi versiya", readonly=True, copy=False)
    agronova_yoqotish_foiz = fields.Float(
        "Standart yo'qotish (%)", default=1.5, tracking=True, digits=(16, 2),
        help="Texnologik jarayon uchun tasdiqlangan yo'qotish me'yori: berilgan xomashyoning "
             "necha foizi tayyor mahsulotga aylanmaydi.")
    agronova_chiqim_foiz = fields.Float("Kutilayotgan chiqim (%)", compute='_compute_agronova_chiqim',
                                        digits=(16, 2))
    agronova_partiya_kg = fields.Float("Partiya hajmi (kg)", compute='_compute_agronova_chiqim',
                                       digits=(16, 1))
    agronova_komponent_kg = fields.Float("Komponentlar jami (kg)", compute='_compute_agronova_chiqim',
                                         digits=(16, 1))
    agronova_izoh = fields.Text("Texnolog izohi")

    @api.depends('agronova_versiya')
    def _compute_agronova_versiya_nomi(self):
        for b in self:
            b.agronova_versiya_nomi = "v%s" % (b.agronova_versiya or 1)

    @api.depends('agronova_yoqotish_foiz', 'product_qty', 'product_uom_id',
                 'bom_line_ids.product_qty', 'bom_line_ids.product_uom_id')
    def _compute_agronova_chiqim(self):
        P = self.env['product.product']
        for b in self:
            b.agronova_chiqim_foiz = 100.0 - (b.agronova_yoqotish_foiz or 0.0)
            b.agronova_partiya_kg = P._agronova_kg(b.product_qty, b.product_uom_id)
            b.agronova_komponent_kg = sum(
                P._agronova_kg(l.product_qty, l.product_uom_id) for l in b.bom_line_ids)

    def _compute_display_name(self):
        super()._compute_display_name()
        for b in self:
            if b.agronova_holat:
                b.display_name = "%s · v%s" % (b.display_name, b.agronova_versiya or 1)

    # ------------------------------------------------------------------ himoya
    def _agronova_texnolog(self):
        return self.env.user.has_group('agronova_yem_zavodi.group_yem_texnolog') \
            or self.env.su

    def write(self, vals):
        cheklangan = set(vals) - TAHRIR_ERKIN
        if cheklangan and not self.env.context.get('agronova_bom_ruxsat'):
            for b in self:
                if b.agronova_holat in ('tasdiqlangan', 'arxiv'):
                    raise UserError(_(
                        "«%(b)s» retsepturasi tasdiqlangan — uni o'zgartirib bo'lmaydi. "
                        "Me'yor o'zgarsa «Yangi versiya» tugmasini bosing.", b=b.display_name))
        if 'agronova_holat' in vals and not self._agronova_texnolog():
            raise UserError(_("Retseptura holatini faqat texnolog o'zgartiradi."))
        return super().write(vals)

    def unlink(self):
        for b in self:
            if b.agronova_holat != 'loyiha' or self.env['mrp.production'].search_count(
                    [('bom_id', '=', b.id)], limit=1):
                raise UserError(_("Ishlatilgan yoki tasdiqlangan retseptura o'chirilmaydi — "
                                  "arxivlang."))
        return super().unlink()

    # ---------------------------------------------------------------- amallar
    def action_agronova_tasdiqlash(self):
        if not self._agronova_texnolog():
            raise UserError(_("Retsepturani faqat texnolog tasdiqlaydi."))
        for b in self:
            if b.agronova_holat != 'loyiha':
                continue
            if not b.bom_line_ids:
                raise UserError(_("Komponentsiz retsepturani tasdiqlab bo'lmaydi."))
            # Shu mahsulotning avvalgi tasdiqlangan versiyalari arxivga tushadi.
            eskilar = self.search([
                ('product_tmpl_id', '=', b.product_tmpl_id.id),
                ('agronova_holat', '=', 'tasdiqlangan'),
                ('id', '!=', b.id), ('company_id', 'in', [False, b.company_id.id]),
            ])
            eskilar.with_context(agronova_bom_ruxsat=True).write(
                {'agronova_holat': 'arxiv', 'active': False})
            b.with_context(agronova_bom_ruxsat=True).write({
                'agronova_holat': 'tasdiqlangan',
                'agronova_tasdiqlagan_id': self.env.user.id,
                'agronova_tasdiq_sana': fields.Datetime.now(),
                'sequence': 1,
            })
            b.message_post(body=_("Retseptura v%(v)s tasdiqlandi (%(kim)s).",
                                  v=b.agronova_versiya, kim=self.env.user.name))
        return True

    def action_agronova_yangi_versiya(self):
        self.ensure_one()
        if not self._agronova_texnolog():
            raise UserError(_("Yangi versiyani faqat texnolog ochadi."))
        oxirgi = self.with_context(active_test=False).search(
            [('product_tmpl_id', '=', self.product_tmpl_id.id)],
            order='agronova_versiya desc', limit=1)
        yangi = self.with_context(agronova_bom_ruxsat=True).copy({
            'agronova_versiya': (oxirgi.agronova_versiya or 1) + 1,
            'agronova_holat': 'loyiha',
            'agronova_avvalgi_id': self.id,
            'active': True,
            'sequence': 50,
        })
        yangi.message_post(body=_("v%(v)s asosida yangi versiya ochildi.", v=self.agronova_versiya))
        return {
            'type': 'ir.actions.act_window', 'res_model': 'mrp.bom', 'res_id': yangi.id,
            'view_mode': 'form', 'target': 'current',
        }

    def action_agronova_versiyalar(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _("Retseptura versiyalari"),
            'res_model': 'mrp.bom', 'view_mode': 'list,form',
            'domain': [('product_tmpl_id', '=', self.product_tmpl_id.id)],
            'context': {'active_test': False},
        }


class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'

    agronova_ogish_foiz = fields.Float(
        "Ruxsat etilgan og'ish (%)", default=2.0, digits=(16, 2),
        help="Haqiqiy sarf reja miqdoridan shuncha foizgacha farq qilsa — me'yorda. "
             "Oshsa, buyurtma boshliq tasdig'isiz yopilmaydi.")
    agronova_ulush = fields.Float("Ulushi (%)", compute='_compute_agronova_ulush', digits=(16, 2))

    @api.depends('product_qty', 'product_uom_id', 'bom_id.bom_line_ids.product_qty')
    def _compute_agronova_ulush(self):
        P = self.env['product.product']
        for line in self:
            jami = sum(P._agronova_kg(l.product_qty, l.product_uom_id)
                       for l in line.bom_id.bom_line_ids)
            kg = P._agronova_kg(line.product_qty, line.product_uom_id)
            line.agronova_ulush = (kg / jami * 100.0) if jami else 0.0

    def _agronova_tekshir(self):
        if self.env.context.get('agronova_bom_ruxsat'):
            return
        for line in self:
            if line.bom_id.agronova_holat in ('tasdiqlangan', 'arxiv'):
                raise UserError(_(
                    "«%s» retsepturasi tasdiqlangan — komponentlarni o'zgartirish uchun "
                    "yangi versiya oching.", line.bom_id.display_name))

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._agronova_tekshir()
        return lines

    def write(self, vals):
        self._agronova_tekshir()
        return super().write(vals)

    def unlink(self):
        self._agronova_tekshir()
        return super().unlink()
