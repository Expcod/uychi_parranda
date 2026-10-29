# -*- coding: utf-8 -*-
"""Xarid kirim hujjati (TZ 4.5, 7-bo'lim).

**Bu model tovarni ham, pulni ham o'zi qimirlatmaydi.** U ikkita Odoo
standart hujjatini bog'lab turadigan va custom maydonlarni saqlaydigan
qobiq (TZ 2-bo'lim qarori):

* `stock.picking` — tovar harakati: yetkazib beruvchi -> **zakupchik
  tranziti**, keyin omborchi qabul qilgach tranzit -> asosiy ombor;
* `account.move` (in_invoice) — moliyaviy qarz.

Ikkalasi **hech qachon birlashtirilmaydi**: Didox fakturasi tovardan 1-2
kun kech kelishi mumkin. Qarz esa tovar zakupchik qo'liga o'tgan zahoti
yoziladi — MSFO talabi, omborchi tasdig'iga bog'liq emas; omborchi tasdig'i
faqat tovarning joylashuvini o'zgartiradi.

Transport va qo'shimcha xarajat alohida xarajat sifatida emas, Landed Cost
orqali tannarxga qo'shiladi (IAS 2).
"""
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

XARID_TURI = [
    ('A_naqd', "A — naqd / bozor"),
    ('B_mahalliy', "B — mahalliy ta'minotchi"),
    ('C1_import_tovar', "C1 — tovar importi"),
    ('C2_import_uskuna', "C2 — uskuna importi"),
]
BALL_SABABI = [
    ('zakupchik_aybi', "Zakupchik aybi"),
    ('obyektiv_sabab', "Obyektiv sabab"),
    ('nizoli', "Nizoli — rahbar hal qiladi"),
]


