# -*- coding: utf-8 -*-
"""Tuxum omboriga kirim — B08.

Kunlik jurnal tasdiqlanganda avtomat ochiladi. Har kirim tuxum omboriga
`stock.move` yaratadi va lot beradi (lot = partiya + sana), shunda keyin
qaysi tuxum qaysi kundan va qaysi sexdan kelgani ko'rinadi.

Tannarx qo'lda kiritilmaydi: partiyaning yugurib boruvchi 1 dona tannarxidan
olinadi (jami xarajat / jami ishlab chiqarilgan tuxum).
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

SIFAT = [
    ('inkubatsion', "Inkubatsiyaga yaroqli"),
    ('tovar', "Tovar (sifatli)"),
    ('brak', "Brak"),
]


class AgroNovaOnaTovuqTuxumKirim(models.Model):
    _name = 'agronova.ona_tovuq.tuxum.kirim'
    _description = "Ona tovuq — tuxum omboriga kirim"
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    name = fields.Char("Hujjat", compute='_compute_name', store=True)
    date = fields.Date("Sana", required=True, default=fields.Date.context_today,
                       tracking=True)
    partiya_id = fields.Many2one(
        'agronova.ona_tovuq.partiya.tuxum', string="Ona tovuq partiyasi",
        required=True, ondelete='restrict', index=True)
    sex_id = fields.Many2one(related='partiya_id.sex_id', string="Sex",
                             store=True, readonly=True)
    jurnal_id = fields.Many2one(
        'agronova.ona_tovuq.jurnal.tuxum', string="Kunlik jurnal",
        readonly=True, ondelete='set null', index='btree_not_null')
    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True, readonly=True,
        store=True, precompute=True, compute='_compute_company_id',
        help="Partiya qaysi korxonada bo'lsa — hujjat ham o'shanda.")
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)


    @api.depends('partiya_id')
    def _compute_company_id(self):
        for rec in self:
            rec.company_id = rec.partiya_id.company_id or self.env.company

    qator_ids = fields.One2many(
        'agronova.ona_tovuq.tuxum.kirim.qator', 'kirim_id', string="Qatorlar")
    jami_dona = fields.Integer("Jami (dona)", compute='_compute_jami', store=True)
    jami_qiymat = fields.Monetary("Jami qiymat", compute='_compute_jami', store=True)

    holat = fields.Selection(
        [('draft', "Qoralama"), ('done', "Kirim qilingan")],
        string="Holati", default='draft', required=True, tracking=True, copy=False)

    _sql_jurnal_uniq = models.Constraint(
        'UNIQUE(jurnal_id)', "Bu jurnal uchun kirim allaqachon ochilgan.")

    # --------------------------------------------------------------- compute
    @api.depends('partiya_id', 'date')
    def _compute_name(self):
        for k in self:
            k.name = "%s / %s" % (k.partiya_id.name or "?", k.date or "")

    @api.depends('qator_ids.dona', 'qator_ids.qiymat')
    def _compute_jami(self):
        for k in self:
            k.jami_dona = sum(k.qator_ids.mapped('dona'))
            k.jami_qiymat = sum(k.qator_ids.mapped('qiymat'))

    # ---------------------------------------------------------------- yozish
    @api.model_create_multi
    def create(self, vals_list):
        kirimlar = super().create(vals_list)
        kirimlar._qatorlarni_jurnaldan_tuldirish()
        return kirimlar

    def _qatorlarni_jurnaldan_tuldirish(self):
        """Jurnaldagi tuxum sonlaridan qatorlarni tayyorlaydi."""
        Qator = self.env['agronova.ona_tovuq.tuxum.kirim.qator']
        for k in self.filtered(lambda r: r.jurnal_id and not r.qator_ids):
            j = k.jurnal_id
            taqsimot = [
                ('inkubatsion', j.inkubatsiyaga_yarokli),
                ('tovar', j.sifatli_tuxum - j.inkubatsiyaga_yarokli),
                ('brak', j.brak_tuxum),
            ]
            for sifat, dona in taqsimot:
                if dona > 0:
                    Qator.create({'kirim_id': k.id, 'sifat': sifat, 'dona': dona})

    def write(self, vals):
        for k in self:
            if k.holat == 'done' and set(vals) - {'message_ids',
                                                  'message_follower_ids'}:
                raise UserError(_(
                    "«%s» kirimi bajarilgan — tahrirlanmaydi.", k.display_name))
        return super().write(vals)

    # ------------------------------------------------------------- tasdiqlash
    def action_kirim(self):
        """Tuxumni omborga kiritadi: lot ochadi, `stock.move` yaratadi."""
        for k in self:
            if k.holat == 'done':
                continue
            if not k.qator_ids:
                raise UserError(_("Kirimda birorta qator yo'q."))
            k.partiya_id._tekshir_ochiq(_("tuxum kirimi"))
            k._moveni_yaratish()
            k.with_context(agronova_kirim_done=True).holat = 'done'
        return True

    def _lot_nomi(self, qator, product):
        """Lot nomi: partiya / sana / sifat.

        Bir partiyadan bir kunda ikki marta kirim bo'lishi mumkin
        (ertalabki va kechki yig'im, yoki qayta sanashdan keyingi
        to'g'irlash). Odoo esa bir mahsulotda bir xil nomli ikkita
        lotga yo'l qo'ymaydi — ilgari ikkinchi kirim shu sababli
        xato bilan to'xtardi. Shuning uchun takrorlansa oxiriga
        tartib raqami qo'shiladi: `.../inkubatsion-2`.
        """
        asos = "%s/%s/%s" % (self.partiya_id.name, self.date, qator.sifat)
        Lot = self.env['stock.lot'].sudo()
        nom, n = asos, 1
        while Lot.search_count([('product_id', '=', product.id),
                                ('name', '=', nom)]):
            n += 1
            nom = "%s-%s" % (asos, n)
        return nom

    def _moveni_yaratish(self):
        self.ensure_one()
        sex = self.sex_id
        src = sex._production_location()
        dest = sex._tuxum_ombori()
        if not dest:
            raise UserError(_("Tuxum ombori lokatsiyasi topilmadi."))
        tannarx = self.partiya_id.tannarx_1_dona
        for qator in self.qator_ids.filtered(lambda q: not q.move_id):
            product = qator._product()
            lot = self.env['stock.lot'].sudo().create({
                'name': self._lot_nomi(qator, product),
                'product_id': product.id,
                'company_id': self.company_id.id,
            })
            move = self.env['stock.move'].sudo().create({
                'product_id': product.id,
                'product_uom_qty': qator.dona,
                'product_uom': product.uom_id.id,
                'location_id': src.id,
                'location_dest_id': dest.id,
                'company_id': self.company_id.id,
                'origin': self.display_name,
                # Brak tuxum qiymatsiz — TZ 2-bosqich 4-savoli hal bo'lguncha
                'price_unit': 0.0 if qator.sifat == 'brak' else tannarx,
            })
            move._action_confirm()
            move.quantity = qator.dona
            move.picked = True
            move.move_line_ids.write({'lot_id': lot.id})
            move._action_done()
            qator.move_id = move
            qator.lot_id = lot
            qator._tannarx_yozish().qiymat = (
                0.0 if qator.sifat == 'brak' else tannarx * qator.dona)


class AgroNovaOnaTovuqTuxumKirimQator(models.Model):
    _name = 'agronova.ona_tovuq.tuxum.kirim.qator'
    _description = "Ona tovuq — tuxum kirimi qatori"
    _inherit = ['agronova.tannarx.qulf.mixin']
    _agronova_tannarx_fields = ('qiymat',)

    kirim_id = fields.Many2one(
        'agronova.ona_tovuq.tuxum.kirim', string="Kirim hujjati",
        required=True, ondelete='cascade', index=True)
    sifat = fields.Selection(SIFAT, string="Sifat kategoriyasi", required=True)
    dona = fields.Integer("Miqdor (dona)", required=True)
    lot_id = fields.Many2one('stock.lot', string="Lot", readonly=True, copy=False)
    move_id = fields.Many2one('stock.move', string="Ombor harakati",
                              readonly=True, copy=False)
    qiymat = fields.Monetary("Qiymati", readonly=True, copy=False,
                             help="Partiya tannarxidan avtomat. Qo'lda kiritilmaydi.")
    currency_id = fields.Many2one(
        'res.currency', related='kirim_id.currency_id', readonly=True)

    _dona_musbat = models.Constraint(
        'CHECK (dona > 0)', "Miqdor noldan katta bo'lishi kerak.")

    def _product(self):
        """Sifat kategoriyasiga mos mahsulot."""
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()
        param = {
            'inkubatsion': 'agronova_ona_tovuq.product_inkubatsion',
            'tovar': 'agronova_ona_tovuq.product_tovar',
            'brak': 'agronova_ona_tovuq.product_brak',
        }[self.sifat]
        nom = {
            'inkubatsion': "Inkubatsion tuxum",
            'tovar': "Tovar tuxum",
            'brak': "Brak tuxum",
        }[self.sifat]
        pid = ICP.get_param(param)
        product = self.env['product.product'].browse(int(pid)) if pid else None
        if product and product.exists():
            return product
        product = self.env['product.product'].search([('name', '=', nom)], limit=1)
        if not product:
            raise UserError(_(
                "«%s» mahsuloti topilmadi. Sozlamalarda ko'rsating yoki "
                "shu nom bilan yarating.", nom))
        return product
