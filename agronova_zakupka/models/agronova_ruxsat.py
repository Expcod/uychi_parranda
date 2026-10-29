# -*- coding: utf-8 -*-
"""Sotib olishga ruxsat so'rovi (TZ 4.3, 6-bo'lim).

Tasdiqlash zanjiri **ketma-ket**, parallel emas (TZ 2-bo'lim qarori):

    Zakupchik so'radi
       -> Zakupka bo'lim boshlig'i (kerakmi? miqdor to'g'rimi?)
       -> Sifat va narx nazorati boshlig'i (narx maqbulmi? sifat mos?)
       -> Tasdiqlandi -> kirim hujjati yaratishga ruxsat

Ikki qattiq qoida:

* **O'z-o'zini tasdiqlash taqiqlanadi.** So'rovchi o'sha bosqichning
  tasdiqlovchisi bo'lsa (bo'lim boshlig'i o'zi xarid qilsa), bosqich
  o'tkazib yuborilmaydi — so'rov uning yuqori rahbariga ko'tariladi.
* **Kichik summa — bitta tasdiq.** Chegara sozlamada; undan past so'rovda
  ikkinchi bosqich o'tkazib yuboriladi.

Narx qatlami `agronova.narx.normasi` da; bu hujjat undan norma narxni oladi,
og'ishni hisoblaydi va «birinchi xarid» rejimida kamida 3 taklif talab
qiladi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .agronova_zayavka import MUHIMLIK, MUHIMLIK_PARAM

HOLAT = [
    ('draft', "Qoralama"),
    ('bolim_boshligi', "Bo'lim boshlig'i tasdig'i kutilmoqda"),
    ('sifat_nazorat', "Sifat va narx nazorati kutilmoqda"),
    ('tasdiqlandi', "Tasdiqlandi"),
    ('rad_etildi', "Rad etildi"),
    ('bekor', "Bekor qilindi"),
]
BOSQICH_GURUHI = {
    'bolim_boshligi': 'agronova_zakupka.group_zakupka_bolim_boshligi',
    'sifat_nazorat': 'agronova_zakupka.group_zakupka_sifat_nazorat',
}


class AgroNovaRuxsat(models.Model):
    _name = 'agronova.ruxsat'
    _description = "Sotib olishga ruxsat"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'agronova.muddat.mixin']
    _order = 'muhimlik_darajasi, id desc'

    name = fields.Char(
        "Ruxsat raqami", default=lambda self: _("Yangi"),
        copy=False, readonly=True, index=True)
    zayavka_id = fields.Many2one(
        'agronova.zayavka', string="Zayavka", tracking=True, ondelete='restrict',
        help="Ruxsat qaysi zayavka bo'yicha so'ralayapti. Zayavkasiz "
             "(shoshilinch) xaridda bo'sh qolishi mumkin.")
    zayavka_qatori_id = fields.Many2one(
        'agronova.zayavka.qatori', string="Zayavka qatori",
        domain="[('zayavka_id', '=', zayavka_id)]")
    zakupchik_id = fields.Many2one(
        'res.users', string="Zakupchik", required=True, tracking=True,
        default=lambda self: self.env.user)
    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)

    # --- so'ralayotgan tovar
    product_id = fields.Many2one(
        'product.product', string="Tovar", required=True, tracking=True,
        domain="[('purchase_ok', '=', True)]")
    tovar_nomi = fields.Char(
        "Tovar nomi", compute='_compute_tovar_nomi', store=True, readonly=False,
        help="Hujjatda ko'rinadigan nom — mahsulot nomidan farq qilishi mumkin.")
    miqdor = fields.Float("Miqdor", required=True, default=1.0, tracking=True)
    olchov_birligi_id = fields.Many2one(
        'uom.uom', string="O'lchov birligi",
        compute='_compute_olchov_birligi_id', store=True, readonly=False)
    taklif_narx = fields.Monetary(
        "Taklif qilingan narx", required=True, tracking=True,
        help="Zakupchik topgan narx (birlik uchun).")
    summa = fields.Monetary("Summa", compute='_compute_summa', store=True)
    sotib_olish_joyi = fields.Char(
        "Sotib olish joyi", tracking=True,
        help="Bozor yoki do'kon nomi. Kontragent bazada bo'lsa quyidagi "
             "maydonni to'ldiring.")
    kontragent_id = fields.Many2one(
        'res.partner', string="Kontragent", tracking=True,
        domain="[('zakupka_holati', '=', 'faol')]")
    muhimlik_darajasi = fields.Selection(
        MUHIMLIK, string="Muhimlik", default='2_orta', required=True,
        tracking=True)
    asos = fields.Text("Asos", help="Nima uchun kerak, nega shu narxda.")
    ilova = fields.Binary("Narx dalili", attachment=True)
    ilova_filename = fields.Char("Fayl nomi")

    # --- narx nazorati
    norma_narx = fields.Monetary(
        "Norma narx", compute='_compute_narx_nazorati', store=True,
        help="Uch qatlamli mexanizm natijasi (TZ 6-bo'lim).")
    norma_manba = fields.Char(
        "Norma manbai", compute='_compute_narx_nazorati', store=True)
    norma_eski = fields.Boolean(
        "Norma narx eskirgan", compute='_compute_narx_nazorati', store=True)
    birinchi_xarid = fields.Boolean(
        "Birinchi xarid rejimi", compute='_compute_narx_nazorati', store=True,
        help="Norma narx yo'q — kamida 3 ta taklif solishtiriladi.")
    ogish_foizi = fields.Float(
        "Og'ish (%)", compute='_compute_narx_nazorati', store=True,
        help="Taklif narxning norma narxdan og'ishi. Musbat — qimmat.")
    ogish_chegara = fields.Float(
        "Og'ish chegarasi (%)", compute='_compute_narx_nazorati', store=True)
    ogish_chegara_manba = fields.Char(
        "Chegara manbai", compute='_compute_narx_nazorati', store=True)
    ogishli = fields.Boolean(
        "Chegaradan oshgan", compute='_compute_narx_nazorati', store=True)
    taklif_ids = fields.One2many(
        'agronova.taklif', 'ruxsat_id', string="Takliflar", copy=True)
    tanlangan_taklif_id = fields.Many2one(
        'agronova.taklif', string="Tanlangan taklif",
        domain="[('ruxsat_id', '=', id)]", tracking=True)
    tanlov_sababi = fields.Text(
        "Tanlov sababi",
        help="«Birinchi xarid» rejimida tasdiqlovchi nima uchun shu "
             "taklifni tanlaganini yozadi (TZ 6-bo'lim).")

    # --- tasdiqlash zanjiri
    holat = fields.Selection(
        HOLAT, string="Holati", default='draft', required=True,
        tracking=True, copy=False)
    bitta_tasdiq = fields.Boolean(
        "Bitta tasdiq yetarli", compute='_compute_bitta_tasdiq', store=True,
        help="Summa sozlamadagi chegaradan past — ikkinchi bosqich "
             "o'tkazib yuboriladi.")
    tasdiqlovchi_1_id = fields.Many2one(
        'res.users', string="1-tasdiqlovchi", readonly=True, copy=False,
        tracking=True)
    tasdiq_1_vaqti = fields.Datetime("1-tasdiq vaqti", readonly=True, copy=False)
    tasdiqlovchi_2_id = fields.Many2one(
        'res.users', string="2-tasdiqlovchi", readonly=True, copy=False,
        tracking=True)
    tasdiq_2_vaqti = fields.Datetime("2-tasdiq vaqti", readonly=True, copy=False)
    yuborilgan_vaqti = fields.Datetime(
        "Yuborilgan payt", readonly=True, copy=False)
    javob_muddati = fields.Datetime(
        "Joriy bosqich muddati", readonly=True, copy=False)
    javob_vaqti = fields.Datetime(
        "Joriy bosqich javobi", readonly=True, copy=False)
    rad_izohi = fields.Text("Rad sababi", tracking=True)

    kirim_ids = fields.One2many(
        'agronova.kirim', 'tasdiqlangan_ruxsat_id', string="Kirim hujjatlari")
    kirim_soni = fields.Integer("Kirimlar", compute='_compute_kirim_soni')

    # ------------------------------------------------------------- compute
    @api.depends('product_id')
    def _compute_tovar_nomi(self):
        for rec in self:
            if rec.product_id and not rec.tovar_nomi:
                rec.tovar_nomi = rec.product_id.display_name

    @api.depends('product_id')
    def _compute_olchov_birligi_id(self):
        for rec in self:
            rec.olchov_birligi_id = rec.product_id.uom_id

    @api.depends('miqdor', 'taklif_narx')
    def _compute_summa(self):
        for rec in self:
            rec.summa = rec.miqdor * rec.taklif_narx

    @api.depends('summa')
    def _compute_bitta_tasdiq(self):
        chegara = float(self.env['ir.config_parameter'].sudo().get_param(
            'agronova_zakupka.bitta_tasdiq_chegara', 0) or 0)
        for rec in self:
            rec.bitta_tasdiq = bool(chegara) and rec.summa < chegara

    @api.depends('product_id', 'taklif_narx')
    def _compute_narx_nazorati(self):
        Normativ = self.env['agronova.narx.normasi']
        for rec in self:
            if not rec.product_id:
                rec.norma_narx = 0.0
                rec.norma_manba = False
                rec.norma_eski = False
                rec.birinchi_xarid = False
                rec.ogish_foizi = 0.0
                rec.ogish_chegara = 0.0
                rec.ogish_chegara_manba = False
                rec.ogishli = False
                continue
            norma = Normativ._agronova_norma(rec.product_id)
            chegara, chegara_manba = rec.product_id._agronova_ogish_chegara()
            rec.norma_narx = norma['narx']
            rec.norma_manba = norma['manba_nomi']
            rec.norma_eski = norma['eski']
            rec.birinchi_xarid = norma['birinchi_xarid']
            rec.ogish_chegara = chegara
            rec.ogish_chegara_manba = chegara_manba
            if norma['narx'] and rec.taklif_narx:
                rec.ogish_foizi = 100.0 * (
                    rec.taklif_narx - norma['narx']) / norma['narx']
            else:
                rec.ogish_foizi = 0.0
            rec.ogishli = rec.ogish_foizi > chegara

    def _compute_kirim_soni(self):
        for rec in self:
            rec.kirim_soni = len(rec.kirim_ids)

    def _agronova_muddat_maydoni(self):
        return 'javob_muddati', 'javob_vaqti'

    # ---------------------------------------------------------- validatsiya
    @api.constrains('holat', 'birinchi_xarid', 'taklif_ids')
    def _check_birinchi_xarid(self):
        """«Birinchi xarid» rejimida kamida N ta taklif shart (TZ 6)."""
        minimal = int(self.env['ir.config_parameter'].sudo().get_param(
            'agronova_zakupka.birinchi_xarid_taklif', 3) or 3)
        for rec in self:
            if rec.holat == 'draft' or not rec.birinchi_xarid:
                continue
            if len(rec.taklif_ids) < minimal:
                raise ValidationError(_(
                    "«%(hujjat)s»: bu tovarda norma narx yo'q — «birinchi "
                    "xarid» rejimi. Kamida %(soni)s ta taklif kiritilishi "
                    "shart, hozir %(bor)s ta.",
                    hujjat=rec.display_name, soni=minimal,
                    bor=len(rec.taklif_ids)))

    @api.constrains('miqdor', 'taklif_narx')
    def _check_summa(self):
        for rec in self:
            if rec.miqdor <= 0 or rec.taklif_narx <= 0:
                raise ValidationError(_(
                    "Miqdor va narx noldan katta bo'lishi kerak."))

    @api.constrains('kontragent_id')
    def _check_kontragent(self):
        for rec in self:
            if rec.kontragent_id.zakupka_holati == 'bloklangan':
                raise ValidationError(_(
                    "«%s» bloklangan kontragent — yangi xaridda "
                    "ishlatilmaydi.", rec.kontragent_id.display_name))

    # -------------------------------------------------------------- create
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _("Yangi")) == _("Yangi"):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'agronova.ruxsat') or _("Yangi")
        return super().create(vals_list)

    # ------------------------------------------------- tasdiqlovchi tanlash
    def _agronova_bosqich_tasdiqlovchilari(self, bosqich):
        """Bosqich tasdiqlovchilari, o'z-o'zini tasdiqlash chiqarib tashlangan.

        So'rovchining o'zi guruhda bo'lsa u ro'yxatdan chiqariladi. Ro'yxat
        bo'shab qolsa (masalan bo'lim boshlig'i o'zi so'ragan va guruhda
        yolg'iz) — so'rov uning yuqori rahbariga ko'tariladi.
        """
        self.ensure_one()
        guruh = self.env.ref(BOSQICH_GURUHI[bosqich], raise_if_not_found=False)
        userlar = guruh.sudo().all_user_ids if guruh else self.env['res.users']
        userlar = userlar.filtered(lambda u: u.id != self.zakupchik_id.id)
        if userlar:
            return userlar, False
        rahbar = self.zakupchik_id.zakupka_rahbar_id
        if not rahbar:
            raise UserError(_(
                "«%(hujjat)s»: %(bosqich)s bosqichida tasdiqlovchi topilmadi. "
                "So'rovchining o'zi shu bosqich tasdiqlovchisi, o'z-o'zini "
                "tasdiqlash esa taqiqlangan (TZ 2-bo'lim). Zakupchik "
                "kartochkasida «Yuqori rahbar» ni ko'rsating.",
                hujjat=self.display_name, bosqich=dict(HOLAT)[bosqich]))
        return rahbar, True

    def _agronova_tasdiq_soati(self):
        self.ensure_one()
        kalit, standart = MUHIMLIK_PARAM[self.muhimlik_darajasi]
        return float(self.env['ir.config_parameter'].sudo().get_param(
            kalit, standart) or standart)

    def _agronova_bosqichga_otish(self, bosqich):
        """Bosqichni ochadi: muddat qo'yadi va tasdiqlovchilarga xabar beradi."""
        self.ensure_one()
        userlar, kotarildi = self._agronova_bosqich_tasdiqlovchilari(bosqich)
        hozir = fields.Datetime.now()
        self.write({
            'holat': bosqich,
            'javob_muddati': self._agronova_muddat_qoshish(
                hozir, self._agronova_tasdiq_soati()),
            'javob_vaqti': False,
            'eskalatsiya_darajasi': 0,
        })
        for user in userlar:
            self.activity_schedule(
                'mail.mail_activity_data_todo', user_id=user.id,
                summary=_("Tasdiq kutilmoqda: %s", self.name),
                note=_("«%(tovar)s» — %(summa)s. Og'ish: %(ogish).1f%%. "
                       "Muddat: %(muddat)s.",
                       tovar=self.tovar_nomi or self.product_id.display_name,
                       summa=self.summa, ogish=self.ogish_foizi,
                       muddat=self.javob_muddati))
        if kotarildi:
            self.message_post(body=_(
                "So'rovchi o'zi shu bosqich tasdiqlovchisi — so'rov bir "
                "pog'ona yuqoriga, %s ga ko'tarildi.", userlar.display_name))
        return True

    # ------------------------------------------------------------ workflow
    def action_yuborish(self):
        for rec in self:
            if rec.holat != 'draft':
                raise UserError(_("Faqat qoralama ruxsat yuboriladi."))
            rec.yuborilgan_vaqti = fields.Datetime.now()
            rec._agronova_bosqichga_otish('bolim_boshligi')
        return True

    def _agronova_tasdiqlash_huquqi(self, bosqich):
        """Joriy foydalanuvchi shu bosqichni tasdiqlay oladimi."""
        self.ensure_one()
        if self.env.user == self.zakupchik_id:
            raise UserError(_(
                "O'z so'rovingizni o'zingiz tasdiqlay olmaysiz (TZ 2-bo'lim)."))
        userlar, _kotarildi = self._agronova_bosqich_tasdiqlovchilari(bosqich)
        if self.env.user not in userlar and not self.env.user.has_group(
                'base.group_system'):
            raise UserError(_(
                "«%s» bosqichini tasdiqlash huquqingiz yo'q.",
                dict(HOLAT)[bosqich]))
        return True

    def action_tasdiqlash(self):
        """Joriy bosqichni tasdiqlaydi va keyingisiga o'tadi."""
        for rec in self:
            if rec.holat == 'bolim_boshligi':
                rec._agronova_tasdiqlash_huquqi('bolim_boshligi')
                rec._agronova_bosqich_yopish(1)
                if rec.bitta_tasdiq:
                    rec.message_post(body=_(
                        "Summa bitta tasdiq chegarasidan past — sifat va "
                        "narx nazorati bosqichi o'tkazib yuborildi."))
                    rec._agronova_yakuniy_tasdiq()
                else:
                    rec._agronova_bosqichga_otish('sifat_nazorat')
            elif rec.holat == 'sifat_nazorat':
                rec._agronova_tasdiqlash_huquqi('sifat_nazorat')
                rec._agronova_bosqich_yopish(2)
                rec._agronova_yakuniy_tasdiq()
            else:
                raise UserError(_(
                    "«%s» holatidagi hujjat tasdiqlanmaydi.",
                    dict(HOLAT)[rec.holat]))
        return True

    def _agronova_bosqich_yopish(self, raqam):
        self.ensure_one()
        hozir = fields.Datetime.now()
        vals = {'javob_vaqti': hozir}
        vals['tasdiqlovchi_%s_id' % raqam] = self.env.user.id
        vals['tasdiq_%s_vaqti' % raqam] = hozir
        self.write(vals)
        self._agronova_kechikish_yangilash()
        self.activity_unlink(['mail.mail_activity_data_todo'])
        # Tasdiqlash tezligi tasdiqlovchining KPI siga tushadi. `qiymat` —
        # muddatdan qancha kech javob berilgani (ish soatida); muddat ichida
        # javob berilgan bo'lsa nol.
        self.env['agronova.kpi']._agronova_ball_yozish(
            user=self.env.user, mezon='tasdiqlash_tezligi', manba=self,
            qiymat=self.kechikish_soati, norma=0.0)
        return True

    def _agronova_yakuniy_tasdiq(self):
        """Zanjir tugadi — norma narxni yangilaydi va holatni yopadi."""
        self.ensure_one()
        if self.birinchi_xarid:
            if not self.tanlangan_taklif_id:
                raise UserError(_(
                    "«Birinchi xarid» rejimida tasdiqlashdan oldin eng "
                    "maqbul taklifni tanlang."))
            if not self.tanlov_sababi:
                raise UserError(_(
                    "Tanlov sababini yozing — narx tarixi shu izohdan "
                    "boshlanadi (TZ 6-bo'lim)."))
            self.taklif_narx = self.tanlangan_taklif_id.narx
            # Tasdiqlangan narx avtomat norma narxga aylanadi.
            self.env['agronova.narx.normasi']._agronova_yozuvni_yangilash(
                self.product_id, self.tanlangan_taklif_id.narx,
                'birinchi_xarid',
                izoh=_("%(hujjat)s: %(sabab)s",
                       hujjat=self.name, sabab=self.tanlov_sababi))
        self.holat = 'tasdiqlandi'
        self.message_post(body=_(
            "Ruxsat tasdiqlandi. Kirim hujjati yaratish mumkin."))
        if self.norma_eski:
            self.message_post(body=_(
                "DIQQAT: norma narx eskirgan (%s). Narx qayta "
                "tekshirilishi kerak.", self.norma_manba))
        return True

    def action_rad_etish(self):
        for rec in self:
            if rec.holat not in ('bolim_boshligi', 'sifat_nazorat'):
                raise UserError(_("Bu holatda rad etib bo'lmaydi."))
            if not rec.rad_izohi:
                raise UserError(_("Rad etish sababini yozing."))
            raqam = 1 if rec.holat == 'bolim_boshligi' else 2
            rec._agronova_bosqich_yopish(raqam)
            rec.holat = 'rad_etildi'
            rec.message_post(body=_("Rad etildi: %s", rec.rad_izohi))
        return True

    def action_qoralamaga(self):
        for rec in self:
            if rec.holat not in ('rad_etildi', 'bekor'):
                raise UserError(_(
                    "Faqat rad etilgan yoki bekor qilingan ruxsat "
                    "qoralamaga qaytariladi."))
            rec.write({
                'holat': 'draft', 'tasdiqlovchi_1_id': False,
                'tasdiq_1_vaqti': False, 'tasdiqlovchi_2_id': False,
                'tasdiq_2_vaqti': False, 'javob_muddati': False,
                'javob_vaqti': False, 'eskalatsiya_darajasi': 0,
            })
        return True

    def action_bekor(self):
        for rec in self:
            if rec.kirim_ids:
                raise UserError(_(
                    "Kirim hujjati yaratilgan ruxsat bekor qilinmaydi."))
            rec.holat = 'bekor'
        return True

    def action_kirim_yaratish(self):
        self.ensure_one()
        if self.holat != 'tasdiqlandi':
            raise UserError(_(
                "Kirim hujjati faqat tasdiqlangan ruxsat asosida ochiladi "
                "(TZ 4.5)."))
        return {
            'type': 'ir.actions.act_window',
            'name': _("Xarid kirim hujjati"),
            'res_model': 'agronova.kirim',
            'view_mode': 'form',
            'context': {
                'default_tasdiqlangan_ruxsat_id': self.id,
                'default_kontragent_id': self.kontragent_id.id,
                'default_zakupchik_id': self.zakupchik_id.id,
            },
        }

    def action_kirimlarni_korish(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Kirim hujjatlari"),
            'res_model': 'agronova.kirim',
            'view_mode': 'list,form',
            'domain': [('tasdiqlangan_ruxsat_id', '=', self.id)],
        }

    # ---------------------------------------------------------------- cron
    @api.model
    def _cron_tasdiq_nazorati(self):
        """Tasdiq muddati o'tgan ruxsatlarni eskalatsiya qiladi."""
        kutayotgan = self.sudo().search([
            ('holat', 'in', ('bolim_boshligi', 'sifat_nazorat')),
            ('javob_muddati', '!=', False),
            ('javob_muddati', '<', fields.Datetime.now()),
        ])
        kutayotgan._agronova_kechikish_yangilash()
        oraliq = int(self.env['ir.config_parameter'].sudo().get_param(
            'agronova_zakupka.eskalatsiya_oraliq', 30) or 30) / 60.0
        for rec in kutayotgan:
            kerakli = 2 if rec.kechikish_soati >= oraliq else 1
            if kerakli <= rec.eskalatsiya_darajasi:
                continue
            rec.eskalatsiya_darajasi = kerakli
            rec._agronova_tasdiq_eskalatsiya(kerakli)
        return True

    def _agronova_tasdiq_eskalatsiya(self, daraja):
        """1 — o'rinbosarga, 2 — yuqori rahbarga (TZ 6-bo'lim)."""
        self.ensure_one()
        userlar, _kot = self._agronova_bosqich_tasdiqlovchilari(self.holat)
        if daraja == 1:
            maqsad = userlar.mapped('zakupka_orinbosar_id')
            matn = _("Tasdiqlash muddati o'tdi — o'rinbosarga ham ko'rindi.")
        else:
            maqsad = userlar.mapped('zakupka_rahbar_id')
            matn = _("Ikkinchi muddat ham o'tdi — yuqori rahbarga "
                     "eskalatsiya qilindi.")
            # Javobsiz qolgan so'rov tasdiqlovchi KPI siga tushadi.
            for user in userlar:
                self.env['agronova.kpi']._agronova_ball_yozish(
                    user=user, mezon='javobsiz_sorovlar', manba=self,
                    qiymat=1.0, norma=0.0)
        for user in maqsad:
            self.activity_schedule(
                'mail.mail_activity_data_todo', user_id=user.id,
                summary=_("Kechikkan tasdiq: %s", self.name), note=matn)
        self.message_post(body=matn)


class AgroNovaTaklif(models.Model):
    _name = 'agronova.taklif'
    _description = "Xarid taklifi (birinchi xarid solishtiruvi)"
    _order = 'narx, id'

    ruxsat_id = fields.Many2one(
        'agronova.ruxsat', string="Ruxsat", required=True,
        ondelete='cascade', index=True)
    taklif_beruvchi = fields.Char("Taklif beruvchi", required=True)
    kontragent_id = fields.Many2one(
        'res.partner', string="Kontragent",
        domain="[('zakupka_holati', '=', 'faol')]")
    narx = fields.Monetary("Narx", required=True)
    currency_id = fields.Many2one(
        'res.currency', related='ruxsat_id.currency_id', readonly=True)
    yetkazish_muddati = fields.Char("Yetkazish muddati")
    dalil = fields.Binary("Dalil (chek/prays)", attachment=True)
    dalil_filename = fields.Char("Fayl nomi")
    izoh = fields.Char("Izoh")

    @api.constrains('narx')
    def _check_narx(self):
        for rec in self:
            if rec.narx <= 0:
                raise ValidationError(_("Taklif narxi noldan katta bo'lishi kerak."))
