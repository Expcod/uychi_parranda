# -*- coding: utf-8 -*-
"""So'yish jarayoni va sortirovka (TZ 4, 7-band).

Bitta hujjatda ikkita narsa qayd etiladi:

1. **So'yish** — nechta tovuq so'yildi, nechtasi nobud/brak bo'ldi;
2. **Sortirovka** — chiqqan mahsulot kategoriyalarga bo'linadi: butun
   tovuq, qanot, son, ko'krak, jigar va hokazo. Har biri alohida qator.

Tasdiqlanganda (faqat **ichki** partiyada):

* tirik tovuq ombordan hisobdan chiqadi, FIFO qiymati partiya xarajatiga
  tushadi;
* sortirovka natijasi omborga kirim qilinadi.

Tayyor mahsulotlarning qiymati partiyaning ishlab chiqarish xarajatidan
bo'linadi. Standart holda **vazn bo'yicha**, lekin har qatorga «qiymat
ulushi (%)» qo'yilsa — o'sha nisbatda. Bu kerak, chunki 1 kg file va
1 kg oyoq bir xil turmaydi.

**Tashqi mijoz** partiyasida ombor harakati yo'q: mahsulot mijozning
mulki, biz faqat xizmat haqi olamiz.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class AgroNovaSoyishNatija(models.Model):
    """Sortirovka natijasi — bitta mahsulot qatori."""
    _name = 'agronova.soyish.natija'
    _description = "So'yish — sortirovka natijasi"
    _order = 'jarayon_id, id'

    jarayon_id = fields.Many2one(
        'agronova.soyish.jarayon', string="So'yish hujjati", required=True,
        ondelete='cascade', index=True)
    product_id = fields.Many2one(
        'product.product', string="Mahsulot", required=True,
        domain="[('is_storable', '=', True)]")
    miqdor_kg = fields.Float(
        "Miqdor (kg)", required=True, digits='Product Unit')
    ulush_foiz = fields.Float(
        "Qiymat ulushi (%)",
        help="Bo'sh qoldirilsa tannarx vazn bo'yicha bo'linadi. "
             "To'ldirilsa — shu nisbatda. Qatorlar yig'indisi 100 bo'lsin.")
    qiymat = fields.Monetary("Qiymati", readonly=True, copy=False)
    lot_id = fields.Many2one(
        'stock.lot', string="Lot", readonly=True, copy=False,
        help="Kuzatuv uchun avtomat beriladi: partiya/sana/mahsulot.")
    move_id = fields.Many2one(
        'stock.move', string="Ombor harakati", readonly=True, copy=False)
    currency_id = fields.Many2one(
        'res.currency', related='jarayon_id.currency_id', readonly=True)
    tushka_ulush_foiz = fields.Float(
        "Chiqishdagi ulushi (%)", compute='_compute_tushka_ulush', store=True,
        aggregator='avg', digits=(16, 2),
        help="Shu mahsulot hujjatdagi jami tayyor mahsulotning necha "
             "foizi: masalan file 28%, qanot 11%.")
    dona_ga_kg = fields.Float(
        "1 tovuqdan (kg)", compute='_compute_tushka_ulush', store=True,
        aggregator='avg', digits=(16, 3),
        help="Shu mahsulot so'yilgan har bir tovuqdan o'rtacha necha kg "
             "chiqdi.")

    # Hisobotda filtr va guruhlash uchun — hujjatdan nusxa
    sana = fields.Date(related='jarayon_id.sana', store=True, index=True,
                       string="Sana")
    partiya_id = fields.Many2one(related='jarayon_id.partiya_id', store=True,
                                 string="Partiya")
    manba = fields.Selection(related='jarayon_id.manba', store=True,
                             string="Kelib chiqishi")
    holat = fields.Selection(related='jarayon_id.holat', store=True,
                             string="Hujjat holati")

    _miqdor_musbat = models.Constraint(
        'CHECK (miqdor_kg > 0)', "Miqdor noldan katta bo'lishi kerak.")

    @api.depends('miqdor_kg', 'jarayon_id.tushka_vazn_kg',
                 'jarayon_id.soyilgan_son')
    def _compute_tushka_ulush(self):
        for line in self:
            j = line.jarayon_id
            line.tushka_ulush_foiz = (line.miqdor_kg / j.tushka_vazn_kg * 100.0
                                      if j.tushka_vazn_kg else 0.0)
            line.dona_ga_kg = (line.miqdor_kg / j.soyilgan_son
                               if j.soyilgan_son else 0.0)


class AgroNovaSoyishJarayon(models.Model):
    _name = 'agronova.soyish.jarayon'
    _description = "So'yish jarayoni"
    _inherit = ['mail.thread']
    _order = 'sana desc, id desc'

    name = fields.Char("Hujjat", compute='_compute_name', store=True)
    sana = fields.Date(
        "So'yish sanasi", required=True, default=fields.Date.context_today,
        tracking=True, index=True)
    partiya_id = fields.Many2one(
        'agronova.soyish.partiya', string="Partiya", required=True,
        ondelete='cascade', index=True,
        domain="[('holat', '=', 'active')]")
    manba = fields.Selection(
        related='partiya_id.manba', string="Kelib chiqishi", store=True,
        readonly=True)
    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True, readonly=True,
        store=True, precompute=True, compute='_compute_company_id')
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)
    holat = fields.Selection(
        [('draft', "Qoralama"), ('done', "Tasdiqlangan")],
        string="Holati", default='draft', required=True, tracking=True,
        copy=False)

    soyilgan_son = fields.Integer("So'yilgan (dona)", required=True,
                                  tracking=True)
    nobud_son = fields.Integer("Nobud / brak (dona)", tracking=True)
    natija_ids = fields.One2many(
        'agronova.soyish.natija', 'jarayon_id', string="Sortirovka natijasi")
    tushka_vazn_kg = fields.Float(
        "Jami tayyor mahsulot (kg)", compute='_compute_tushka', store=True,
        digits='Product Unit')
    chiqim_foiz = fields.Float(
        "Chiqim foizi (%)", compute='_compute_tushka', store=True,
        aggregator='avg')
    tirik_vazn_kg = fields.Float(
        "Tirik vazn (kg)", compute='_compute_tushka', store=True,
        digits='Product Unit',
        help="Partiyaning tirik vaznidan shu hujjatga to'g'ri keladigan "
             "qismi (so'yilgan dona ulushi bo'yicha).")
    yoqotish_kg = fields.Float(
        "Yo'qotish (kg)", compute='_compute_tushka', store=True,
        digits='Product Unit',
        help="Tirik vazn − tayyor mahsulot: pat, qon, ichak, chiqindi.")
    ortacha_tushka_kg = fields.Float(
        "1 tovuqdan chiqqan (kg)", compute='_compute_tushka', store=True,
        aggregator='avg', digits=(16, 3))

    # --- apparat bosqichlaridan keyingi vazn (ixtiyoriy). Tozalash va
    # ichini tozalashni apparat qiladi; har biridan keyin tortilsa,
    # apparat va bo'laklashda qancha yo'qotish bo'lgani alohida ko'rinadi.
    tozalangan_vazn_kg = fields.Float(
        "Tozalangan tushka (kg)", digits='Product Unit', tracking=True,
        help="Patdan tozalanib, kallasi va oyog'i olingan holatdagi vazn — "
             "so'yish liniyasiga kirgan tushka.")
    ichaksiz_vazn_kg = fields.Float(
        "Ichi tozalangan tushka (kg)", digits='Product Unit', tracking=True,
        help="Ichak-chovoq olingandan keyin, bo'laklashdan oldingi vazn.")
    tozalash_chiqim_foiz = fields.Float(
        "Tozalash chiqimi (%)", compute='_compute_bosqich_vazn', store=True,
        aggregator='avg', digits=(16, 2),
        help="Tozalangan tushka / tirik vazn × 100.")
    ichak_chiqim_foiz = fields.Float(
        "Ichini tozalash chiqimi (%)", compute='_compute_bosqich_vazn',
        store=True, aggregator='avg', digits=(16, 2),
        help="Ichi tozalangan tushka / tozalangan tushka × 100.")
    bolaklash_yoqotish_kg = fields.Float(
        "Bo'laklashdagi yo'qotish (kg)", compute='_compute_bosqich_vazn',
        store=True, digits='Product Unit',
        help="Ichi tozalangan tushka − sortirovkada chiqqan mahsulot.")

    # --- vaqt va xodimlar
    boshlanish = fields.Datetime("Boshlandi", tracking=True)
    tugash = fields.Datetime("Tugadi", tracking=True)
    davomiylik_soat = fields.Float(
        "Davomiyligi (soat)", compute='_compute_vaqt', store=True,
        digits=(16, 2))
    dona_soat = fields.Float(
        "Liniya tezligi (dona/soat)", compute='_compute_vaqt', store=True,
        aggregator='avg', digits=(16, 1))
    ishchi_ids = fields.One2many(
        'agronova.soyish.ishchi', 'jarayon_id', string="Xodimlar ishi")
    xodim_soni = fields.Integer(
        "Xodimlar soni", compute='_compute_xodim', store=True,
        aggregator='avg')
    dona_xodim = fields.Float(
        "1 xodimga (dona)", compute='_compute_xodim', store=True,
        aggregator='avg', digits=(16, 1),
        help="So'yilgan tovuq / ishlagan xodimlar soni.")
    ishbay_summa = fields.Monetary(
        "Ishbay haqi", compute='_compute_xodim', store=True)
    xodim_brak_son = fields.Integer(
        "Xodim aybi bilan brak", compute='_compute_xodim', store=True)
    tirik_qiymat = fields.Monetary(
        "Tirik tovuq qiymati", readonly=True, copy=False,
        help="Ombordan hisobdan chiqqan FIFO qiymati.")
    analytic_line_ids = fields.Many2many(
        'account.analytic.line', string="Analitik qatorlar", copy=False,
        readonly=True,
        help="Shu hujjat yozgan qatorlar. Storno qilinganda o'chiriladi.")
    tirik_move_id = fields.Many2one(
        'stock.move', string="Tirik tovuq harakati", readonly=True, copy=False,
        help="Storno qilinganda aynan shu harakatdagi lotlar qaytariladi.")
    izoh = fields.Text("Izoh")

    _soyilgan_musbat = models.Constraint(
        'CHECK (soyilgan_son > 0)',
        "So'yilgan tovuq soni noldan katta bo'lishi kerak.")

    # ------------------------------------------------------------- compute
    @api.depends('partiya_id')
    def _compute_company_id(self):
        for j in self:
            j.company_id = j.partiya_id.company_id or self.env.company

    @api.depends('natija_ids.miqdor_kg', 'soyilgan_son',
                 'partiya_id.tirik_vazn_kg', 'partiya_id.tirik_son')
    def _compute_tushka(self):
        for j in self:
            j.tushka_vazn_kg = sum(j.natija_ids.mapped('miqdor_kg'))
            # Shu hujjatga to'g'ri keladigan tirik vazn — so'yilgan dona
            # ulushi bo'yicha (partiya bir necha kunda so'yilishi mumkin).
            p = j.partiya_id
            tirik = (p.tirik_vazn_kg * j.soyilgan_son / p.tirik_son
                     if p.tirik_son else 0.0)
            j.tirik_vazn_kg = tirik
            j.chiqim_foiz = (j.tushka_vazn_kg / tirik * 100.0) if tirik else 0.0
            j.yoqotish_kg = max(tirik - j.tushka_vazn_kg, 0.0) if tirik else 0.0
            j.ortacha_tushka_kg = (j.tushka_vazn_kg / j.soyilgan_son
                                   if j.soyilgan_son else 0.0)

    @api.depends('tirik_vazn_kg', 'tozalangan_vazn_kg', 'ichaksiz_vazn_kg',
                 'tushka_vazn_kg')
    def _compute_bosqich_vazn(self):
        for j in self:
            j.tozalash_chiqim_foiz = (
                j.tozalangan_vazn_kg / j.tirik_vazn_kg * 100.0
                if j.tozalangan_vazn_kg and j.tirik_vazn_kg else 0.0)
            j.ichak_chiqim_foiz = (
                j.ichaksiz_vazn_kg / j.tozalangan_vazn_kg * 100.0
                if j.ichaksiz_vazn_kg and j.tozalangan_vazn_kg else 0.0)
            j.bolaklash_yoqotish_kg = (
                max(j.ichaksiz_vazn_kg - j.tushka_vazn_kg, 0.0)
                if j.ichaksiz_vazn_kg else 0.0)

    @api.depends('boshlanish', 'tugash', 'soyilgan_son')
    def _compute_vaqt(self):
        for j in self:
            soat = 0.0
            if j.boshlanish and j.tugash and j.tugash > j.boshlanish:
                soat = (j.tugash - j.boshlanish).total_seconds() / 3600.0
            j.davomiylik_soat = soat
            j.dona_soat = j.soyilgan_son / soat if soat else 0.0

    @api.depends('ishchi_ids.employee_id', 'ishchi_ids.summa',
                 'ishchi_ids.brak_son', 'soyilgan_son')
    def _compute_xodim(self):
        for j in self:
            j.xodim_soni = len(j.ishchi_ids.employee_id)
            j.dona_xodim = (j.soyilgan_son / j.xodim_soni
                            if j.xodim_soni else 0.0)
            j.ishbay_summa = sum(j.ishchi_ids.mapped('summa'))
            j.xodim_brak_son = sum(j.ishchi_ids.mapped('brak_son'))

    @api.depends('partiya_id', 'sana')
    def _compute_name(self):
        for j in self:
            j.name = "%s / %s" % (j.partiya_id.name or "?", j.sana or "")

    # ---------------------------------------------------------------- yozish
    @api.model_create_multi
    def create(self, vals_list):
        yozuvlar = super().create(vals_list)
        for j in yozuvlar:
            j.partiya_id._tekshir_ochiq(_("so'yish jarayoni"))
        return yozuvlar

    # Tasdiqdan keyin ham tahrirlansa bo'ladigan maydonlar: ular ombor va
    # tannarxga ta'sir qilmaydi. Xodimlar ishi ko'pincha smena oxirida
    # kiritiladi — hujjat esa undan oldin tasdiqlangan bo'lishi mumkin.
    _TASDIQDAN_KEYIN_OCHIQ = {
        'izoh', 'message_ids', 'message_follower_ids',
        'ishchi_ids', 'boshlanish', 'tugash',
        'tozalangan_vazn_kg', 'ichaksiz_vazn_kg',
    }

    def write(self, vals):
        if not self.env.context.get('agronova_soyish_post'):
            for j in self:
                if j.holat == 'done' and set(vals) - self._TASDIQDAN_KEYIN_OCHIQ:
                    raise UserError(_(
                        "«%s» so'yish hujjati tasdiqlangan — tahrirlanmaydi.",
                        j.display_name))
        return super().write(vals)

    def unlink(self):
        for j in self:
            if j.holat == 'done':
                raise UserError(_("Tasdiqlangan hujjat o'chirilmaydi."))
        return super().unlink()

    @api.constrains('soyilgan_son', 'nobud_son', 'partiya_id')
    def _check_son(self):
        for j in self:
            p = j.partiya_id
            boshqa = sum((p.jarayon_ids - j).filtered(
                lambda x: x.holat == 'done').mapped('soyilgan_son'))
            boshqa += sum((p.jarayon_ids - j).filtered(
                lambda x: x.holat == 'done').mapped('nobud_son'))
            if boshqa + j.soyilgan_son + j.nobud_son > p.tirik_son:
                raise ValidationError(_(
                    "«%(p)s» partiyasiga %(kelgan)s dona tovuq kelgan, "
                    "jami %(jami)s dona so'yish/brak ko'rsatilmoqda.",
                    p=p.name, kelgan=p.tirik_son,
                    jami=boshqa + j.soyilgan_son + j.nobud_son))
        self._check_ishchi_son()

    @api.constrains('boshlanish', 'tugash')
    def _check_vaqt(self):
        for j in self:
            if j.boshlanish and j.tugash and j.tugash < j.boshlanish:
                raise ValidationError(_(
                    "So'yish tugash vaqti boshlanishidan oldin bo'lmaydi."))

    def _check_ishchi_son(self):
        """Bir bosqichda xodimlar jami so'yilgandan ko'p tovuq ishlamaydi.

        Masalan 1000 dona so'yilgan bo'lsa, bo'laklashda barcha
        xodimlarning donasi (brak bilan) 1000 dan oshmasligi kerak — aks
        holda kimdir ikki marta yozilgan.
        """
        for j in self:
            if not j.ishchi_ids:
                continue
            for bosqich in j.ishchi_ids.bosqich_id:
                qatorlar = j.ishchi_ids.filtered(
                    lambda q: q.bosqich_id == bosqich)
                jami = sum(qatorlar.mapped('dona')) + sum(
                    qatorlar.mapped('brak_son'))
                if jami > j.soyilgan_son:
                    raise ValidationError(_(
                        "«%(b)s» bosqichida xodimlar jami %(jami)s dona "
                        "ko'rsatilgan, hujjatda esa %(s)s dona so'yilgan.",
                        b=bosqich.name, jami=jami, s=j.soyilgan_son))

    # ----------------------------------------------------------- tasdiqlash
    def action_tasdiqlash(self):
        for j in self:
            if j.holat == 'done':
                continue
            if not j.natija_ids:
                raise UserError(_(
                    "Sortirovka natijasi kiritilmagan — qanday mahsulot "
                    "chiqqani ko'rsatilishi kerak."))
            j.partiya_id._tekshir_ochiq(_("so'yishni tasdiqlash"))
            if j.manba == 'ichki':
                j._tirikni_chiqarish()
                j._natijani_kirim_qilish()
            j.with_context(agronova_soyish_post=True).holat = 'done'
            j.message_post(body=_(
                "So'yildi: %(s)s dona, chiqdi %(kg).1f kg, chiqim %(c).2f%%",
                s=j.soyilgan_son, kg=j.tushka_vazn_kg, c=j.chiqim_foiz))
        return True

    def action_storno(self):
        """Tasdiqlangan hujjatni qaytaradi: ombor va analitika teskarilanadi.

        So'yishda xato bo'lishi mumkin — noto'g'ri miqdor, noto'g'ri
        kategoriya. Hujjatni o'chirib tashlab bo'lmaydi (ombor harakati
        qolib ketadi), shuning uchun teskari harakat yaratiladi va hujjat
        qoralamaga qaytadi.
        """
        for j in self:
            if j.holat != 'done':
                raise UserError(_("Faqat tasdiqlangan hujjat storno qilinadi."))
            j.partiya_id._tekshir_ochiq(_("storno"))
            if j.manba == 'ichki':
                wh = j._ombor()
                ishlab = j._ishlab_chiqarish_joyi()

                # 1. Tayyor mahsulotni ombordan qaytarib olamiz
                for line in j.natija_ids.filtered(lambda l: l.move_id):
                    qaytish = self.env['stock.move'].sudo().create({
                        'product_id': line.product_id.id,
                        'product_uom_qty': line.miqdor_kg,
                        'product_uom': line.product_id.uom_id.id,
                        'location_id': wh.lot_stock_id.id,
                        'location_dest_id': ishlab.id,
                        'company_id': j.company_id.id,
                        'origin': _("STORNO: %s", j.display_name),
                    })
                    qaytish._action_confirm()
                    qaytish._action_assign()
                    qaytish.quantity = line.miqdor_kg
                    if line.lot_id:
                        qaytish.move_line_ids.write({'lot_id': line.lot_id.id})
                    qaytish.picked = True
                    qaytish._action_done()
                    line.write({'move_id': False, 'qiymat': 0.0,
                                'lot_id': False})

                # 2. Tirik tovuqni omborga qaytaramiz
                if j.tirik_qiymat:
                    dona = j.soyilgan_son + j.nobud_son
                    product = j.partiya_id.product_id
                    qaytish = self.env['stock.move'].sudo().create({
                        'product_id': product.id,
                        'product_uom_qty': dona,
                        'product_uom': product.uom_id.id,
                        'location_id': ishlab.id,
                        'location_dest_id': wh.lot_stock_id.id,
                        'company_id': j.company_id.id,
                        'price_unit': j.tirik_qiymat / dona if dona else 0.0,
                        'origin': _("STORNO: %s", j.display_name),
                    })
                    qaytish._action_confirm()
                    qaytish._action_assign()
                    qaytish.quantity = dona
                    # Tirik tovuq lot bilan kuzatilsa, aynan chiqqan lotni
                    # qaytaramiz — aks holda Odoo lot so'rab rad etadi.
                    asl_qatorlar = j.tirik_move_id.move_line_ids
                    if not asl_qatorlar and product.tracking != 'none':
                        # Eski hujjatlarda `tirik_move_id` yo'q (maydon keyin
                        # qo'shilgan). Ishlab chiqarish joyidagi qoldiqdan
                        # lotni topamiz — tovuq o'sha yerga chiqqan.
                        asl_qatorlar = self.env['stock.quant'].sudo().search([
                            ('product_id', '=', product.id),
                            ('location_id', '=', ishlab.id),
                            ('lot_id', '!=', False),
                        ], limit=5)
                    if asl_qatorlar and asl_qatorlar[0].lot_id:
                        qaytish.move_line_ids.unlink()
                        qolgan = dona
                        for asl in asl_qatorlar:
                            if qolgan <= 0:
                                break
                            # `stock.quant` da manfiy qoldiq bo'lishi mumkin
                            miqdor = min(abs(asl.quantity), qolgan)
                            qolgan -= miqdor
                            self.env['stock.move.line'].sudo().create({
                                'move_id': qaytish.id,
                                'product_id': product.id,
                                'quantity': miqdor,
                                'lot_id': asl.lot_id.id,
                                'location_id': ishlab.id,
                                'location_dest_id': wh.lot_stock_id.id,
                                'company_id': j.company_id.id,
                            })
                    qaytish.picked = True
                    qaytish._action_done()

                    # Analitik qatorni O'CHIRAMIZ, teskari qator yozmaymiz.
                    # Sabab: xarajat yig'indisi faqat manfiy qatorlarni
                    # sanaydi, shuning uchun musbat teskari qator xarajatni
                    # kamaytirmaydi — aksincha daromadga qo'shilib ketadi.
                    # Storno esa bu yerda «bekor qilish» degani: hujjat
                    # qoralamaga qaytadi, ya'ni go'yo bo'lmagan.
                    j.analytic_line_ids.sudo().unlink()
                    # Hujjat hali `done` — yozish qulfini chetlab o'tamiz
                    j.with_context(agronova_soyish_post=True).write({
                        'tirik_qiymat': 0.0, 'analytic_line_ids': [(5, 0, 0)],
                        'tirik_move_id': False})

            j.with_context(agronova_soyish_post=True).holat = 'draft'
            j.message_post(body=_("Hujjat storno qilindi va qoralamaga qaytdi."))
        return True

    # ------------------------------------------------------------ ombor
    def _ombor(self):
        self.ensure_one()
        return self.env['stock.warehouse'].sudo().search(
            [('company_id', '=', self.company_id.id)], limit=1)

    def _ishlab_chiqarish_joyi(self):
        self.ensure_one()
        loc = self.env['stock.location'].sudo().search([
            ('usage', '=', 'production'),
            ('company_id', 'in', [self.company_id.id, False]),
        ], limit=1)
        if not loc:
            loc = self.env['stock.location'].sudo().create({
                'name': _("So'yish sexi"), 'usage': 'production',
                'company_id': self.company_id.id})
        return loc

    def _tirikni_chiqarish(self):
        """Tirik tovuqni ombordan hisobdan chiqaradi va xarajatga yozadi."""
        self.ensure_one()
        product = self.partiya_id.product_id
        if not product:
            return
        wh = self._ombor()
        if not wh:
            raise UserError(_("So'yish korxonasida ombor topilmadi."))
        dona = self.soyilgan_son + self.nobud_son
        move = self.env['stock.move'].sudo().create({
            'product_id': product.id,
            'product_uom_qty': dona,
            'product_uom': product.uom_id.id,
            'location_id': wh.lot_stock_id.id,
            'location_dest_id': self._ishlab_chiqarish_joyi().id,
            'company_id': self.company_id.id,
            'origin': self.display_name,
        })
        move._action_confirm()
        move._action_assign()
        move.quantity = dona
        # Tirik tovuq lot bilan kuzatilsa, ombordagi mavjud lotdan olinadi —
        # `_action_assign` uni o'zi tanlaydi. Tanlanmagan bo'lsa (masalan
        # qoldiq yetarli emas) Odoo o'zi xato beradi.
        move.picked = True
        move._action_done()

        qiymat = abs(move.value or 0.0)
        if not qiymat:
            # `standard_price` korxonaga bog'liq maydon. Hujjatni boshqa
            # bo'lim xodimi ochgan bo'lsa (masalan Ona tovuqdan poda
            # avtomat kelganda) joriy korxona boshqa bo'ladi va narx nol
            # o'qiladi — shuning uchun aniq ko'rsatamiz.
            qiymat = abs(product.with_company(self.company_id).standard_price
                         * dona)
        self.tirik_qiymat = qiymat
        self.tirik_move_id = move.id
        if qiymat:
            line = self.partiya_id._agronova_post_analytic(
                name=_("Tirik tovuq: %(dona)s dona", dona=dona),
                amount=-qiymat, date=self.sana, unit_amount=dona,
                product=product,
                extra={'company_id': self.company_id.id})
            self.analytic_line_ids = [(4, line.id)]

    def _natijani_kirim_qilish(self):
        """Sortirovka natijasini omborga kirim qiladi."""
        self.ensure_one()
        wh = self._ombor()
        manba_joy = self._ishlab_chiqarish_joyi()

        # Partiyaning shu paytgacha yig'ilgan ishlab chiqarish xarajati
        xarajat = self.partiya_id._agronova_analytic_amount(
            sign='cost', faqat_tannarx=True)
        jami_kg = self.tushka_vazn_kg

        ulushlar = sum(self.natija_ids.mapped('ulush_foiz'))
        for line in self.natija_ids.filtered(lambda l: not l.move_id):
            if ulushlar > 0:
                # Qiymat ulushi ko'rsatilgan — o'sha nisbatda
                qiymat = xarajat * (line.ulush_foiz / ulushlar)
            else:
                # Ko'rsatilmagan — vazn bo'yicha
                qiymat = (xarajat * line.miqdor_kg / jami_kg) if jami_kg else 0.0
            narx = (qiymat / line.miqdor_kg) if line.miqdor_kg else 0.0

            # Kuzatuv uchun lot: qaysi partiyadan, qaysi kuni chiqqani
            # shundan ko'rinadi (TZ 9 va 12-band).
            lot = False
            if line.product_id.tracking != 'none':
                lot_nomi = "%s/%s" % (self.partiya_id.name, self.sana)
                # Mavjud bo'lsa QAYTA ISHLATAMIZ. Sabab: hujjat storno
                # qilinib qayta tasdiqlansa yoki bir kunda ikki marta
                # yozilsa, bir xil nomli lot yaratib bo'lmaydi — Odoo
                # «mahsulot + lot kombinatsiyasi noyob bo'lsin» deydi.
                # Ayni partiya, ayni kun, ayni mahsulot — bu bitta lot.
                lot = self.env['stock.lot'].sudo().search([
                    ('name', '=', lot_nomi),
                    ('product_id', '=', line.product_id.id),
                    ('company_id', 'in', [self.company_id.id, False]),
                ], limit=1)
                if not lot:
                    lot = self.env['stock.lot'].sudo().create({
                        'name': lot_nomi,
                        'product_id': line.product_id.id,
                        'company_id': self.company_id.id,
                    })

            move = self.env['stock.move'].sudo().create({
                'product_id': line.product_id.id,
                'product_uom_qty': line.miqdor_kg,
                'product_uom': line.product_id.uom_id.id,
                'location_id': manba_joy.id,
                'location_dest_id': wh.lot_stock_id.id,
                'company_id': self.company_id.id,
                'price_unit': narx,
                'origin': self.display_name,
            })
            move._action_confirm()
            move._action_assign()
            move.quantity = line.miqdor_kg
            if lot:
                move.move_line_ids.write({'lot_id': lot.id})
            move.picked = True
            move._action_done()
            line.write({'move_id': move.id, 'qiymat': qiymat,
                        'lot_id': lot and lot.id})