class AgroNovaKirim(models.Model):
    _name = 'agronova.kirim'
    _description = "Xarid kirim hujjati"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sotib_olingan_sana desc, id desc'

    name = fields.Char(
        "Hujjat raqami", default=lambda self: _("Yangi"),
        copy=False, readonly=True, index=True)

    # --- sanalar (TZ 21.4: ikkalasi ham kerak, ikkinchisi o'zgarmaydi)
    sotib_olingan_sana = fields.Date(
        "Sotib olingan sana", required=True, tracking=True,
        default=fields.Date.context_today,
        help="Operatsiya sanasi — o'zgartirilishi mumkin.")
    kiritilgan_sana = fields.Datetime(
        "Kiritilgan payt", related='create_date', store=True, readonly=True,
        help="Nazorat izi — hech qachon o'zgarmaydi.")
    kechikib_kiritilgan = fields.Boolean(
        "Kechikib kiritilgan", readonly=True, copy=False, tracking=True,
        help="Operatsiya sanasi kiritilgan sanadan orqada — TZ 12-bo'lim.")

    xarid_turi = fields.Selection(
        XARID_TURI, string="Xarid turi", required=True, default='A_naqd',
        tracking=True)
    tasdiqlangan_ruxsat_id = fields.Many2one(
        'agronova.ruxsat', string="Tasdiqlangan ruxsat", required=True,
        tracking=True, ondelete='restrict',
        domain="[('holat', '=', 'tasdiqlandi')]",
        help="Ruxsatsiz xarid rasmiylashtirilmaydi (TZ 4.5).")
    zayavka_id = fields.Many2one(
        'agronova.zayavka', related='tasdiqlangan_ruxsat_id.zayavka_id',
        store=True, readonly=True, string="Zayavka")
    zakupchik_id = fields.Many2one(
        'res.users', string="Zakupchik", required=True, tracking=True,
        default=lambda self: self.env.user)
    kontragent_id = fields.Many2one(
        'res.partner', string="Kontragent", tracking=True,
        domain="[('zakupka_holati', '=', 'faol')]")
    oz_nomidan = fields.Boolean(
        "O'z nomidan (bozor)", tracking=True,
        help="Bozordan rasmiy kontragentsiz olingan xarid. Faqat A turida.")
    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)

    qator_ids = fields.One2many(
        'agronova.kirim.qatori', 'kirim_id', string="Qatorlar", copy=True)

    # --- summa va QQS
    summa = fields.Monetary(
        "Tovar summasi", compute='_compute_summa', store=True, tracking=True)
    qqs_bormi = fields.Boolean("QQS bor", tracking=True)
    qqs_foizi = fields.Float("QQS (%)", default=12.0)
    qqs_summasi = fields.Monetary(
        "QQS summasi", compute='_compute_summa', store=True)
    jami_summa = fields.Monetary(
        "Jami summa", compute='_compute_summa', store=True)
    tolangan_summa = fields.Monetary("To'langan summa", tracking=True)
    depozit_id = fields.Many2one(
        'agronova.depozit', string="Depozit",
        help="Naqd xaridda pul shu depozitdan chiqadi (TZ 12-bo'lim).")
    depozit_harakat_id = fields.Many2one(
        'agronova.depozit.harakat', string="Depozit chiqimi",
        readonly=True, copy=False)

    # --- ombor
    maqsad_ombor_id = fields.Many2one(
        'stock.warehouse', string="Maqsad ombori", required=True,
        tracking=True,
        help="Omborchi qabul qilgandan keyin tovar shu omborga o'tadi.")
    tranzit_id = fields.Many2one(
        'stock.location', string="Zakupchik tranziti", readonly=True, copy=False)
    picking_kirim_id = fields.Many2one(
        'stock.picking', string="Tranzitga kirim", readonly=True, copy=False)
    picking_qabul_id = fields.Many2one(
        'stock.picking', string="Omborga qabul", readonly=True, copy=False)
    transport_xarajati = fields.Monetary("Transport xarajati", tracking=True)
    qoshimcha_xarajat = fields.Monetary("Boshqa qo'shimcha xarajat")
    landed_cost_id = fields.Many2one(
        'stock.landed.cost', string="Landed Cost", readonly=True, copy=False)

    # --- moliya
    faktura_id = fields.Many2one(
        'account.move', string="Kirim fakturasi", readonly=True, copy=False,
        help="Qarz hujjati. Tovar bilan bir vaqtda yaratiladi, Didox "
             "fakturasi kelgach solishtiriladi.")
    faktura_holati = fields.Selection(
        [('yoq', "Yaratilmagan"),
         ('kutilmoqda', "Didox fakturasi kutilmoqda"),
         ('moslashtirildi', "Didox bilan solishtirildi"),
         ('nomos', "Nomuvofiqlik")],
        string="Faktura holati", default='yoq', readonly=True, copy=False,
        tracking=True)
    didox_log_id = fields.Many2one(
        'agronova.didox.log', string="Didox yozuvi", readonly=True, copy=False)
    import_id = fields.Many2one(
        'agronova.import', string="Import hujjati", readonly=True, copy=False)

    ilova = fields.Binary("Chek / schyot / faktura surati", attachment=True)
    ilova_filename = fields.Char("Fayl nomi")
    izoh = fields.Text("Izoh")

    # --- narx nazorati
    ruxsat_narxi = fields.Monetary(
        "Ruxsatdagi narx", related='tasdiqlangan_ruxsat_id.taklif_narx',
        readonly=True)
    ogish_foizi = fields.Float(
        "Ruxsatdan og'ish (%)", compute='_compute_ogish', store=True,
        help="Haqiqiy narxning tasdiqlangan ruxsat narxidan og'ishi.")
    ogish_chegara = fields.Float(
        "Og'ish chegarasi (%)", compute='_compute_ogish', store=True)

    # --- holat va omborchi bahosi
    holat = fields.Selection(
        [('draft', "Qoralama"),
         ('tasdiqlangan', "Tasdiqlangan (tranzitda)"),
         ('qabul_qilindi', "Omborga qabul qilindi"),
         ('bekor', "Bekor qilindi")],
        string="Holati", default='draft', required=True, tracking=True, copy=False)
    tranzit_sanasi = fields.Datetime(
        "Tranzitga tushgan payt", readonly=True, copy=False)
    tranzit_kunlari = fields.Integer(
        "Tranzitda (kun)", compute='_compute_tranzit_kunlari',
        search='_search_tranzit_kunlari')
    qabul_sanasi = fields.Datetime("Qabul sanasi", readonly=True, copy=False)
    omborchi_id = fields.Many2one(
        'res.users', string="Qabul qilgan omborchi", readonly=True, copy=False)

    ball_toliqlik = fields.Integer("Ball — to'liqlik", readonly=True, copy=False)
    ball_muddat = fields.Integer("Ball — muddat", readonly=True, copy=False)
    ball_sifat = fields.Integer("Ball — sifat", readonly=True, copy=False)
    ball_ortacha = fields.Float(
        "O'rtacha ball", compute='_compute_ball_ortacha', store=True)
    ball_sababi = fields.Selection(
        BALL_SABABI, string="Ball sababi", readonly=True, copy=False)
    ball_izohi = fields.Text("Ball izohi", readonly=True, copy=False)

    qaytarish_ids = fields.One2many(
        'agronova.qaytarish', 'kirim_id', string="Qaytarishlar")

    # ------------------------------------------------------------- compute
    @api.depends('qator_ids.summa', 'qqs_bormi', 'qqs_foizi')
    def _compute_summa(self):
        for rec in self:
            summa = sum(rec.qator_ids.mapped('summa'))
            rec.summa = summa
            rec.qqs_summasi = summa * rec.qqs_foizi / 100.0 if rec.qqs_bormi else 0.0
            rec.jami_summa = rec.summa + rec.qqs_summasi

    @api.depends('qator_ids.narx', 'tasdiqlangan_ruxsat_id.taklif_narx',
                 'tasdiqlangan_ruxsat_id.product_id')
    def _compute_ogish(self):
        for rec in self:
            ruxsat = rec.tasdiqlangan_ruxsat_id
            chegara = 0.0
            if ruxsat.product_id:
                chegara = ruxsat.product_id._agronova_ogish_chegara()[0]
            rec.ogish_chegara = chegara
            # Ruxsatda ko'rsatilgan tovarning haqiqiy narxi bilan
            # solishtiramiz; boshqa qatorlar (yo'l-yo'lakay olingan mayda
            # tovarlar) o'z norma narxi bo'yicha alohida tekshiriladi.
            qator = rec.qator_ids.filtered(
                lambda q: q.product_id == ruxsat.product_id)[:1]
            if qator and ruxsat.taklif_narx:
                rec.ogish_foizi = 100.0 * (
                    qator.narx - ruxsat.taklif_narx) / ruxsat.taklif_narx
            else:
                rec.ogish_foizi = 0.0

    @api.depends('ball_toliqlik', 'ball_muddat', 'ball_sifat')
    def _compute_ball_ortacha(self):
        for rec in self:
            ballar = [rec.ball_toliqlik, rec.ball_muddat, rec.ball_sifat]
            rec.ball_ortacha = sum(ballar) / 3.0 if any(ballar) else 0.0

    def _compute_tranzit_kunlari(self):
        hozir = fields.Datetime.now()
        for rec in self:
            if rec.holat == 'tasdiqlangan' and rec.tranzit_sanasi:
                rec.tranzit_kunlari = (hozir - rec.tranzit_sanasi).days
            else:
                rec.tranzit_kunlari = 0

    def _search_tranzit_kunlari(self, operator, value):
        if operator not in ('>', '>=', '<', '<='):
            raise NotImplementedError(_("Bu filtr faqat solishtirish bilan ishlaydi."))
        chegara = fields.Datetime.now() - relativedelta(days=value)
        teskari = {'>': '<', '>=': '<=', '<': '>', '<=': '>='}[operator]
        return [('holat', '=', 'tasdiqlangan'),
                ('tranzit_sanasi', teskari, chegara)]

    # ---------------------------------------------------------- validatsiya
    @api.constrains('qator_ids', 'tasdiqlangan_ruxsat_id')
    def _check_narx_ogishi(self):
        """Chegaradan oshgan narx bilan hujjat **saqlanmaydi** (TZ 6, 19).

        Bu tekshiruv ataylab constraint qatlamida: UI validatsiyasi
        import va XML-RPC orqali kiritishni to'smaydi.
        """
        for rec in self:
            if rec.holat == 'bekor':
                continue
            for qator in rec.qator_ids:
                if not qator.product_id or qator.narx <= 0:
                    continue
                chegara, manba = qator.product_id._agronova_ogish_chegara()
                ruxsat = rec.tasdiqlangan_ruxsat_id
                if ruxsat.product_id == qator.product_id and ruxsat.taklif_narx:
                    baza, baza_nomi = ruxsat.taklif_narx, _("tasdiqlangan ruxsat")
                else:
                    norma = self.env['agronova.narx.normasi']._agronova_norma(
                        qator.product_id)
                    baza, baza_nomi = norma['narx'], _("norma narx")
                if not baza:
                    continue
                ogish = 100.0 * (qator.narx - baza) / baza
                if ogish > chegara:
                    raise ValidationError(_(
                        "«%(tovar)s» narxi %(baza_nomi)s dan %(ogish).1f%% "
                        "oshgan, ruxsat etilgan chegara %(chegara).1f%% "
                        "(%(manba)s). Hujjat saqlanmaydi — qayta ruxsat "
                        "so'rang (TZ 6-bo'lim).",
                        tovar=qator.product_id.display_name,
                        baza_nomi=baza_nomi, ogish=ogish,
                        chegara=chegara, manba=manba))

    @api.constrains('xarid_turi', 'kontragent_id', 'oz_nomidan', 'ilova',
                    'depozit_id', 'tolangan_summa')
    def _check_rekvizit(self):
        self.filtered(lambda r: r.holat != 'draft')._agronova_rekvizit_tekshir()

    def _agronova_rekvizit_tekshir(self):
        """Hujjat rasmiylashtirilishi uchun zarur rekvizitlar.

        Constraint holatga qaraydi, `action_tasdiqlash` esa holatni oxirida
        yozadi — shuning uchun tekshiruv shu yerda alohida turadi va
        tasdiqlashdan **oldin** chaqiriladi.
        """
        for rec in self:
            if not rec.kontragent_id and not rec.oz_nomidan:
                raise ValidationError(_(
                    "«%s»: kontragent tanlanmagan. Bozordan rasmiy "
                    "kontragentsiz olingan bo'lsa «O'z nomidan» ni "
                    "belgilang.", rec.display_name))
            if rec.oz_nomidan and rec.xarid_turi != 'A_naqd':
                raise ValidationError(_(
                    "«O'z nomidan» faqat A (naqd/bozor) turida bo'ladi."))
            if rec.xarid_turi in ('B_mahalliy', 'C1_import_tovar',
                                  'C2_import_uskuna') and not rec.kontragent_id.stir:
                raise ValidationError(_(
                    "«%s»: %s turidagi xaridda kontragent STIRi majburiy — "
                    "Didox solishtiruvi shunga tayanadi.",
                    rec.display_name, dict(XARID_TURI)[rec.xarid_turi]))
            if not rec.ilova:
                raise ValidationError(_(
                    "«%s»: chek / schyot / faktura surati ilova qilinishi "
                    "shart (agronova_base xarajat qoidasi bilan bir xil).",
                    rec.display_name))
            if rec.xarid_turi == 'A_naqd':
                if not rec.depozit_id:
                    raise ValidationError(_(
                        "«%s»: naqd xaridda depozit tanlanishi shart — pul "
                        "kimning qo'lidan chiqqani ko'rinishi kerak.",
                        rec.display_name))
                if rec.tolangan_summa <= 0:
                    raise ValidationError(_(
                        "«%s»: naqd xaridda to'langan summa ko'rsatilmagan.",
                        rec.display_name))

    @api.constrains('sotib_olingan_sana')
    def _check_orqaga_sana(self):
        """Orqaga sana bilan kiritish qoidalari (TZ 12-bo'lim)."""
        oyna = int(self.env['ir.config_parameter'].sudo().get_param(
            'agronova_zakupka.orqaga_sana_oyna', 24) or 24)
        bugun = fields.Date.context_today(self)
        for rec in self:
            if not rec.sotib_olingan_sana:
                continue
            if rec.sotib_olingan_sana > bugun:
                raise ValidationError(_(
                    "Kelajakdagi sana bilan xarid kiritilmaydi."))
            farq_soat = (bugun - rec.sotib_olingan_sana).days * 24
            if farq_soat <= oyna:
                continue
            # Oyna tashqarisida — bosh buxgalter ruxsati kerak.
            if not self.env.user.has_group('agronova_base.group_agronova_bosh_buxgalter'):
                raise ValidationError(_(
                    "«%(sana)s» sanasi kiritish oynasidan (%(oyna)s soat) "
                    "tashqarida. Bunday yozuvni faqat bosh buxgalter "
                    "kirita oladi (TZ 12-bo'lim).",
                    sana=rec.sotib_olingan_sana, oyna=oyna))
            # Oy yopilgandan keyin — mutlaqo taqiq (Odoo Lock Date).
            qulf = rec.company_id.fiscalyear_lock_date
            if qulf and rec.sotib_olingan_sana <= qulf:
                raise ValidationError(_(
                    "«%(sana)s» yopilgan davrga tegishli (qulf: %(qulf)s) — "
                    "yozuv kiritilmaydi.",
                    sana=rec.sotib_olingan_sana, qulf=qulf))

    # -------------------------------------------------------- create/write
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _("Yangi")) == _("Yangi"):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'agronova.kirim') or _("Yangi")
        recs = super().create(vals_list)
        recs._agronova_kechikish_belgilash()
        return recs

    def write(self, vals):
        # Moliyaviy yozuv tahrirlanmaydi — faqat storno (TZ 21.6).
        himoyalangan = {
            'sotib_olingan_sana', 'xarid_turi', 'kontragent_id', 'summa',
            'qqs_bormi', 'qqs_foizi', 'tolangan_summa', 'depozit_id',
            'qator_ids', 'tasdiqlangan_ruxsat_id', 'maqsad_ombor_id',
        }
        if himoyalangan & set(vals):
            for rec in self:
                if rec.holat in ('tasdiqlangan', 'qabul_qilindi'):
                    raise UserError(_(
                        "«%s» tasdiqlangan — moliyaviy ma'lumot "
                        "tahrirlanmaydi. Xato bo'lsa qaytarish hujjatini "
                        "rasmiylashtiring (TZ 21.6).", rec.display_name))
        res = super().write(vals)
        if 'sotib_olingan_sana' in vals:
            self._agronova_kechikish_belgilash()
        return res

    def _agronova_kechikish_belgilash(self):
        for rec in self:
            kiritilgan = fields.Datetime.context_timestamp(
                rec, rec.create_date or fields.Datetime.now()).date()
            rec.kechikib_kiritilgan = bool(
                rec.sotib_olingan_sana and rec.sotib_olingan_sana < kiritilgan)
        return True

    def unlink(self):
        if any(rec.holat != 'draft' for rec in self):
            raise UserError(_(
                "Tasdiqlangan kirim hujjati o'chirilmaydi — qaytarish "
                "hujjatini rasmiylashtiring."))
        return super().unlink()

    # ---------------------------------------------------------- tasdiqlash
    def action_tasdiqlash(self):
        """Tovarni zakupchik tranzitiga oladi va qarzni darhol yozadi."""
        for rec in self:
            if rec.holat != 'draft':
                raise UserError(_("Faqat qoralama kirim tasdiqlanadi."))
            if not rec.qator_ids:
                raise UserError(_("Bo'sh kirim hujjati tasdiqlanmaydi."))
            if rec.tasdiqlangan_ruxsat_id.holat != 'tasdiqlandi':
                raise UserError(_(
                    "Ruxsat hali tasdiqlanmagan — xarid rasmiylashtirilmaydi."))
            rec._check_narx_ogishi()
            rec._agronova_rekvizit_tekshir()
            rec.qator_ids._agronova_kuzatuv_tekshir()

            rec.tranzit_id = rec.zakupchik_id._agronova_tranzit()
            # 1. Tovar — yetkazib beruvchidan zakupchik tranzitiga.
            #    C2 (uskuna importi) omborga tushmaydi: u asosiy vosita,
            #    zaxira emas (TZ 10-bo'lim).
            if rec.xarid_turi != 'C2_import_uskuna':
                rec.picking_kirim_id = rec._agronova_tranzitga_kirim()
            # 2. Qarz — tovar nazorati o'tgan zahoti, omborchiga bog'liq emas.
            rec.faktura_id = rec._agronova_faktura_yaratish()
            rec.faktura_holati = 'kutilmoqda'
            # 3. Naqd bo'lsa depozitdan chiqim.
            if rec.xarid_turi == 'A_naqd':
                rec._agronova_depozitdan_chiqim()
            # 4. Transport va qo'shimcha xarajat — tannarxga (IAS 2).
            if rec.picking_kirim_id and (rec.transport_xarajati or
                                         rec.qoshimcha_xarajat):
                rec.landed_cost_id = rec._agronova_landed_cost()
            # 5. C2 — asosiy vosita sifatida ro'yxatga olinadi.
            if rec.xarid_turi == 'C2_import_uskuna':
                rec._agronova_asosiy_vosita()

            rec.write({'holat': 'tasdiqlangan',
                       'tranzit_sanasi': fields.Datetime.now()})
            rec._agronova_zayavka_holatini_yangilash()
            rec.message_post(body=_(
                "Xarid rasmiylashtirildi. Tovar «%(tranzit)s» da, qarz "
                "%(faktura)s hujjatida yozildi.",
                tranzit=rec.tranzit_id.display_name,
                faktura=rec.faktura_id.name or ''))
        return True

    # ------------------------------------------------------- tovar harakati
    def _agronova_picking_turi(self, kod):
        """Maqsad omborining kirim/ichki operatsiya turi."""
        self.ensure_one()
        wh = self.maqsad_ombor_id
        tur = wh.in_type_id if kod == 'incoming' else wh.int_type_id
        if not tur:
            raise UserError(_(
                "«%s» omborida %s operatsiya turi sozlanmagan.",
                wh.display_name, kod))
        return tur

    def _agronova_move_qiymatlari(self, qator, manba, maqsad, miqdor):
        return {
            # Odoo 19 da `stock.move.name` yo'q — hujjat matni
            # `description_picking` da yuriladi.
            'description_picking': qator.product_id.display_name,
            'product_id': qator.product_id.id,
            'product_uom_qty': miqdor,
            'product_uom': qator.olchov_birligi_id.id,
            'location_id': manba.id,
            'location_dest_id': maqsad.id,
            'company_id': self.company_id.id,
            'price_unit': qator.narx,
            'date': fields.Datetime.now(),
        }

    def _agronova_pickingni_yakunlash(self, picking, miqdorlar):
        """Miqdor va lotni qo'yib, harakatni yakunlaydi.

        `miqdorlar` — `{move: (miqdor, qator)}`.
        """
        picking = picking.sudo()
        picking.action_confirm()
        picking.action_assign()
        Lot = self.env['stock.lot'].sudo()
        for move, (miqdor, qator) in miqdorlar.items():
            move.quantity = miqdor
            move.picked = True
            if move.product_id.tracking != 'none':
                if not qator.lot_nomi:
                    raise UserError(_(
                        "«%s» tovarida lot/seriya kuzatuvi yoqilgan — "
                        "lot raqamini kiriting (TZ 8-bo'lim).",
                        move.product_id.display_name))
                lot = Lot.search([
                    ('name', '=', qator.lot_nomi),
                    ('product_id', '=', move.product_id.id),
                    ('company_id', '=', self.company_id.id),
                ], limit=1)
                if not lot:
                    lot_vals = {
                        'name': qator.lot_nomi,
                        'product_id': move.product_id.id,
                        'company_id': self.company_id.id,
                    }
                    if move.product_id.use_expiration_date:
                        if not qator.yaroqlilik_sanasi:
                            raise UserError(_(
                                "«%s» — yaroqlilik muddati majburiy "
                                "(dori-darmon / oziq-ovqat).",
                                move.product_id.display_name))
                        lot_vals['expiration_date'] = qator.yaroqlilik_sanasi
                    lot = Lot.create(lot_vals)
                move.move_line_ids.write({'lot_id': lot.id})
                qator.lot_id = lot.id
        picking._action_done()
        return picking

    def _agronova_tranzitga_kirim(self):
        """Yetkazib beruvchi -> zakupchik tranziti."""
        self.ensure_one()
        tur = self._agronova_picking_turi('incoming')
        manba = (self.kontragent_id.property_stock_supplier
                 or self.env.ref('stock.stock_location_suppliers'))
        # Hujjatni oqim yaratadi, foydalanuvchi emas — tasdiqlash
        # huquqi shu modulning ACL si bilan boshqariladi, shuning
        # uchun omborchi/zakupchikdan «Inventory/User» talab
        # qilinmaydi.
        picking = self.env['stock.picking'].sudo().create({
            'picking_type_id': tur.id,
            'partner_id': self.kontragent_id.id or False,
            'location_id': manba.id,
            'location_dest_id': self.tranzit_id.id,
            'origin': self.name,
            'company_id': self.company_id.id,
            'scheduled_date': fields.Datetime.now(),
        })
        miqdorlar = {}
        for qator in self.qator_ids:
            move = self.env['stock.move'].sudo().create(dict(
                self._agronova_move_qiymatlari(
                    qator, manba, self.tranzit_id, qator.miqdor),
                picking_id=picking.id))
            qator.move_kirim_id = move.id
            miqdorlar[move] = (qator.miqdor, qator)
        return self._agronova_pickingni_yakunlash(picking, miqdorlar)

    def _agronova_omborga_qabul(self):
        """Zakupchik tranziti -> asosiy ombor (omborchi tasdig'idan keyin)."""
        self.ensure_one()
        tur = self._agronova_picking_turi('internal')
        maqsad = self.maqsad_ombor_id.lot_stock_id
        picking = self.env['stock.picking'].sudo().create({
            'picking_type_id': tur.id,
            'location_id': self.tranzit_id.id,
            'location_dest_id': maqsad.id,
            'origin': self.name,
            'company_id': self.company_id.id,
            'scheduled_date': fields.Datetime.now(),
        })
        miqdorlar = {}
        for qator in self.qator_ids:
            if qator.qabul_miqdor <= 0:
                continue
            move = self.env['stock.move'].sudo().create(dict(
                self._agronova_move_qiymatlari(
                    qator, self.tranzit_id, maqsad, qator.qabul_miqdor),
                picking_id=picking.id))
            qator.move_qabul_id = move.id
            miqdorlar[move] = (qator.qabul_miqdor, qator)
        if not miqdorlar:
            picking.unlink()
            raise UserError(_(
                "Bironta ham qatorda qabul miqdori ko'rsatilmagan."))
        return self._agronova_pickingni_yakunlash(picking, miqdorlar)

    # ------------------------------------------------------------- moliya
    def _agronova_bozor_kontragenti(self):
        """«O'z nomidan» xarid uchun umumiy kontragent."""
        Partner = self.env['res.partner'].sudo()
        partner = Partner.search([('ref', '=', 'AGRONOVA_BOZOR')], limit=1)
        if not partner:
            partner = Partner.create({
                'name': _("Bozor (o'z nomidan xarid)"),
                'ref': 'AGRONOVA_BOZOR',
                'shaxs_turi': 'jismoniy',
                'supplier_rank': 1,
                'company_id': False,
            })
        return partner

    def _agronova_xarid_jurnali(self):
        jurnal = self.env['account.journal'].search([
            ('type', '=', 'purchase'),
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        if not jurnal:
            raise UserError(_(
                "«%s» korxonasida xarid jurnali topilmadi — faktura "
                "yaratilmaydi.", self.company_id.display_name))
        return jurnal

    def _agronova_faktura_yaratish(self):
        """Qarz hujjati — tovardan mustaqil, o'sha zahoti yoziladi."""
        self.ensure_one()
        partner = self.kontragent_id or self._agronova_bozor_kontragenti()
        qatorlar = []
        for qator in self.qator_ids:
            qatorlar.append((0, 0, {
                'product_id': qator.product_id.id,
                'name': qator.product_id.display_name,
                'quantity': qator.miqdor,
                'product_uom_id': qator.olchov_birligi_id.id,
                'price_unit': qator.narx,
            }))
        move = self.env['account.move'].sudo().create({
            'move_type': 'in_invoice',
            'partner_id': partner.id,
            'invoice_date': self.sotib_olingan_sana,
            'date': self.sotib_olingan_sana,
            'journal_id': self._agronova_xarid_jurnali().id,
            'company_id': self.company_id.id,
            'ref': self.name,
            'invoice_line_ids': qatorlar,
        })
        move.action_post()
        return move

    def _agronova_depozitdan_chiqim(self):
        """Naqd xarid — pul zakupchik depozitidan chiqadi (TZ 12)."""
        self.ensure_one()
        self.depozit_harakat_id = self.depozit_id._chiqim_yozish(
            summa=self.tolangan_summa,
            izoh=_("Xarid %s", self.name),
            manba=self,
            sana=self.sotib_olingan_sana,
        )
        return True

    def _agronova_landed_cost(self):
        """Transport va qo'shimcha xarajat tannarxga (IAS 2, TZ 8-bo'lim).

        Taqsimotni Odoo o'zi qiladi — qo'lda hisoblanmaydi (TZ 21.3).
        """
        self.ensure_one()
        mahsulot = self._agronova_landed_cost_mahsuloti()
        qatorlar = []
        if self.transport_xarajati:
            qatorlar.append((0, 0, {
                'product_id': mahsulot.id,
                'name': _("Transport — %s", self.name),
                'price_unit': self.transport_xarajati,
                'split_method': 'by_current_cost_price',
            }))
        if self.qoshimcha_xarajat:
            qatorlar.append((0, 0, {
                'product_id': mahsulot.id,
                'name': _("Qo'shimcha xarajat — %s", self.name),
                'price_unit': self.qoshimcha_xarajat,
                'split_method': 'by_current_cost_price',
            }))
        lc = self.env['stock.landed.cost'].sudo().create({
            'account_journal_id': self._agronova_landed_cost_jurnali().id,
            'date': self.sotib_olingan_sana,
            'target_model': 'picking',
            'picking_ids': [(6, 0, self.picking_kirim_id.ids)],
            'company_id': self.company_id.id,
            'cost_lines': qatorlar,
            'vendor_bill_id': self.faktura_id.id,
        })
        lc.compute_landed_cost()
        lc.button_validate()
        return lc

    def _agronova_landed_cost_jurnali(self):
        """Landed Cost jurnali: korxona sozlamasi -> ombor -> umumiy."""
        jurnal = self.company_id.lc_journal_id
        if not jurnal:
            jurnal = self.qator_ids.product_id.categ_id.with_company(
                self.company_id).property_stock_journal[:1]
        if not jurnal:
            jurnal = self.env['account.journal'].search([
                ('type', '=', 'general'),
                ('company_id', '=', self.company_id.id)], limit=1)
        if not jurnal:
            raise UserError(_(
                "«%s» korxonasida Landed Cost uchun jurnal topilmadi — "
                "sozlamalarda ko'rsating.", self.company_id.display_name))
        return jurnal

    def _agronova_landed_cost_mahsuloti(self):
        Product = self.env['product.product'].sudo()
        mahsulot = Product.search([('default_code', '=', 'AGRONOVA_LC')], limit=1)
        if not mahsulot:
            mahsulot = Product.create({
                'name': _("Xarid qo'shimcha xarajati"),
                'default_code': 'AGRONOVA_LC',
                'type': 'service',
                'landed_cost_ok': True,
                'purchase_ok': True,
            })
        elif not mahsulot.landed_cost_ok:
            mahsulot.landed_cost_ok = True
        return mahsulot

    def _agronova_asosiy_vosita(self):
        """C2 — uskuna importi: omborga emas, Assets ga (TZ 10-bo'lim)."""
        self.ensure_one()
        Asset = self.env['account.asset'].sudo()
        for qator in self.qator_ids:
            hisob = (qator.product_id.property_account_expense_id
                     or qator.product_id.categ_id.property_account_expense_categ_id)
            if not hisob:
                raise UserError(_(
                    "«%s» uchun xarajat hisobi sozlanmagan — asosiy vosita "
                    "kartochkasi ochilmaydi.", qator.product_id.display_name))
            qator.asset_id = Asset.create({
                'name': _("%(tovar)s (%(hujjat)s)",
                          tovar=qator.product_id.display_name, hujjat=self.name),
                'company_id': self.company_id.id,
                'original_value': qator.summa,
                'acquisition_date': self.sotib_olingan_sana,
                'account_asset_id': hisob.id,
                'account_depreciation_id': hisob.id,
                'account_depreciation_expense_id': hisob.id,
                'journal_id': self.env['account.journal'].search([
                    ('type', '=', 'general'),
                    ('company_id', '=', self.company_id.id)], limit=1).id,
            }).id
        return True

    # ------------------------------------------------------ omborchi qabuli
    def action_qabul_wizard(self):
        self.ensure_one()
        if self.holat != 'tasdiqlangan':
            raise UserError(_(
                "Faqat tranzitdagi tovar qabul qilinadi."))
        return {
            'type': 'ir.actions.act_window',
            'name': _("Tovarni qabul qilish va baholash"),
            'res_model': 'agronova.qabul.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_kirim_id': self.id},
        }

    def _agronova_qabul_yakunlash(self, ballar):
        """Wizard chaqiradi: tovarni omborga o'tkazadi va KPI yozadi."""
        self.ensure_one()
        self.picking_qabul_id = self._agronova_omborga_qabul()
        self.write(dict(
            ballar,
            holat='qabul_qilindi',
            qabul_sanasi=fields.Datetime.now(),
            omborchi_id=self.env.user.id,
        ))
        self._agronova_qabul_kpi()
        self._agronova_zayavka_holatini_yangilash()
        self.message_post(body=_(
            "Omborga qabul qilindi. Ballar — to'liqlik: %(t)s, muddat: "
            "%(m)s, sifat: %(s)s (%(sabab)s).",
            t=self.ball_toliqlik, m=self.ball_muddat, s=self.ball_sifat,
            sabab=dict(BALL_SABABI).get(self.ball_sababi, '')))
        return True

    def _agronova_qabul_kpi(self):
        """Uch o'lchovli baho + narx tejami KPI ga yoziladi (TZ 13)."""
        self.ensure_one()
        # Obyektiv sabab zakupchik ballini tushirmaydi (TZ 7-bo'lim).
        if self.ball_sababi != 'obyektiv_sabab':
            for mezon, ball in (('toliqlik', self.ball_toliqlik),
                                ('muddat', self.ball_muddat),
                                ('sifat', self.ball_sifat)):
                self.env['agronova.kpi']._agronova_ball_yozish(
                    user=self.zakupchik_id, mezon=mezon, manba=self,
                    qiymat=ball, norma=10.0,
                    nizoli=self.ball_sababi == 'nizoli')
        # Narx tejami — bu mezon majburiy, aks holda zakupchik jarimadan
        # qo'rqib eng yaqin va eng qimmat joydan olib keladi (TZ 13).
        ruxsat = self.tasdiqlangan_ruxsat_id
        if ruxsat.norma_narx:
            qator = self.qator_ids.filtered(
                lambda q: q.product_id == ruxsat.product_id)[:1]
            if qator:
                tejam = 100.0 * (
                    ruxsat.norma_narx - qator.narx) / ruxsat.norma_narx
                self.env['agronova.kpi']._agronova_ball_yozish(
                    user=self.zakupchik_id, mezon='narx_tejami', manba=self,
                    qiymat=tejam, norma=0.0)
        return True

    def _agronova_zayavka_holatini_yangilash(self):
        self.ensure_one()
        zayavka = self.zayavka_id
        if not zayavka or zayavka.holat in ('yopildi', 'rad_etildi'):
            return
        if all(q.qoldiq_miqdor <= 0 for q in zayavka.qator_ids):
            zayavka.holat = 'yopildi'
        elif any(q.bajarilgan_miqdor > 0 for q in zayavka.qator_ids):
            zayavka.holat = 'qisman_bajarildi'
        return True

    def action_bekor(self):
        for rec in self:
            if rec.holat != 'draft':
                raise UserError(_(
                    "Tasdiqlangan kirim bekor qilinmaydi — qaytarish "
                    "hujjatini rasmiylashtiring (TZ 21.6)."))
            rec.holat = 'bekor'
        return True

    def action_qaytarish(self):
        self.ensure_one()
        if self.holat not in ('tasdiqlangan', 'qabul_qilindi'):
            raise UserError(_("Faqat rasmiylashtirilgan xarid qaytariladi."))
        return {
            'type': 'ir.actions.act_window',
            'name': _("Tovarni qaytarish"),
            'res_model': 'agronova.qaytarish',
            'view_mode': 'form',
            'context': {'default_kirim_id': self.id},
        }

    # ---------------------------------------------------------------- cron
    @api.model
    def _cron_tranzit_nazorati(self):
        """Tranzitda uzoq qolgan tovar bo'yicha eslatma (TZ 7-bo'lim)."""
        kun = int(self.env['ir.config_parameter'].sudo().get_param(
            'agronova_zakupka.tranzit_ogohlantirish_kun', 3) or 3)
        chegara = fields.Datetime.now() - relativedelta(days=kun)
        kechikkanlar = self.sudo().search([
            ('holat', '=', 'tasdiqlangan'),
            ('tranzit_sanasi', '<', chegara),
        ])
        for rec in kechikkanlar:
            if rec.activity_ids.filtered(
                    lambda a: a.user_id == rec.zakupchik_id):
                continue
            rec.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=rec.zakupchik_id.id,
                summary=_("Tranzitda qolgan tovar: %s", rec.name),
                note=_("Tovar %(kun)s kundan beri sizning tranzitingizda "
                       "turibdi va balansda sizning zimmangizda. Omborchiga "
                       "topshiring.", kun=rec.tranzit_kunlari))
        return True


