# -*- coding: utf-8 -*-
"""Ishlab chiqarish buyurtmasi — yem zavodi zanjirining markazi.

Buyurtmada yig'iladi:

* **qayerda va qachon** — liniya, smena, smena hisoboti, reja qatori;
* **qaysi me'yor bilan** — retseptura versiyasi tasdiqlash paytida qotadi;
* **sarf** — har komponent bo'yicha reja/haqiqiy (`stock.move`), ruxsat
  etilgan og'ishdan oshsa boshliq tasdig'i talab qilinadi (TZ 3.3);
* **yo'qotish** — me'yoriy (retseptura %) va haqiqiy (berilgan xomashyo −
  tayyor mahsulot), ortiqchasi alohida (TZ 5.1); buyurtma yopilganda
  yo'qotish reyestriga yozuv avtomatik tushadi;
* **tannarx** — xomashyo (FIFO), ish markazi, qadoq va taqsimlangan
  xarajatlar bilan 1 kg / 1 tonna (TZ 9).

Qoidalar faqat **tayyor yem** (`agronova_yem_turi = 'yem'`) buyurtmalariga
qo'llanadi — boshqa bo'limlarning MRP buyurtmalari o'zgarmaydi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)

    # Ishlab chiqariladigan mahsulot ro'yxati: faqat retsepti bor mahsulotlar —
    # operator ro'yxatda vitamin yoki dori ko'rib adashmasin.
    product_id = fields.Many2one(
        domain="[('type', '=', 'consu'),"
               " ('bom_ids', '!=', False),"
               " ('bom_ids.company_id', 'in', [False, company_id])]")

    agronova_yem = fields.Boolean("Yem buyurtmasi", compute='_compute_agronova_yem', store=True)

    # --- joy va vaqt
    agronova_liniya_id = fields.Many2one('agronova.yem.liniya', "Liniya", tracking=True,
                                         index='btree_not_null')
    agronova_smena_turi_id = fields.Many2one('agronova.yem.smena.turi', "Smena", tracking=True)
    agronova_smena_id = fields.Many2one('agronova.yem.smena', "Smena hisoboti", copy=False,
                                        index='btree_not_null')
    agronova_reja_qator_id = fields.Many2one('agronova.yem.reja.qator', "Reja qatori", copy=False,
                                             index='btree_not_null')
    agronova_bom_versiya = fields.Char("Retseptura versiyasi", readonly=True, copy=False,
                                       help="Buyurtma tasdiqlangan paytdagi retseptura versiyasi.")

    # --- sarf va yo'qotish (TZ 3.3, 5.1)
    agronova_kirim_kg = fields.Float("Berilgan xomashyo (kg)", compute='_compute_agronova_yoqotish',
                                     store=True, digits=(16, 1))
    agronova_meyoriy_yoqotish_kg = fields.Float("Me'yoriy yo'qotish (kg)",
                                                compute='_compute_agronova_yoqotish', store=True,
                                                digits=(16, 1))
    agronova_kutilgan_kg = fields.Float("Kutilgan chiqim (kg)", compute='_compute_agronova_yoqotish',
                                        store=True, digits=(16, 1))
    agronova_haqiqiy_yoqotish_kg = fields.Float("Haqiqiy yo'qotish (kg)",
                                                compute='_compute_agronova_yoqotish', store=True,
                                                digits=(16, 1))
    agronova_ortiqcha_yoqotish_kg = fields.Float("Me'yordan ortiq (kg)",
                                                 compute='_compute_agronova_yoqotish', store=True,
                                                 digits=(16, 1))
    agronova_yoqotish_pct = fields.Float("Yo'qotish (%)", compute='_compute_agronova_yoqotish',
                                         store=True, digits=(16, 2))
    agronova_yoqotish_qiymat = fields.Monetary("Yo'qotish qiymati",
                                               compute='_compute_agronova_yoqotish', store=True)
    agronova_sarf_ogish = fields.Boolean("Sarfda og'ish", compute='_compute_agronova_sarf_ogish',
                                         store=True)
    agronova_sarf_tasdiqlagan_id = fields.Many2one('res.users', "Og'ishni tasdiqlagan",
                                                   readonly=True, copy=False, tracking=True)
    agronova_sarf_sabab = fields.Text("Og'ish sababi", copy=False, tracking=True)
    agronova_yoqotish_ids = fields.One2many('agronova.yem.yoqotish', 'production_id', "Yo'qotishlar")

    # --- qadoqlash
    agronova_qadoqlash_ids = fields.One2many('agronova.yem.qadoqlash', 'production_id', "Qadoqlash")
    agronova_qadoqlangan_kg = fields.Float("Qadoqlangan (kg)", compute='_compute_agronova_qadoq',
                                           store=True, digits=(16, 1))
    agronova_qop_soni = fields.Integer("Qoplar soni", compute='_compute_agronova_qadoq', store=True)
    agronova_qadoq_qiymat = fields.Monetary("Qadoq qiymati", compute='_compute_agronova_qadoq',
                                            store=True)

    # --- tannarx (TZ 9)
    agronova_miqdor_kg = fields.Float(
        "Ishlab chiqarilgan (kg)", compute='_compute_agronova_tannarx',
        store=True, digits='Product Unit',
        help="Mahsulot o'lchov birligidan kilogrammga o'girilgan miqdor.")
    agronova_xomashyo_qiymat = fields.Monetary(
        "Xomashyo qiymati", compute='_compute_agronova_tannarx', store=True,
        help="Sarflangan xomashyoning FIFO bo'yicha haqiqiy qiymati.")
    agronova_ustama_qiymat = fields.Monetary(
        "Ish markazi xarajati", compute='_compute_agronova_tannarx', store=True,
        help="Ish markazi orqali kirgan xarajat. Tayyor mahsulot qiymati minus xomashyo.")
    agronova_jami_tannarx = fields.Monetary("Ishlab chiqarish tannarxi",
                                            compute='_compute_agronova_tannarx', store=True)
    agronova_ustama_taqsim = fields.Monetary(
        "Taqsimlangan xarajat", readonly=True, copy=False,
        help="Davr xarajatlari (ish haqi, elektr, gaz, xizmat...) ishlab chiqarilgan kg ga "
             "mutanosib taqsimlangan qismi.")
    agronova_toliq_tannarx = fields.Monetary("To'liq tannarx", compute='_compute_agronova_toliq',
                                             store=True)
    agronova_tannarx_1_kg = fields.Monetary("1 kg tannarxi", compute='_compute_agronova_toliq',
                                            store=True)
    agronova_tannarx_1_tonna = fields.Monetary("1 tonna tannarxi", compute='_compute_agronova_toliq',
                                               store=True)
    agronova_xomashyo_ulush = fields.Float(
        "Xomashyo ulushi (%)", compute='_compute_agronova_toliq', store=True,
        help="Xomashyo qiymati to'liq tannarxning necha foizi.")
    # Reja tasdiqlash paytida qotadi: keyin xomashyo narxi o'zgarsa ham o'tgan
    # davrlarning reja-fakt taqqoslamasi siljimaydi.
    agronova_reja_tannarx_1_kg = fields.Monetary(
        "Reja: 1 kg tannarxi", readonly=True, copy=False,
        help="Tasdiqlash paytidagi retseptura bo'yicha: komponentlarning standart narxi + "
             "operatsiya vaqti × ish markazi tarifi.")
    agronova_chetlanish = fields.Float(
        "Rejadan chetlanish (%)", compute='_compute_agronova_chetlanish', store=True,
        help="Fakt rejadan qancha foizga farq qildi. Musbat — qimmatga tushgan.")

    # ---------------------------------------------------------------- yordamchi
    def _agronova_kg(self, qty, uom):
        return self.env['product.product']._agronova_kg(qty, uom)

    # ------------------------------------------------------------------ compute
    @api.depends('product_id.agronova_yem_turi')
    def _compute_agronova_yem(self):
        for mo in self:
            mo.agronova_yem = mo.product_id.agronova_yem_turi == 'yem'

    @api.depends('state', 'qty_produced', 'product_uom_id',
                 'move_raw_ids.value', 'move_raw_ids.state',
                 'move_finished_ids.value', 'move_finished_ids.state',
                 'move_finished_ids.quantity')
    def _compute_agronova_tannarx(self):
        for mo in self:
            xom = sum(abs(m.value or 0.0) for m in mo.move_raw_ids if m.state == 'done')
            tayyor = mo.move_finished_ids.filtered(
                lambda m: m.state == 'done' and m.product_id == mo.product_id)
            jami = sum(abs(m.value or 0.0) for m in tayyor)
            miqdor = sum(m.quantity for m in tayyor)
            if not jami and xom:
                jami = xom
            mo.agronova_xomashyo_qiymat = xom
            mo.agronova_ustama_qiymat = max(jami - xom, 0.0)
            mo.agronova_jami_tannarx = jami
            mo.agronova_miqdor_kg = mo._agronova_kg(
                miqdor, tayyor[:1].product_uom or mo.product_uom_id)

    @api.depends('agronova_jami_tannarx', 'agronova_ustama_taqsim', 'agronova_qadoq_qiymat',
                 'agronova_xomashyo_qiymat', 'agronova_miqdor_kg')
    def _compute_agronova_toliq(self):
        for mo in self:
            toliq = (mo.agronova_jami_tannarx or 0.0) + (mo.agronova_ustama_taqsim or 0.0) \
                + (mo.agronova_qadoq_qiymat or 0.0)
            kg = mo.agronova_miqdor_kg
            mo.agronova_toliq_tannarx = toliq
            mo.agronova_tannarx_1_kg = (toliq / kg) if kg else 0.0
            mo.agronova_tannarx_1_tonna = mo.agronova_tannarx_1_kg * 1000.0
            mo.agronova_xomashyo_ulush = (mo.agronova_xomashyo_qiymat / toliq * 100.0) if toliq else 0.0

    @api.depends('agronova_tannarx_1_kg', 'agronova_reja_tannarx_1_kg')
    def _compute_agronova_chetlanish(self):
        for mo in self:
            reja = mo.agronova_reja_tannarx_1_kg
            mo.agronova_chetlanish = (
                (mo.agronova_tannarx_1_kg - reja) / reja * 100.0
                if reja and mo.agronova_tannarx_1_kg else 0.0)

    @api.depends('state', 'move_raw_ids.agronova_fakt_kg', 'move_raw_ids.state',
                 'agronova_miqdor_kg', 'bom_id.agronova_yoqotish_foiz', 'agronova_xomashyo_qiymat')
    def _compute_agronova_yoqotish(self):
        for mo in self:
            kirim = sum(m.agronova_fakt_kg for m in mo.move_raw_ids if m.state != 'cancel')
            foiz = mo.bom_id.agronova_yoqotish_foiz or 0.0
            meyoriy = kirim * foiz / 100.0
            mo.agronova_kirim_kg = kirim
            mo.agronova_meyoriy_yoqotish_kg = meyoriy
            mo.agronova_kutilgan_kg = kirim - meyoriy
            if mo.state == 'done' and kirim and mo.agronova_miqdor_kg:
                haqiqiy = max(kirim - mo.agronova_miqdor_kg, 0.0)
                birlik = (mo.agronova_xomashyo_qiymat / kirim) if kirim else 0.0
                mo.agronova_haqiqiy_yoqotish_kg = haqiqiy
                mo.agronova_ortiqcha_yoqotish_kg = max(haqiqiy - meyoriy, 0.0)
                mo.agronova_yoqotish_pct = haqiqiy / kirim * 100.0
                mo.agronova_yoqotish_qiymat = haqiqiy * birlik
            else:
                mo.agronova_haqiqiy_yoqotish_kg = 0.0
                mo.agronova_ortiqcha_yoqotish_kg = 0.0
                mo.agronova_yoqotish_pct = 0.0
                mo.agronova_yoqotish_qiymat = 0.0

    @api.depends('move_raw_ids.agronova_limitdan_oshdi', 'move_raw_ids.state')
    def _compute_agronova_sarf_ogish(self):
        for mo in self:
            mo.agronova_sarf_ogish = any(
                m.agronova_limitdan_oshdi for m in mo.move_raw_ids if m.state != 'cancel')

    @api.depends('agronova_qadoqlash_ids.state', 'agronova_qadoqlash_ids.netto_kg',
                 'agronova_qadoqlash_ids.qop_soni', 'agronova_qadoqlash_ids.qop_qiymat')
    def _compute_agronova_qadoq(self):
        for mo in self:
            q = mo.agronova_qadoqlash_ids.filtered(lambda r: r.state == 'tasdiqlangan')
            mo.agronova_qadoqlangan_kg = sum(q.mapped('netto_kg'))
            mo.agronova_qop_soni = sum(q.mapped('qop_soni'))
            mo.agronova_qadoq_qiymat = sum(q.mapped('qop_qiymat'))

    # ----------------------------------------------------------- smena bog'lash
    def _agronova_sana(self):
        self.ensure_one()
        dt = self.date_start or fields.Datetime.now()
        return fields.Datetime.context_timestamp(self, dt).date()

    def _agronova_smena_bogla(self):
        Smena = self.env['agronova.yem.smena']
        for mo in self:
            if not (mo.agronova_liniya_id and mo.agronova_smena_turi_id):
                continue
            smena = Smena.search([
                ('liniya_id', '=', mo.agronova_liniya_id.id),
                ('smena_turi_id', '=', mo.agronova_smena_turi_id.id),
                ('sana', '=', mo._agronova_sana()),
            ], limit=1)
            if smena and mo.agronova_smena_id != smena:
                mo.with_context(agronova_smena_bogla=True).agronova_smena_id = smena

    @api.model_create_multi
    def create(self, vals_list):
        mos = super().create(vals_list)
        mos._agronova_smena_bogla()
        return mos

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('agronova_smena_bogla') and \
                {'agronova_liniya_id', 'agronova_smena_turi_id', 'date_start'} & set(vals):
            self._agronova_smena_bogla()
        return res

    # ------------------------------------------------------------ reja qotish
    def _agronova_reja_hisobla(self):
        """Retseptura bo'yicha 1 kg nazariy tannarx (shu paytdagi narxlarda)."""
        self.ensure_one()
        bom = self.bom_id
        if not bom or not bom.product_qty:
            return 0.0
        xom = sum(line.product_id.standard_price * line.product_qty for line in bom.bom_line_ids)
        ustama = sum((op.time_cycle_manual / 60.0) * op.workcenter_id.costs_hour
                     for op in bom.operation_ids)
        kg = self._agronova_kg(bom.product_qty, bom.product_uom_id)
        return ((xom + ustama) / kg) if kg else 0.0

    def action_confirm(self):
        for mo in self.filtered('agronova_yem'):
            if mo.bom_id and mo.bom_id.agronova_holat != 'tasdiqlangan':
                raise UserError(_(
                    "«%(b)s» retsepturasi tasdiqlanmagan. Yem faqat texnolog tasdiqlagan "
                    "retseptura bo'yicha ishlab chiqariladi.", b=mo.bom_id.display_name))
        res = super().action_confirm()
        for mo in self:
            vals = {}
            if not mo.agronova_reja_tannarx_1_kg:
                vals['agronova_reja_tannarx_1_kg'] = mo._agronova_reja_hisobla()
            if mo.bom_id and not mo.agronova_bom_versiya:
                vals['agronova_bom_versiya'] = "v%s" % (mo.bom_id.agronova_versiya or 1)
            if vals:
                mo.write(vals)
        return res

    # ---------------------------------------------------------- sarf tasdig'i
    def _agronova_ogishlar_matni(self):
        self.ensure_one()
        qatorlar = []
        for m in self.move_raw_ids.filtered(lambda x: x.agronova_limitdan_oshdi):
            qatorlar.append("• %s: reja %.1f kg, haqiqiy %.1f kg (%+.2f%%, ruxsat ±%.1f%%)" % (
                m.product_id.display_name, m.agronova_reja_kg,
                m.agronova_reja_kg + m.agronova_farq_kg, m.agronova_farq_pct, m.agronova_ogish_limit))
        return "\n".join(qatorlar)

    def action_agronova_sarf_tasdiq(self):
        if not self.env.user.has_group('agronova_yem_zavodi.group_yem_boshliq'):
            raise UserError(_("Me'yordan tashqari sarfni faqat ishlab chiqarish boshlig'i tasdiqlaydi."))
        for mo in self:
            if not (mo.agronova_sarf_sabab or '').strip():
                raise UserError(_("Og'ish sababini yozing."))
            mo.agronova_sarf_tasdiqlagan_id = self.env.user
            mo.message_post(body=_("Me'yordan tashqari sarf tasdiqlandi. Sabab: %(s)s\n%(q)s",
                                   s=mo.agronova_sarf_sabab, q=mo._agronova_ogishlar_matni()))
        return True

    def button_mark_done(self):
        for mo in self.filtered(lambda m: m.agronova_yem and m.agronova_sarf_ogish
                                and not m.agronova_sarf_tasdiqlagan_id):
            raise UserError(_(
                "%(mo)s: xomashyo sarfi ruxsat etilgan og'ishdan chiqdi:\n%(q)s\n\n"
                "Buyurtmani yopish uchun ishlab chiqarish boshlig'i og'ish sababini yozib, "
                "«Og'ishni tasdiqlash» tugmasini bosishi kerak.",
                mo=mo.name, q=mo._agronova_ogishlar_matni()))
        for mo in self:
            if not mo.agronova_reja_tannarx_1_kg:
                mo.agronova_reja_tannarx_1_kg = mo._agronova_reja_hisobla()
        res = super().button_mark_done()
        self.filtered(lambda m: m.state == 'done' and m.agronova_yem)._agronova_yoqotish_yoz()
        return res

    def _agronova_yoqotish_yoz(self):
        """Yopilgan buyurtma bo'yicha yo'qotish reyestriga yozuv.

        Me'yor doirasidagi yo'qotish avtomatik tasdiqlanadi; me'yordan
        ortig'i «tekshiruvda» holatida ochiladi va boshliqqa vazifa tushadi —
        u sababni aniqlab, tasdiqlaydi yoki rad etadi (TZ 5.2).
        """
        Yoqotish = self.env['agronova.yem.yoqotish'].sudo()
        for mo in self:
            if mo.agronova_yoqotish_ids.filtered(lambda y: y.avtomatik) or \
                    not mo.agronova_haqiqiy_yoqotish_kg:
                continue
            ortiq = mo.agronova_ortiqcha_yoqotish_kg > 0.05
            y = Yoqotish.create({
                'sana': mo.date_finished or fields.Datetime.now(),
                'production_id': mo.id,
                'product_id': mo.product_id.id,
                'liniya_id': mo.agronova_liniya_id.id,
                'smena_id': mo.agronova_smena_id.id,
                'turi': 'texnologik',
                'miqdor_kg': mo.agronova_haqiqiy_yoqotish_kg,
                'meyoriy_kg': mo.agronova_meyoriy_yoqotish_kg,
                'avtomatik': True,
                'state': 'tekshiruvda' if ortiq else 'tasdiqlangan',
                'sabab': _("Buyurtma yopilganda avtomatik: berilgan %(k)s kg, chiqim %(c)s kg.",
                           k=round(mo.agronova_kirim_kg, 1), c=round(mo.agronova_miqdor_kg, 1)),
            })
            if ortiq:
                y._boshliqqa_vazifa()

    # ----------------------------------------------------------------- tugmalar
    def action_agronova_yoqotishlar(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'agronova_yem_zavodi.action_agronova_yem_yoqotish')
        action['domain'] = [('production_id', '=', self.id)]
        action['context'] = {'default_production_id': self.id}
        return action

    def action_agronova_qadoqlash(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'agronova_yem_zavodi.action_agronova_yem_qadoqlash')
        action['domain'] = [('production_id', '=', self.id)]
        action['context'] = {'default_production_id': self.id}
        return action
