# -*- coding: utf-8 -*-
"""Xarajat hujjatining umumiy skeleti.

Boquv TZ sida tasvirlangan va Ona Tovuqda ham o'zgarishsiz qo'llaniladigan
mexanizm shu yerda bir marta yozilgan:

* to'lov turi **naqd** (depozitdan chiqim) yoki **qarz** (kontragent majburiy);
* naqd xarajatda **foto ilova majburiy** — fotosiz saqlanmaydi;
* maqsad majburiy: bitta obyekt / bir necha obyekt / butun bo'lim;
* taqsimlash bazasi: bosh soni / m² / teng / to'g'ridan-to'g'ri;
* tahrirlash muddati pog'onasi 12/24/36 soat, keyin faqat bosh buxgalter;
* tasdiqlangan hujjat tahrirlanmaydi — faqat storno.

Bo'lim moduli shu mixin'dan meros olib, `_agronova_taqsimot_targets()` metodini
o'ziga moslashtiradi (Ona Tovuqda — sexlar va ulardagi aktiv partiyalar).
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .agronova_xarajat_kategoriya import TAQSIMLASH_BAZASI

# Rolga qarab tahrirlash muddati (soat). None — cheklovsiz.
TAHRIR_MUDDATI = [
    ('agronova_base.group_agronova_bosh_buxgalter', None),
    ('agronova_base.group_agronova_hisobchi', 36),
    ('agronova_base.group_agronova_bolim_boshliq', 24),
]
TAHRIR_MUDDATI_DEFAULT = 12


class AgroNovaXarajatMixin(models.AbstractModel):
    _name = 'agronova.xarajat.mixin'
    _description = "AgroNova — xarajat hujjati mixin"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sana desc, id desc'

    name = fields.Char(
        "Hujjat raqami", default=lambda self: _("Yangi"),
        copy=False, readonly=True, index=True)
    sana = fields.Date(
        "Operatsiya sanasi", required=True, tracking=True,
        default=fields.Date.context_today,
        help="Xarajat aslida qilingan sana. Tizimga kiritilgan sana alohida "
             "(create_date) saqlanadi — TZ talabi.")
    kategoriya_id = fields.Many2one(
        'agronova.xarajat.kategoriya', string="Kategoriya",
        required=True, tracking=True, ondelete='restrict')
    nom = fields.Char("Xarajat nomi", required=True, tracking=True)
    miqdor = fields.Float("Miqdor", default=1.0)
    narx = fields.Monetary("Narx", tracking=True)
    summa = fields.Monetary(
        "Summa", compute='_compute_summa', store=True, tracking=True,
        help="Miqdor × narx. Qo'lda kiritilmaydi.")
    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)

    # --- to'lov
    tolov_turi = fields.Selection(
        [('naqd', "Naqd"), ('qarz', "Qarz")],
        string="To'lov turi", default='naqd', required=True, tracking=True)
    kontragent_id = fields.Many2one(
        'res.partner', string="Kontragent", tracking=True,
        help="Qarzga olingan xarajatda majburiy.")
    foto = fields.Binary("Chek / foto", attachment=True)
    foto_filename = fields.Char("Fayl nomi")

    # --- maqsad va taqsimlash
    maqsad_turi = fields.Selection(
        [('bitta', "Bitta obyekt"),
         ('bir_necha', "Bir necha obyekt"),
         ('bolim', "Butun bo'lim")],
        string="Xarajat maqsadi", default='bolim', required=True, tracking=True,
        help="Xarajat qaysi obyektga tegishli. Maqsad ko'rsatilmagan xarajat "
             "saqlanmaydi — TZ talabi.")
    taqsimlash_bazasi = fields.Selection(
        TAQSIMLASH_BAZASI, string="Taqsimlash bazasi",
        compute='_compute_taqsimlash_bazasi', store=True, readonly=False,
        required=True,
        help="Kategoriyadan standart qiymat olinadi, hujjatda o'zgartirilishi "
             "mumkin.")

    # --- holat
    holat = fields.Selection(
        [('draft', "Qoralama"),
         ('tasdiqlangan', "Tasdiqlangan"),
         ('storno', "Storno qilingan")],
        string="Holati", default='draft', required=True, tracking=True, copy=False)
    storno_id = fields.Many2one(
        'account.analytic.line', string="Storno qatori", readonly=True, copy=False)
    analytic_line_ids = fields.Many2many(
        'account.analytic.line', string="Analitik qatorlar",
        readonly=True, copy=False,
        help="Tasdiqlashda yaratilgan xarajat qatorlari. Tannarx shulardan "
             "hisoblanadi.")
    tahrir_mumkinmi = fields.Boolean(
        "Tahrirlash mumkin", compute='_compute_tahrir_mumkinmi')
    izoh = fields.Text("Izoh")

    # ------------------------------------------------------------- compute
    @api.depends('miqdor', 'narx')
    def _compute_summa(self):
        for rec in self:
            rec.summa = rec.miqdor * rec.narx

    @api.depends('kategoriya_id')
    def _compute_taqsimlash_bazasi(self):
        for rec in self:
            if rec.kategoriya_id:
                rec.taqsimlash_bazasi = rec.kategoriya_id.taqsimlash_bazasi
            elif not rec.taqsimlash_bazasi:
                rec.taqsimlash_bazasi = 'm2'

    def _agronova_tahrir_muddati(self):
        """Joriy foydalanuvchi uchun tahrirlash muddati (soat) yoki None."""
        for xmlid, hours in TAHRIR_MUDDATI:
            if self.env.user.has_group(xmlid):
                return hours
        return TAHRIR_MUDDATI_DEFAULT

    @api.depends('holat', 'create_date')
    def _compute_tahrir_mumkinmi(self):
        hours = self._agronova_tahrir_muddati()
        now = fields.Datetime.now()
        for rec in self:
            if rec.holat != 'draft':
                rec.tahrir_mumkinmi = False
            elif hours is None or not rec.create_date:
                rec.tahrir_mumkinmi = True
            else:
                elapsed = (now - rec.create_date).total_seconds() / 3600.0
                rec.tahrir_mumkinmi = elapsed <= hours

    # ----------------------------------------------------------- validatsiya
    @api.constrains('tolov_turi', 'foto', 'kontragent_id')
    def _check_tolov(self):
        for rec in self:
            if rec.tolov_turi == 'naqd' and not rec.foto:
                raise ValidationError(_(
                    "«%s» naqd xarajati fotosiz saqlanmaydi. Chek yoki "
                    "xarajat fotosini ilova qiling.", rec.nom or ''))
            if rec.tolov_turi == 'qarz' and not rec.kontragent_id:
                raise ValidationError(_(
                    "«%s» qarzga olingan xarajatda kontragent majburiy.",
                    rec.nom or ''))
            rec._check_naqd_manba()

    def _check_naqd_manba(self):
        """Naqd to'lov manbasi (depozit) tekshiruvi.

        `agronova_savdo_moliya` o'rnatilganda shu metod qayta yoziladi va
        depozit majburiy bo'ladi. Bazaviy modulda depozit modeli yo'q,
        shuning uchun bu yerda bo'sh.
        """
        return True

    @api.constrains('summa')
    def _check_summa(self):
        for rec in self:
            if rec.summa <= 0:
                raise ValidationError(_("Xarajat summasi noldan katta bo'lishi kerak."))

    def _agronova_qulfsiz_maydonlar(self):
        """Tahrir qulfiga tushmaydigan texnik maydonlar.

        Tasdiqlash paytida hujjat o'ziga bir necha texnik maydon yozadi:
        analitik qatorlar, storno izi, to'lov izi. `holat` allaqachon
        «tasdiqlangan» bo'lgani uchun ular qulfga tushib qolsa, hujjat
        o'zini tasdiqlay olmay qoladi — foydalanuvchi «tasdiqlangan,
        tahrirlash taqiqlanadi» degan chalg'ituvchi xatoni ko'radi.

        Modul yangi texnik maydon qo'shsa (`agronova_savdo_moliya` —
        depozit izi), shu to'plamni kengaytiradi.
        """
        return {'holat', 'storno_id', 'analytic_line_ids',
                'message_follower_ids', 'message_ids', 'activity_ids'}

    def write(self, vals):
        # Tasdiqlangan hujjat tahrirlanmaydi — faqat storno.
        holat_ozgarish = set(vals) <= self._agronova_qulfsiz_maydonlar()
        if not holat_ozgarish:
            for rec in self:
                if rec.holat != 'draft':
                    raise UserError(_(
                        "«%s» hujjati tasdiqlangan — tahrirlash taqiqlanadi. "
                        "Xato bo'lsa storno qiling va yangi hujjat kiriting.",
                        rec.display_name))
                if not rec.tahrir_mumkinmi:
                    hours = rec._agronova_tahrir_muddati()
                    raise UserError(_(
                        "«%s» hujjatini tahrirlash muddati (%s soat) tugagan. "
                        "Endi faqat bosh buxgalter o'zgartira oladi.",
                        rec.display_name, hours))
        return super().write(vals)

    # ------------------------------------------------------------ taqsimlash
    def _agronova_taqsimot_targets(self):
        """Xarajat taqsimlanadigan obyektlar.

        Meros oluvchi model qaytaradi: `[{'record': rec, 'maydoni': m2,
        'bosh_soni': n, 'analytic': account}, ...]`.
        """
        self.ensure_one()
        raise NotImplementedError(
            "Bo'lim moduli _agronova_taqsimot_targets() metodini yozishi kerak.")

    def _agronova_taqsimot(self):
        """Summani tanlangan baza bo'yicha bo'ladi.

        Qaytaradi: `[(target_dict, ulush_summasi), ...]`.
        """
        self.ensure_one()
        targets = self._agronova_taqsimot_targets()
        if not targets:
            raise UserError(_(
                "«%s» xarajati hech qaysi obyektga biriktirilmagan — "
                "saqlanmaydi. Maqsadni ko'rsating.", self.display_name))

        baza = self.taqsimlash_bazasi
        if baza == 'togridan' or len(targets) == 1:
            weights = [1.0] * len(targets)
        elif baza == 'm2':
            weights = [t.get('maydoni', 0.0) for t in targets]
        elif baza == 'bosh_soni':
            weights = [t.get('bosh_soni', 0.0) for t in targets]
        else:  # teng
            weights = [1.0] * len(targets)

        jami = sum(weights)
        if not jami:
            # Baza bo'yicha ma'lumot yo'q (masalan m² kiritilmagan) — teng bo'lamiz,
            # lekin foydalanuvchini ogohlantiramiz.
            raise UserError(_(
                "«%s» xarajatini «%s» bazasi bo'yicha taqsimlab bo'lmaydi: "
                "obyektlarda bu ko'rsatkich nolga teng. Sex maydoni (m²) yoki "
                "bosh sonini to'ldiring, yoki bazani «Teng bo'lib» ga o'zgartiring.",
                self.display_name, dict(TAQSIMLASH_BAZASI).get(baza, baza)))

        natija = []
        taqsimlangan = 0.0
        for idx, (target, weight) in enumerate(zip(targets, weights)):
            if idx == len(targets) - 1:
                ulush = self.summa - taqsimlangan   # yaxlitlash farqi oxirgisiga
            else:
                ulush = self.currency_id.round(self.summa * weight / jami)
                taqsimlangan += ulush
            natija.append((target, ulush))
        return natija

    # ---------------------------------------------------------------- holat
    def action_tasdiqlash(self):
        for rec in self:
            if rec.holat != 'draft':
                raise UserError(_("Faqat qoralama hujjat tasdiqlanadi."))
            lines = self.env['account.analytic.line'].sudo().browse()
            for target, ulush in rec._agronova_taqsimot():
                if not ulush:
                    continue
                obyekt = target['record']
                lines |= obyekt._agronova_post_analytic(
                    name=_("%(kat)s: %(nom)s", kat=rec.kategoriya_id.name, nom=rec.nom),
                    amount=-abs(ulush),          # xarajat — manfiy
                    date=rec.sana,
                    extra={'company_id': rec.company_id.id,
                           'partner_id': rec.kontragent_id.id or False,
                           'agronova_kategoriya_id': rec.kategoriya_id.id or False,
                           'general_account_id': rec.kategoriya_id.account_id.id or False},
                )
            rec.analytic_line_ids = [(6, 0, lines.ids)]
            rec.holat = 'tasdiqlangan'
            rec._agronova_tolov_amalga_oshirish()
        return True

    def _agronova_tolov_amalga_oshirish(self):
        """Naqd to'lovda depozitdan chiqim. `agronova_savdo_moliya` qayta yozadi."""
        return True

    def action_storno(self):
        """Yozuvni o'chirmaydi — teskari analitik qator yozadi."""
        for rec in self:
            if rec.holat != 'tasdiqlangan':
                raise UserError(_("Faqat tasdiqlangan hujjat storno qilinadi."))
            for line in rec.analytic_line_ids:
                line.copy({
                    'name': _("STORNO: %s", line.name),
                    'amount': -line.amount,
                    'date': fields.Date.context_today(rec),
                })
            rec._agronova_tolov_storno()
            rec.holat = 'storno'
            rec.message_post(body=_("Hujjat storno qilindi."))
        return True

    def _agronova_tolov_storno(self):
        return True

    def unlink(self):
        for rec in self:
            if rec.holat != 'draft':
                raise UserError(_(
                    "Tasdiqlangan xarajat hujjati o'chirilmaydi — storno qiling."))
        return super().unlink()