class AgroNovaKirimQatori(models.Model):
    _name = 'agronova.kirim.qatori'
    _description = "Xarid kirim qatori"
    _order = 'kirim_id, id'

    kirim_id = fields.Many2one(
        'agronova.kirim', string="Kirim hujjati", required=True,
        ondelete='cascade', index=True)
    product_id = fields.Many2one(
        'product.product', string="Tovar", required=True,
        domain="[('purchase_ok', '=', True)]")
    zayavka_qatori_id = fields.Many2one(
        'agronova.zayavka.qatori', string="Zayavka qatori", index='btree_not_null',
        help="Qisman bajarilishni kuzatish uchun zayavka qatoriga bog'lanadi.")
    miqdor = fields.Float("Sotib olingan miqdor", required=True, default=1.0)
    olchov_birligi_id = fields.Many2one(
        'uom.uom', string="O'lchov birligi",
        compute='_compute_olchov_birligi_id', store=True, readonly=False)
    narx = fields.Monetary("Narx (birlik)", required=True)
    summa = fields.Monetary("Summa", compute='_compute_summa', store=True)
    currency_id = fields.Many2one(
        'res.currency', related='kirim_id.currency_id', readonly=True)

    qabul_miqdor = fields.Float(
        "Qabul qilingan miqdor", copy=False,
        help="Omborchi haqiqatda qabul qilgan miqdor.")
    lot_nomi = fields.Char(
        "Lot / seriya raqami",
        help="Kuzatuv yoqilgan tovarda majburiy (TZ 8-bo'lim).")
    yaroqlilik_sanasi = fields.Datetime(
        "Yaroqlilik muddati",
        help="Dori-darmon va oziq-ovqatda majburiy.")
    lot_id = fields.Many2one(
        'stock.lot', string="Lot", readonly=True, copy=False)
    kuzatuv_shart = fields.Boolean(
        "Kuzatuv majburiy", related='product_id.seriya_kuzatuv_shart',
        readonly=True)

    move_kirim_id = fields.Many2one(
        'stock.move', string="Tranzit harakati", readonly=True, copy=False)
    move_qabul_id = fields.Many2one(
        'stock.move', string="Ombor harakati", readonly=True, copy=False)
    asset_id = fields.Many2one(
        'account.asset', string="Asosiy vosita", readonly=True, copy=False)

    @api.depends('product_id')
    def _compute_olchov_birligi_id(self):
        for qator in self:
            qator.olchov_birligi_id = qator.product_id.uom_id

    @api.depends('miqdor', 'narx')
    def _compute_summa(self):
        for qator in self:
            qator.summa = qator.miqdor * qator.narx

    @api.constrains('miqdor', 'narx', 'qabul_miqdor')
    def _check_miqdor(self):
        for qator in self:
            if qator.miqdor <= 0 or qator.narx <= 0:
                raise ValidationError(_(
                    "Miqdor va narx noldan katta bo'lishi kerak."))
            if qator.qabul_miqdor and qator.qabul_miqdor > qator.miqdor:
                raise ValidationError(_(
                    "«%s»: qabul qilingan miqdor sotib olingandan ko'p "
                    "bo'lolmaydi.", qator.product_id.display_name))

    @api.constrains('lot_nomi', 'yaroqlilik_sanasi', 'product_id')
    def _check_kuzatuv(self):
        self.filtered(
            lambda q: q.kirim_id.holat != 'draft')._agronova_kuzatuv_tekshir()

    def _agronova_kuzatuv_tekshir(self):
        """Lot va yaroqlilik muddati majburiyati (TZ 8-bo'lim).

        C2 (uskuna importi) bundan mustasno: u omborga umuman tushmaydi,
        seriya raqami `account.asset` kartochkasida yuriladi.
        """
        for qator in self:
            if qator.kirim_id.xarid_turi == 'C2_import_uskuna':
                continue
            if qator.product_id.tracking != 'none' and not qator.lot_nomi:
                raise ValidationError(_(
                    "«%s» tovarida lot/seriya kuzatuvi majburiy "
                    "(TZ 8-bo'lim).", qator.product_id.display_name))
            if qator.product_id.use_expiration_date and not qator.yaroqlilik_sanasi:
                raise ValidationError(_(
                    "«%s» — yaroqlilik muddati majburiy (dori-darmon / "
                    "oziq-ovqat).", qator.product_id.display_name))
