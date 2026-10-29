# -*- coding: utf-8 -*-
"""Bo'lim foyda-zarar hisobotining umumiy skeleti.

Har bo'limning hisoboti bir xil savolga javob beradi: qancha daromad,
qancha xarajat, qancha foyda va rentabellik. Farqi faqat manbalarda —
qaysi analitik hisoblar bo'limga tegishli, ichki daromad qayerdan
keladi, qanday ishlab chiqarish ko'rsatkichi ko'rsatiladi.

Shuning uchun tuzilma shu yerda bir marta yozilgan, bo'lim modullari esa
bir nechta ilgakni to'ldiradi:

* `_pl_company()` — hisobot qaysi korxonani ko'rsatadi. Foydalanuvchi
  qaysi korxonada turganidan qat'i nazar shu qaytadi: hisobot bo'lim
  ilovasi ichida turibdi, demak har doim o'sha bo'limni ko'rsatishi kerak;
* `_pl_analytic_accounts()` — bo'limning analitik hisoblari;
* `_pl_ichki_sotuv()` — boshqa bo'limga sotilgan summa (bo'lmasa 0);
* `_pl_elminatsiya()` — realizatsiya qilinmagan ichki marja (bo'lmasa 0);
* `_pl_korsatkichlar()` — bo'limga xos ishlab chiqarish raqamlari;
* `_pl_qator_model()` va `_pl_view_xmlid()` — konkret model va ko'rinish.

## Ikki narsa tajribadan chiqqan

**Xarajatga ishlab chiqarish xarajati emas, sotilgan mahsulot tannarxi
kiradi.** Ishlab chiqarilgan, lekin sotilmagan mahsulot omborda aktiv
bo'lib turibdi — uning tannarxi hali xarajat emas. Ikkalasini qo'shsak
bir xil pul ikki marta sanaladi.

**Qatorlar haqiqiy yozuv bo'lishi kerak.** Hisoblanadigan x2many `NewId`
yozuvlar yaratadi, ular RPC va sahifa orasida yo'qoladi — hisobotning
«Xarajat tarkibi» bo'limi bo'sh chiqadi. Shuning uchun qatorlar
`create` / `write` da yoziladi.
"""
from dateutil.relativedelta import relativedelta

from odoo.tools import format_date
from odoo import _, api, fields, models


class AgroNovaPlQatorMixin(models.AbstractModel):
    """Xarajat tarkibining bitta satri."""
    _name = 'agronova.pl.qator.mixin'
    _description = "AgroNova — foyda-zarar hisoboti qatori"
    _order = 'summa desc'

    # Abstrakt modelda ham valyuta maydoni bo'lishi shart, aks holda
    # Monetary maydonni sozlab bo'lmaydi. Konkret model uni hisobotga
    # bog'langan `related` bilan qayta e'lon qiladi.
    currency_id = fields.Many2one('res.currency', string="Valyuta")
    nom = fields.Char("Xarajat turi")
    summa = fields.Monetary("Summa")
    ulush = fields.Float("Ulush (%)")


