# -*- coding: utf-8 -*-
"""Ichki sotuv — B10.

Ikki holatda ishlatiladi:

* **tuxum → Inkubatsiya** — yig'ilgan inkubatsion tuxum boshqa bo'limga
  beriladi;
* **poda → So'yish** — tuxum berish normadan tushgan (eskirgan) poda tirik
  vazn bilan so'yishga o'tkaziladi.

TZ 12-bo'lim: bu **oddiy ichki ko'chirish emas** — Ona Tovuqning daromadi
shakllanadi, chunki bo'limning haqiqiy natijasi shundan ko'rinadi. Lekin
QQS hisob-fakturasi va tashqi mijozga sotuvdagi hujjat aylanishi bo'lmaydi
— faqat boshqaruv hisobi qatorlari.

## Mahsulot jismonan qanday ko'chadi

Boshqaruv hisobi qatoridan tashqari **ombor harakati** ham yaratiladi, aks
holda tuxum Ona tovuq omborida qolib ketadi va qabul qiluvchi bo'lim uni
ishlata olmaydi.

Ikki tur ikki xil ishlaydi, chunki ular ombor hisobida bir xil emas:

* **tuxum** — yig'ilgandan keyin tuxum omboriga kirim qilingan, ya'ni
  qoldiqda turibdi. Shuning uchun ikkita harakat: tuxum ombori →
  **Inter-company transit** (Ona tovuq korxonasida chiqim) va transit →
  Inkubatoriya ombori (qabul qiluvchida kirim). Transit lokatsiyasining
  korxonasi yo'q, shuning uchun korxonalararo ko'chirishga ruxsat beriladi;
* **poda** — tirik tovuq ombor qoldig'ida yuritilmaydi, u partiya
  modelida (`boshlangich_son` minus nobud/brak) sanaladi. Shuning uchun
  chiqim harakati yo'q: partiyaning `chiqim_son` i oshadi, So'yish
  tomonida esa transitdan kirim qilinadi — u yerda tirik tovuq
  `agronova.soyish.jarayon` da hisobdan chiqishi uchun qoldiqda bo'lishi shart.

Podada bundan tashqari So'yish bo'limida **qabul hujjati qoralamasi**
ochiladi. Vazn oldindan to'ldiriladi, lekin haqiqiy tortish so'yish
sexining tarozisida bo'ladi — operator raqamni to'g'rilab, «Qabul»
tugmasini bosadi va so'yish partiyasi ochiladi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

TUR = [
    ('tuxum_inkubatsiya', "Tuxum → Inkubatsiya"),
    ('poda_soyish', "Eskirgan poda → So'yish"),
]


class AgroNovaOnaTovuqIchkiSotuv(models.Model):
    _name = 'agronova.ona_tovuq.ichki_sotuv'
    _description = "Ona tovuq — ichki sotuv"
    _inherit = ['mail.thread', 'agronova.tannarx.qulf.mixin',
                'agronova.otkazma.mixin']
    _agronova_tannarx_fields = ('tannarx_summa',)
    _order = 'date desc, id desc'

    @api.model_create_multi
    def create(self, vals_list):
        # Tuxum -> Inkubatsiya yo'nalishi endi standart Sotuv (sale.order)
        # orqali ishlaydi (`agronova_ona_tovuq_ichki_otkazma.py`) — bu model
        # o'sha turdagi YANGI hujjat yaratmaydi. Eski `done` yozuvlar
        # (elminatsiya hujjatlari ularga bog'langan) o'chirilmaydi,
        # tarixiy hisobot va audit izi sifatida qoladi.
        for vals in vals_list:
            if vals.get('tur') == 'tuxum_inkubatsiya':
                raise UserError(_(
                    "Tuxum -> Inkubatoriya o'tkazmasi endi oddiy Sotuv "
                    "(sale.order) orqali qilinadi — mijoz qilib "
                    "Inkubatoriya korxonasini tanlang."))
        return super().create(vals_list)

    name = fields.Char("Hujjat", default=lambda s: _("Yangi"), copy=False,
                       readonly=True)
    tur = fields.Selection(TUR, string="Turi", required=True, tracking=True,
                           default='tuxum_inkubatsiya')
    date = fields.Date("Sana", required=True, default=fields.Date.context_today,
                       tracking=True)
    partiya_id = fields.Many2one(
        'agronova.ona_tovuq.partiya.tuxum', string="Ona tovuq partiyasi",
        required=True, ondelete='restrict', index=True)
    sex_id = fields.Many2one(related='partiya_id.sex_id', string="Sex",
                             store=True, readonly=True)
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

    # --- miqdor
    dona = fields.Integer(
        "Miqdor (dona / bosh)", required=True,
        help="Tuxumda — dona, podada — bosh soni.")
    tirik_vazn = fields.Float(
        "Jami tirik vazn (kg)", digits='Product Unit',
        help="Faqat poda o'tkazishda to'ldiriladi.")

    product_id = fields.Many2one(
        'product.product', string="Mahsulot",
        compute='_compute_product_id', store=True, readonly=False,
        domain="[('is_storable', '=', True)]",
        help="Ombor harakati shu mahsulot bo'yicha yaratiladi. Turga qarab "
             "sozlamalardan avtomat qo'yiladi, kerak bo'lsa o'zgartiriladi.")
    qabul_company_id = fields.Many2one(
        'res.company', string="Qabul qiluvchi bo'lim",
        compute='_compute_product_id', store=True, readonly=False,
        help="Mahsulot shu korxonaning omboriga kirim qilinadi.")

    # --- narx
    narx_id = fields.Many2one(
        'agronova.ona_tovuq.narx', string="Tasdiqlangan ichki narx",
        help="Bo'sh bo'lsa amaldagi narx avtomat olinadi.")
    birlik_narx = fields.Monetary("Birlik narxi", tracking=True)
    summa = fields.Monetary("Jami summa", compute='_compute_summa', store=True)
    tannarx_summa = fields.Monetary(
        "Tannarx summasi", readonly=True, copy=False,
        help="Partiyaning yugurib boruvchi tannarxidan. Qo'lda kiritilmaydi.")
    ichki_foyda = fields.Monetary(
        "Ichki marja", compute='_compute_summa', store=True,
        help="Summa − tannarx. Elminatsiyada shu qiymat teskari yoziladi.")

    holat = fields.Selection(
        [('draft', "Qoralama"), ('done', "O'tkazilgan")],
        string="Holati", default='draft', required=True, tracking=True, copy=False)
    move_id = fields.Many2one(
        'stock.move', string="Chiqim harakati", readonly=True, copy=False,
        help="Ona tovuq omboridan transitga. Podada bo'lmaydi — tirik tovuq "
             "ombor qoldig'ida yuritilmaydi.")
    move_kirim_id = fields.Many2one(
        'stock.move', string="Kirim harakati", readonly=True, copy=False,
        help="Transitdan qabul qiluvchi bo'lim omboriga.")
    lot_id = fields.Many2one(
        'stock.lot', string="Lot", readonly=True, copy=False,
        help="Qabul qiluvchi bo'lim tomonidagi lot — qaysi partiyadan "
             "kelgani shundan bilinadi.")
    soyish_qabul_id = fields.Many2one(
        'agronova.soyish.qabul', string="So'yishdagi qabul hujjati",
        readonly=True, copy=False)

    _dona_musbat = models.Constraint(
        'CHECK (dona > 0)', "Miqdor noldan katta bo'lishi kerak.")

    # --------------------------------------------------------------- compute
    @api.depends('dona', 'birlik_narx', 'tannarx_summa')
    def _compute_summa(self):
        for s in self:
            s.summa = s.dona * s.birlik_narx
            s.ichki_foyda = s.summa - s.tannarx_summa

    # Turga qarab mahsulot va qabul qiluvchi bo'lim. Compute xato
    # ko'tarmaydi — topilmasa bo'sh qoladi, `action_otkazish` tushunarli
    # xabar beradi.
    @api.depends('tur')
    def _compute_product_id(self):
        for s in self:
            s.product_id = s._sozlama_yozuvi('product.product') or s.product_id
            s.qabul_company_id = (s._sozlama_yozuvi('res.company')
                                  or s.qabul_company_id)

    _SOZLAMA = {
        'tuxum_inkubatsiya': {
            'product.product': ('agronova_ona_tovuq.product_inkubatsion',
                                "Inkubatsion tuxum"),
            'res.company': ('agronova_ona_tovuq.company_inkubatsiya',
                            "Inkubatoriya"),
        },
        'poda_soyish': {
            'product.product': ('agronova_ona_tovuq.product_poda', "Ona tovuq"),
            'res.company': ('agronova_ona_tovuq.company_soyish', "So'yish"),
        },
    }

    def _sozlama_yozuvi(self, model):
        """Sozlamadagi yozuv, bo'lmasa nom bo'yicha topilgani."""
        self.ensure_one()
        if not self.tur:
            return None
        param, nom = self._SOZLAMA[self.tur][model]
        pid = self.env['ir.config_parameter'].sudo().get_param(param)
        if pid:
            rec = self.env[model].sudo().browse(int(pid))
            if rec.exists():
                return rec
        return self.env[model].sudo().search([('name', '=ilike', nom)],
                                             limit=1) or None

    @api.onchange('tur', 'date', 'partiya_id')
    def _onchange_narx(self):
        """Amaldagi tasdiqlangan ichki narxni tortib qo'yadi."""
        for s in self:
            narx = self.env['agronova.ona_tovuq.narx'].amaldagi(s.tur, s.date)
            if narx:
                s.narx_id = narx
                s.birlik_narx = narx.narx

    # ------------------------------------------------------------- o'tkazish
    def action_otkazish(self):
        for s in self:
            if s.holat == 'done':
                continue
            if not s.birlik_narx:
                raise UserError(_(
                    "Ichki narx ko'rsatilmagan — bo'lim daromadi hisoblanmaydi. "
                    "Avval narxni tasdiqlang."))
            s.partiya_id._tekshir_ochiq(_("ichki sotuv"))
            s._tekshir_miqdor()
            s._tannarxni_hisoblash()
            s._analitik_yozish()
            if not s.name or s.name == _("Yangi"):
                s.name = self.env['ir.sequence'].next_by_code(
                    'agronova.ona_tovuq.ichki_sotuv') or _("ICHKI/%s", s.id)
            s._ombor_harakati()
            if s.tur == 'tuxum_inkubatsiya':
                s._ink_qabulini_ochish()
            if s.tur == 'poda_soyish':
                s._soyish_qabulini_ochish()
                # Poda ombor qoldig'ida emas, partiya hisobida yuritiladi —
                # bosh soni shu yerda kamayadi.
                s.partiya_id.sudo().write({
                    'chiqim_son': s.partiya_id.chiqim_son + s.dona,
                    'soyishga_otkazish_id': s.id,
                })
            s.holat = 'done'
        return True

    def _tekshir_miqdor(self):
        """Podada vazn majburiy va bosh sonidan oshib ketmasin."""
        self.ensure_one()
        if self.tur != 'poda_soyish':
            return
        if not self.tirik_vazn:
            raise UserError(_(
                "Podani o'tkazishda jami tirik vazn ko'rsatilishi shart — "
                "so'yishdagi chiqim foizi shu vazndan hisoblanadi."))
        qolgan = self.partiya_id.joriy_son
        if self.dona > qolgan:
            raise UserError(_(
                "«%(nom)s» partiyasida %(qolgan)s bosh qolgan, siz "
                "%(soralgan)s bosh o'tkazmoqchisiz.",
                nom=self.partiya_id.name, qolgan=qolgan, soralgan=self.dona))

    # ------------------------------------------------------- ombor harakati
    def _manba_location(self):
        """Chiqim qayerdan. Poda ombor qoldig'ida emas — bo'sh qaytadi."""
        self.ensure_one()
        if self.tur != 'tuxum_inkubatsiya':
            return self.env['stock.location'].browse()
        return self.partiya_id.sex_id._tuxum_ombori()

    def _ombor_harakati(self):
        self.ensure_one()
        if not self.product_id:
            raise UserError(_(
                "Mahsulot ko'rsatilmagan — ombor harakati yaratilmaydi. "
                "Sozlamalarda «%s» uchun mahsulotni belgilang.",
                dict(TUR)[self.tur]))
        if not self.qabul_company_id:
            raise UserError(_(
                "Qabul qiluvchi bo'lim ko'rsatilmagan — mahsulot qayerga "
                "kirim qilinishi noma'lum."))
        transit = self._transit_location()
        manba = self._manba_location()
        if manba:
            out = self._chiqim(manba, transit)
            self.move_id = out
            # Chiqimda qaysi lotlardan olingan bo'lsa, kirimda ham o'shalar —
            # kuzatuv zanjiri uzilmasin.
            taqsimot = [(ml.lot_id.name, ml.quantity)
                        for ml in out.move_line_ids if ml.quantity]
        else:
            # Poda ombor qoldig'ida yuritilmaydi — lot partiya nomidan.
            taqsimot = [("%s/%s" % (self.partiya_id.name, self.date), self.dona)]
        move_in, lot = self._kirim(transit, self._qabul_location(), taqsimot)
        self.move_kirim_id = move_in
        self.lot_id = lot
        return True

    def _tannarx_1_birlik(self):
        self.ensure_one()
        return self.tannarx_summa / self.dona if self.dona else 0.0

    # ------------------------------------------------ inkubatsiyaga topshirish
    def _ink_qabulini_ochish(self):
        """Inkubatoriya bo'limida tuxum qabuli qoralamasini ochadi.

        Tuxum jismonan allaqachon ko'chgan, lekin uning **kelib chiqishi
        va qiymati** inkubatsiya partiyasiga bog'lanishi kerak — aks holda
        jo'ja tannarxi tuxum qiymatisiz qolib, bepul chiqqandek ko'rinadi.

        Hujjat qoralama qoladi: qaysi partiyaga qo'yilishini inkubatoriya
        operatori o'zi tanlaydi.
        """
        self.ensure_one()
        Qabul = self.env.get('agronova.ink.qabul')
        if Qabul is None:
            # Inkubatoriya moduli o'rnatilmagan bazada ham ishlashi kerak
            return False
        qabul = Qabul.sudo().create({
            'manba': 'ichki',
            'company_id': self.qabul_company_id.id,
            'ot_ichki_sotuv_id': self.id,
            'ot_partiya_id': self.partiya_id.id,
            'ot_company_id': self.company_id.id,
            'product_id': self.product_id.id,
            'dona': self.dona,
            'qiymat': self.summa,
            'date': self.date,
            'izoh': _(
                "Ona tovuq bo'limidan avtomat: %(hujjat)s, %(partiya)s. "
                "Inkubatsiya partiyasini tanlab, «Qabul qilish» ni bosing.",
                hujjat=self.name, partiya=self.partiya_id.name),
        })
        return qabul

    def action_open_ink_qabul(self):
        """Inkubatoriyadagi qabul hujjatini ochadi.

        Bog'lanish maydon bilan emas, qidiruv bilan: Many2one qo'yilsa
        `agronova_ona_tovuq` `agronova_inkubatoriya` ga bog'lanib qolardi, u esa
        o'z navbatida shu modulga tayanadi — aylanma bog'liqlik chiqardi.
        Zanjirning yo'nalishi bitta: quyi bo'lim yuqorisiga bog'lanadi.
        """
        self.ensure_one()
        Qabul = self.env.get('agronova.ink.qabul')
        if Qabul is None:
            raise UserError(_("Inkubatoriya moduli o'rnatilmagan."))
        qabul = Qabul.sudo().search([('ot_ichki_sotuv_id', '=', self.id)],
                                    limit=1)
        if not qabul:
            raise UserError(_(
                "«%s» bo'yicha Inkubatoriyada qabul hujjati topilmadi.",
                self.name))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'agronova.ink.qabul',
            'res_id': qabul.id,
            'view_mode': 'form',
        }

    # -------------------------------------------------- so'yishga topshirish
    def _soyish_qabulini_ochish(self):
        """So'yish bo'limida qabul hujjati qoralamasini ochadi.

        Vazn oldindan to'ldiriladi, lekin haqiqiy tortish so'yish sexining
        tarozisida bo'ladi — shuning uchun hujjat qoralama holatida qoladi.
        """
        self.ensure_one()
        Qabul = self.env.get('agronova.soyish.qabul')
        if Qabul is None:
            # So'yish moduli o'rnatilmagan bazada ham ishlashi kerak
            return False
        qabul = Qabul.sudo().create({
            'manba': 'ichki',
            'product_id': self.product_id.id,
            'company_id': self.qabul_company_id.id,
            'tovuq_soni': self.dona,
            'brutto_kg': self.tirik_vazn,
            'tara_kg': 0.0,
            'izoh': _(
                "Ona tovuq bo'limidan avtomat: %(hujjat)s, %(partiya)s. "
                "Vazn jo'natuvchi tomonning ma'lumoti — tarozida tortib "
                "to'g'rilang.",
                hujjat=self.name, partiya=self.partiya_id.name),
        })
        self.soyish_qabul_id = qabul
        qabul.message_post(body=_(
            "«%(nom)s» ona tovuq partiyasidan %(son)s bosh eskirgan poda "
            "keldi. Tarozida tortib, brutto va tara vaznini to'g'rilang.",
            nom=self.partiya_id.name, son=self.dona))
        return True

    def action_open_soyish_qabul(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'agronova.soyish.qabul',
            'res_id': self.soyish_qabul_id.id,
            'view_mode': 'form',
        }

    def _tannarxni_hisoblash(self):
        self.ensure_one()
        if self.tur == 'tuxum_inkubatsiya':
            summa = self.partiya_id.tannarx_1_dona * self.dona
        else:
            # Podada 1 bosh tannarxi = partiya qoldiq xarajati / joriy bosh soni
            joriy = self.partiya_id.joriy_son or 1
            bir_bosh = self.partiya_id.jami_xarajat / joriy
            summa = bir_bosh * self.dona
        self._tannarx_yozish().tannarx_summa = summa

    def _analitik_yozish(self):
        """Bo'lim daromadi va tannarx chiqimini analitik hisobga yozadi."""
        self.ensure_one()
        partiya = self.partiya_id
        partiya._agronova_post_analytic(
            name=_("Ichki sotuv: %s (%s dona)", dict(TUR)[self.tur], self.dona),
            amount=self.summa, date=self.date)
        if self.tannarx_summa:
            partiya._agronova_post_analytic(
                name=_("Ichki sotuv tannarxi: %s", dict(TUR)[self.tur]),
                amount=-self.tannarx_summa, date=self.date,
                tannarxga=False)

    def write(self, vals):
        for s in self:
            if s.holat == 'done' and set(vals) - {'message_ids',
                                                  'message_follower_ids'}:
                raise UserError(_(
                    "O'tkazilgan hujjat tahrirlanmaydi (%s).", s.display_name))
        return super().write(vals)