class AgroNovaPlMixin(models.AbstractModel):
    _name = 'agronova.pl.mixin'
    _description = "AgroNova — bo'lim foyda-zarari"

    davr_boshi = fields.Date(
        "Davr boshi", required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1))
    davr_oxiri = fields.Date(
        "Davr oxiri", required=True,
        default=lambda self: (
            fields.Date.context_today(self).replace(day=1)
            + relativedelta(months=1, days=-1)))
    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True,
        default=lambda self: self._pl_company())
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)

    # --- daromad
    ichki_sotuv = fields.Monetary("Ichki sotuv", compute='_compute_pl')
    tashqi_sotuv = fields.Monetary("Tashqi sotuv", compute='_compute_pl')
    boshqa_daromad = fields.Monetary("Boshqa daromad", compute='_compute_pl')
    jami_daromad = fields.Monetary("JAMI DAROMAD", compute='_compute_pl')

    # --- xarajat
    sotilgan_tannarx = fields.Monetary(
        "Sotilgan mahsulot tannarxi", compute='_compute_pl',
        help="Foyda-zararga aynan shu kiradi.")
    jami_xarajat = fields.Monetary("JAMI XARAJAT", compute='_compute_pl')
    ishlab_chiqarish = fields.Monetary(
        "Davrdagi ishlab chiqarish xarajati", compute='_compute_pl',
        help="Ma'lumot uchun: uning sotilmagan qismi ombordagi mahsulot "
             "tannarxida yotadi.")
    ombor_ozgarishi = fields.Monetary(
        "Ombor qiymatiga qo'shildi", compute='_compute_pl',
        help="Ishlab chiqarish xarajati minus sotilgan mahsulot tannarxi.")

    # --- natija
    bolim_foyda = fields.Monetary("Bo'lim foydasi", compute='_compute_pl')
    bolim_rentabellik = fields.Float("Bo'lim rentabelligi (%)",
                                     compute='_compute_pl')
    elminatsiya = fields.Monetary(
        "Elminatsiya (realizatsiya qilinmagan marja)", compute='_compute_pl')
    konsolidatsiya_foyda = fields.Monetary(
        "Konsolidatsiyalangan foyda", compute='_compute_pl')
    konsolidatsiya_rentabellik = fields.Float(
        "Konsolidatsiya rentabelligi (%)", compute='_compute_pl')

    @api.depends('company_id', 'davr_boshi', 'davr_oxiri')
    def _compute_display_name(self):
        """Sarlavhada model nomi emas, hisobot nomi tursin.

        Transient yozuvning `_rec_name` i yo'q — sukut bo'yicha nishonda
        «agronova.qx.pl,4» ko'rinardi.
        """
        for rec in self:
            rec.display_name = "%s (%s — %s)" % (
                rec._pl_nom(),
                format_date(rec.env, rec.davr_boshi) if rec.davr_boshi else "",
                format_date(rec.env, rec.davr_oxiri) if rec.davr_oxiri else "")

    # ------------------------------------------------------------- ilgaklar
    @api.model
    def _pl_company(self):
        """Hisobot qaysi korxonani ko'rsatadi."""
        return self.env.company

    def _pl_analytic_accounts(self):
        """Bo'limga tegishli analitik hisoblar."""
        return self.env['account.analytic.account']

    def _pl_ichki_sotuv(self):
        """Boshqa bo'limga sotilgan summa.

        Sukut bo'yicha korxonalararo sotuv buyurtmalari olinadi. Bo'limda
        o'z ichki sotuv hujjati bo'lsa (Ona tovuqda ichki sotuv, qishloq
        xo'jaligida ichki berish), meros oluvchi model ustiga qo'shadi.
        """
        return self._sotuv_ichki()[0]

    def _pl_elminatsiya(self):
        """Realizatsiya qilinmagan ichki marja."""
        return 0.0

    def _pl_korsatkichlar(self):
        """Bo'limga xos ishlab chiqarish raqamlari (ixtiyoriy)."""
        return

    def _pl_qator_model(self):
        raise NotImplementedError

    def _pl_view_xmlid(self):
        raise NotImplementedError

    def _pl_nom(self):
        return _("Foyda va zarar")

    # --------------------------------------------------------------- manba
    def _analitik_qatorlar(self):
        """Bo'lim hisoblarining davrdagi analitik qatorlari."""
        self.ensure_one()
        hisoblar = self._pl_analytic_accounts()
        if not hisoblar:
            return self.env['account.analytic.line']
        # Har reja o'z ustuniga yozadi, shuning uchun reja bo'yicha ajratamiz
        domain = []
        for plan in hisoblar.mapped('plan_id'):
            shart = [(plan._column_name(), 'in',
                      hisoblar.filtered(lambda h: h.plan_id == plan).ids)]
            domain = shart if not domain else ['|'] + domain + shart
        return self.env['account.analytic.line'].sudo().search(
            domain + [('date', '>=', self.davr_boshi),
                      ('date', '<=', self.davr_oxiri)])

    def _oz_korxona_partnerlari(self):
        """Guruhimizdagi korxonalarning kontragent yozuvlari.

        Bo'limlar o'rtasidagi harakat ba'zan haqiqiy `sale.order` bilan
        rasmiylashtiriladi (korxonalararo sotuv-xarid). Mijoz o'z
        korxonamiz bo'lsa, bu tashqi sotuv emas — ichki sotuv. Aks holda
        hisobotda ichki aylanma tashqi tushum bo'lib ko'rinadi va
        rentabellik haqiqatdan katta chiqadi.
        """
        return self.env['res.company'].sudo().search([]).mapped('partner_id')

    def _sotuv_qatorlari(self):
        """Korxonaning davrdagi tasdiqlangan sotuv qatorlari."""
        self.ensure_one()
        return self.env['sale.order.line'].sudo().search([
            ('company_id', '=', self.company_id.id),
            ('state', '=', 'sale'),
            ('order_id.date_order', '>=', self.davr_boshi),
            ('order_id.date_order', '<=', self.davr_oxiri),
        ])

    def _sotuv_summasi(self, lines):
        tushum = sum(lines.mapped('price_subtotal'))
        tannarx = sum(l.agronova_tannarx * l.product_uom_qty for l in lines
                      if 'agronova_tannarx' in l._fields)
        return tushum, tannarx

    def _tashqi_sotuv(self):
        """Haqiqiy tashqi mijozga sotuv: (tushum, tannarx)."""
        self.ensure_one()
        ichki = self._oz_korxona_partnerlari()
        lines = self._sotuv_qatorlari().filtered(
            lambda l: l.order_id.partner_id not in ichki)
        return self._sotuv_summasi(lines)

    def _sotuv_ichki(self):
        """Boshqa bo'limimizga `sale.order` bilan sotilgani: (tushum, tannarx).

        Tannarx ham qaytariladi: ichki sotuv ham mahsulotni omborimizdan
        chiqaradi, demak uning tannarxi shu davrning xarajati. Bo'lmasa
        daromad tannarxsiz turadi va rentabellik 100% ko'rinadi.
        """
        self.ensure_one()
        ichki = self._oz_korxona_partnerlari()
        lines = self._sotuv_qatorlari().filtered(
            lambda l: l.order_id.partner_id in ichki)
        return self._sotuv_summasi(lines)

    # ------------------------------------------------------------- compute
    @api.depends('davr_boshi', 'davr_oxiri', 'company_id')
    def _compute_pl(self):
        for rec in self:
            qatorlar = rec._analitik_qatorlar()
            rec.ichki_sotuv = rec._pl_ichki_sotuv()
            tashqi_tushum, tashqi_tannarx = rec._tashqi_sotuv()
            rec.tashqi_sotuv = tashqi_tushum
            # Korxonalararo sotuv buyurtmasining tannarxi ham xarajat.
            ichki_tannarx = rec._sotuv_ichki()[1]

            daromad = qatorlar.filtered(lambda l: l.amount > 0)
            rec.boshqa_daromad = max(
                sum(daromad.mapped('amount')) - rec.ichki_sotuv, 0.0)
            rec.jami_daromad = (rec.ichki_sotuv + rec.tashqi_sotuv
                                + rec.boshqa_daromad)

            xarajat = qatorlar.filtered(lambda l: l.amount < 0)
            ishlab_chiqarish = -sum(
                xarajat.filtered('agronova_tannarx_bazasi').mapped('amount'))
            rec.ishlab_chiqarish = ishlab_chiqarish
            rec.sotilgan_tannarx = -sum(
                xarajat.filtered(lambda l: not l.agronova_tannarx_bazasi)
                .mapped('amount')) + tashqi_tannarx + ichki_tannarx
            rec.jami_xarajat = rec.sotilgan_tannarx
            rec.ombor_ozgarishi = ishlab_chiqarish - rec.sotilgan_tannarx

            rec.bolim_foyda = rec.jami_daromad - rec.jami_xarajat
            rec.bolim_rentabellik = (
                rec.bolim_foyda / rec.jami_daromad * 100.0
                if rec.jami_daromad else 0.0)
            rec.elminatsiya = rec._pl_elminatsiya()
            rec.konsolidatsiya_foyda = rec.bolim_foyda - rec.elminatsiya
            rec.konsolidatsiya_rentabellik = (
                rec.konsolidatsiya_foyda / rec.jami_daromad * 100.0
                if rec.jami_daromad else 0.0)
            rec._pl_korsatkichlar()

    # ----------------------------------------------------------- qatorlar
    @api.model
    def _nomdan_guruh(self, name):
        """Kategoriyasi ham, mahsuloti ham yo'q qator uchun guruh nomi.

        Qator nomlari «Kategoriya: nom» yoki «Xarajat turi (hujjat raqami)»
        ko'rinishida. Ikkalasida ham ma'noli qism boshida — oxirini
        kesmasak, har hujjat alohida satr bo'lib chiqadi.
        """
        nom = (name or "").split(':')[0].split('(')[0].strip()
        return nom or _("Boshqa xarajat")

    def _tarkib_vals(self, xarajat_qatorlar):
        """Ishlab chiqarish xarajatining turlarga bo'linishi."""
        self.ensure_one()
        jami = -sum(xarajat_qatorlar.mapped('amount')) or 1.0
        guruh = {}
        xodim_maydoni = 'employee_id' in xarajat_qatorlar._fields
        for line in xarajat_qatorlar:
            if line.agronova_kategoriya_id:
                nom = line.agronova_kategoriya_id.name
            elif line.product_id:
                nom = line.product_id.categ_id.name or _("Material sarfi")
            elif xodim_maydoni and line.employee_id:
                nom = _("Ish haqi")
            else:
                nom = self._nomdan_guruh(line.name)
            guruh[nom] = guruh.get(nom, 0.0) - line.amount
        return [
            {'nom': nom, 'summa': summa, 'ulush': summa / jami * 100.0}
            for nom, summa in sorted(guruh.items(), key=lambda kv: -kv[1])
        ]

    def _qatorlarni_yangilash(self):
        Qator = self.env[self._pl_qator_model()]
        for rec in self:
            rec.qator_ids.unlink()
            # Sotilgan mahsulot tannarxi bu ro'yxatga kirmaydi — u shu
            # xarajatlarning omborga o'tib, keyin sotilgan qismi.
            xarajat = rec._analitik_qatorlar().filtered(
                lambda l: l.amount < 0 and l.agronova_tannarx_bazasi)
            Qator.create([dict(v, pl_id=rec.id)
                          for v in rec._tarkib_vals(xarajat)])

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._qatorlarni_yangilash()
        return records

    def write(self, vals):
        res = super().write(vals)
        if {'davr_boshi', 'davr_oxiri', 'company_id'} & set(vals):
            self._qatorlarni_yangilash()
        return res

    # --------------------------------------------------------------- kirish
    @api.model
    def action_ochish(self):
        """Menyudan kirishda tayyor hisobotni to'liq sahifada ochadi."""
        return self.create({})._act_window()

    def _act_window(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self._pl_nom(),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref(self._pl_view_xmlid()).id,
            'target': 'current',
        }

    def action_yangilash(self):
        """Davr o'zgargandan keyin tarkibni qayta hisoblaydi."""
        self.ensure_one()
        self._qatorlarni_yangilash()
        return self._act_window()
