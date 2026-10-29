# -*- coding: utf-8 -*-
"""Didox integratsiyasi (TZ 9-bo'lim).

Oqim:

    Tovar sotib olindi -> kirim hujjati tasdiqlandi -> `account.move`
    (in_invoice) o'sha zahoti yoziladi: qarz tan olindi (MSFO)
        -> Didox'dan faktura keldi (1-2 kundan keyin) -> STIR + summa +
           sana bo'yicha solishtirildi
        -> rasmiy hujjat raqami mavjud qarz yozuviga biriktirildi

**Odoo 19 haqida eslatma.** TZ 9-bo'limi «Stock Interim (Received)»
oraliq hisobiga tayanadi; Odoo 19 da ombor baholash modeli o'zgargan va
input/output oraliq hisoblari olib tashlangan (o'rniga
`property_stock_valuation_account_id` + `account_stock_variation_id`).
Shuning uchun oraliq qarzning roli bu yerda **bizning kirim
fakturamiz** o'ynaydi: u tovar bilan bir vaqtda yoziladi, Didox hujjati
esa unga *bog'lanadi*, ikkinchi faktura sifatida yozilmaydi. Natija
TZ talab qilgan bilan bir xil — qarz tovar nazorati o'tgan zahoti tan
olinadi va Didox kechikishi oqimni to'xtatmaydi.

Shu moduldan noldan yoziladigani: **tortib olish**, **solishtirish** va
**ikki tomonlama hisobot**.

API ulanishi `_agronova_didox_soov()` metodida ajratilgan: Didox rekvizitlari
sozlamada bo'lmasa cron xatoga tushmaydi, shunchaki hech nima tortmaydi.
Solishtirish mantig'i esa API'dan mustaqil — qo'lda kiritilgan yozuvda ham
ishlaydi va test qilinadi.
"""
import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Summa solishtirishda ruxsat etilgan farq (yaxlitlash uchun).
SUMMA_TOLERANS = 0.01
# Sana solishtirishda ruxsat etilgan oyna (kun).
SANA_TOLERANS = 5


class AgroNovaDidoxLog(models.Model):
    _name = 'agronova.didox.log'
    _description = "Didox faktura yozuvi"
    _inherit = ['mail.thread']
    _order = 'sana desc, id desc'

    name = fields.Char("Didox hujjat raqami", required=True, index=True)
    sana = fields.Date("Faktura sanasi", required=True, index=True)
    hujjat_turi = fields.Selection(
        [('faktura', "Hisob-faktura"),
         ('akt', "Bajarilgan ish akti"),
         ('shartnoma', "Shartnoma"),
         ('boshqa', "Boshqa")],
        string="Hujjat turi", default='faktura', required=True)
    stir = fields.Char("Kontragent STIRi", required=True, index=True)
    kontragent_id = fields.Many2one(
        'res.partner', string="Kontragent", compute='_compute_kontragent_id',
        store=True, readonly=True)
    summa = fields.Monetary("Summa", required=True)
    qqs_summasi = fields.Monetary("QQS summasi")
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one(
        'res.company', string="Korxona", required=True,
        default=lambda self: self.env.company)

    moslashtirilgan_kirim_id = fields.Many2one(
        'agronova.kirim', string="Moslashtirilgan kirim", readonly=True,
        copy=False, index='btree_not_null')
    holat = fields.Selection(
        [('kutilmoqda', "Kutilmoqda (tovari topilmadi)"),
         ('moslashtirildi', "Moslashtirildi"),
         ('nomos', "Nomuvofiqlik")],
        string="Holati", default='kutilmoqda', required=True, tracking=True)
    nomoslik_izohi = fields.Text("Nomuvofiqlik izohi", readonly=True)
    xom_javob = fields.Text(
        "Didox javobi (xom)", readonly=True,
        help="API dan kelgan asl yozuv — nizoli holatda tekshirish uchun.")

    _didox_hujjat_uniq = models.Constraint(
        'UNIQUE(name, company_id)',
        "Bu Didox hujjati allaqachon yuklangan.",
    )

    @api.depends('stir')
    def _compute_kontragent_id(self):
        Partner = self.env['res.partner'].sudo()
        for rec in self:
            rec.kontragent_id = Partner.search(
                [('stir', '=', rec.stir)], limit=1) if rec.stir else False

    # ------------------------------------------------------- API ulanishi
    @api.model
    def _agronova_didox_sozlama(self):
        param = self.env['ir.config_parameter'].sudo()
        return {
            'url': param.get_param('agronova_zakupka.didox_url'),
            'login': param.get_param('agronova_zakupka.didox_login'),
            'token': param.get_param('agronova_zakupka.didox_token'),
        }

    @api.model
    def _agronova_didox_soov(self, boshlanish, tugash):
        """Didox'dan hujjatlar ro'yxatini oladi.

        Qaytaradi: `[{'name', 'sana', 'stir', 'summa', 'qqs_summasi',
        'hujjat_turi', 'xom'}, ...]`.

        Rekvizitlar sozlanmagan bo'lsa bo'sh ro'yxat qaytaradi — cron
        xatoga tushmaydi. Haqiqiy API chaqiruvi shu metodda, boshqa
        hech qayerda: Didox tomonidagi o'zgarish faqat shu joyni tegadi.
        """
        sozlama = self._agronova_didox_sozlama()
        if not (sozlama['url'] and sozlama['token']):
            _logger.info(
                "Didox rekvizitlari sozlanmagan — tortib olish o'tkazib "
                "yuborildi.")
            return []
        try:
            import requests
            javob = requests.get(
                '%s/v1/documents/inbox' % sozlama['url'].rstrip('/'),
                headers={'Authorization': 'Bearer %s' % sozlama['token']},
                params={'from': boshlanish.isoformat(),
                        'to': tugash.isoformat()},
                timeout=30,
            )
            javob.raise_for_status()
            return [self._agronova_didox_normalize(x) for x in javob.json()]
        except Exception as xato:      # noqa: BLE001 — cron to'xtamasligi kerak
            _logger.warning("Didox'dan tortib olishda xato: %s", xato)
            return []

    @api.model
    def _agronova_didox_normalize(self, xom):
        """Didox javobini bizning maydonlarga o'giradi."""
        return {
            'name': str(xom.get('doc_id') or xom.get('number') or ''),
            'sana': xom.get('doc_date') or xom.get('date'),
            'stir': str(xom.get('seller_tin') or xom.get('tin') or ''),
            'summa': float(xom.get('total_sum') or 0.0),
            'qqs_summasi': float(xom.get('vat_sum') or 0.0),
            'hujjat_turi': 'faktura',
            'xom': repr(xom),
        }

    # --------------------------------------------------------------- cron
    @api.model
    def _cron_didox_tortish(self):
        """Har soatda yangi fakturalarni tortib oladi."""
        tugash = fields.Date.context_today(self)
        boshlanish = tugash - relativedelta(days=30)
        yozuvlar = self._agronova_didox_soov(boshlanish, tugash)
        yaratildi = self.browse()
        for yozuv in yozuvlar:
            if not yozuv.get('name') or not yozuv.get('stir'):
                continue
            mavjud = self.sudo().search([
                ('name', '=', yozuv['name']),
                ('company_id', '=', self.env.company.id)], limit=1)
            if mavjud:
                continue
            yaratildi |= self.sudo().create({
                'name': yozuv['name'],
                'sana': yozuv['sana'],
                'stir': yozuv['stir'],
                'summa': yozuv['summa'],
                'qqs_summasi': yozuv.get('qqs_summasi', 0.0),
                'hujjat_turi': yozuv.get('hujjat_turi', 'faktura'),
                'xom_javob': yozuv.get('xom'),
                'company_id': self.env.company.id,
            })
        if yaratildi:
            yaratildi.action_solishtirish()
        return True

    @api.model
    def _cron_didox_solishtirish(self):
        kutayotganlar = self.sudo().search([('holat', '=', 'kutilmoqda')])
        kutayotganlar.action_solishtirish()
        self.env['agronova.kirim']._cron_faktura_ogohlantirish()
        return True

    # -------------------------------------------------------- solishtirish
    def action_solishtirish(self):
        """STIR + summa + sana bo'yicha kirim hujjatini topadi (TZ 9)."""
        Kirim = self.env['agronova.kirim'].sudo()
        for rec in self:
            if rec.holat == 'moslashtirildi':
                continue
            if not rec.kontragent_id:
                rec.nomoslik_izohi = _(
                    "STIR %s bo'yicha kontragent bazada topilmadi.", rec.stir)
                continue
            nomzodlar = Kirim.search([
                ('kontragent_id', '=', rec.kontragent_id.id),
                ('faktura_holati', '=', 'kutilmoqda'),
                ('sotib_olingan_sana', '>=', rec.sana - relativedelta(
                    days=SANA_TOLERANS)),
                ('sotib_olingan_sana', '<=', rec.sana + relativedelta(
                    days=SANA_TOLERANS)),
            ])
            aniq = nomzodlar.filtered(
                lambda k: abs(k.jami_summa - rec.summa) <= SUMMA_TOLERANS)
            if len(aniq) == 1:
                rec._agronova_moslashtirish(aniq)
            elif len(aniq) > 1:
                rec.write({
                    'holat': 'nomos',
                    'nomoslik_izohi': _(
                        "Bir xil summa va sanadagi %s ta kirim topildi — "
                        "qo'lda tanlash kerak: %s",
                        len(aniq), ", ".join(aniq.mapped('name'))),
                })
            elif nomzodlar:
                rec.write({
                    'holat': 'nomos',
                    'nomoslik_izohi': _(
                        "Kontragent va sana mos, lekin summa farq qiladi. "
                        "Didox: %(didox)s; kirimlar: %(kirim)s",
                        didox=rec.summa,
                        kirim=", ".join(
                            "%s=%s" % (k.name, k.jami_summa) for k in nomzodlar)),
                })
            else:
                rec.nomoslik_izohi = _(
                    "Mos kirim hujjati topilmadi — tovari hali kelmagan "
                    "bo'lishi mumkin.")
        return True

    def _agronova_moslashtirish(self, kirim):
        """Fakturani kirimga bog'laydi va vaqtinchalik hisobni yopadi."""
        self.ensure_one()
        kirim.ensure_one()
        self.write({'holat': 'moslashtirildi',
                    'moslashtirilgan_kirim_id': kirim.id,
                    'nomoslik_izohi': False})
        kirim.write({'faktura_holati': 'moslashtirildi',
                     'didox_log_id': self.id})
        if kirim.faktura_id:
            # Didox raqami buxgalteriya hujjatida ko'rinib tursin.
            kirim.faktura_id.sudo().write({
                'ref': _("%(kirim)s / Didox %(didox)s",
                         kirim=kirim.name, didox=self.name),
            })
        kirim.message_post(body=_(
            "Didox fakturasi %(didox)s (%(sana)s, %(summa)s) bilan "
            "solishtirildi.", didox=self.name, sana=self.sana, summa=self.summa))
        return True

    def action_qolda_moslashtirish(self):
        """Buxgalter kirim hujjatini qo'lda tanlaydi."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Kirim hujjatini tanlash"),
            'res_model': 'agronova.kirim',
            'view_mode': 'list,form',
            'domain': [('faktura_holati', '=', 'kutilmoqda'),
                       ('kontragent_id', '=', self.kontragent_id.id)],
            'context': {'agronova_didox_log_id': self.id},
        }

    def action_bogllash(self):
        """Kontekstdagi kirim bilan bog'laydi (list ko'rinishidan chaqiriladi)."""
        self.ensure_one()
        kirim_id = self.env.context.get('agronova_kirim_id')
        if not kirim_id:
            raise UserError(_("Kirim hujjati ko'rsatilmagan."))
        self._agronova_moslashtirish(self.env['agronova.kirim'].browse(kirim_id))
        return True


class AgroNovaKirimDidox(models.Model):
    """Faktura kutish nazorati — kirim hujjati tomonidagi qismi."""
    _inherit = 'agronova.kirim'

    faktura_kutish_kuni = fields.Integer(
        "Faktura kutilmoqda (kun)", compute='_compute_faktura_kutish_kuni',
        search='_search_faktura_kutish_kuni')

    def _compute_faktura_kutish_kuni(self):
        bugun = fields.Date.context_today(self)
        for rec in self:
            if rec.faktura_holati == 'kutilmoqda' and rec.sotib_olingan_sana:
                rec.faktura_kutish_kuni = (bugun - rec.sotib_olingan_sana).days
            else:
                rec.faktura_kutish_kuni = 0

    def _search_faktura_kutish_kuni(self, operator, value):
        if operator not in ('>', '>=', '<', '<='):
            raise NotImplementedError(
                _("Bu filtr faqat solishtirish bilan ishlaydi."))
        chegara = fields.Date.context_today(self) - relativedelta(days=value)
        teskari = {'>': '<', '>=': '<=', '<': '>', '<=': '>='}[operator]
        return [('faktura_holati', '=', 'kutilmoqda'),
                ('sotib_olingan_sana', teskari, chegara)]

    @api.model
    def _cron_faktura_ogohlantirish(self):
        """Faktura N kundan oshsa buxgalterga xabar (TZ 9-bo'lim)."""
        kun = int(self.env['ir.config_parameter'].sudo().get_param(
            'agronova_zakupka.didox_kutish_kun', 3) or 3)
        chegara = fields.Date.context_today(self) - relativedelta(days=kun)
        kechikkanlar = self.sudo().search([
            ('faktura_holati', '=', 'kutilmoqda'),
            ('sotib_olingan_sana', '<', chegara),
            ('xarid_turi', '!=', 'A_naqd'),
        ])
        guruh = self.env.ref('agronova_zakupka.group_zakupka_buxgalter',
                             raise_if_not_found=False)
        buxgalterlar = guruh.sudo().all_user_ids if guruh else self.env['res.users']
        for rec in kechikkanlar:
            mavjud = rec.activity_ids.filtered(
                lambda a: a.user_id in buxgalterlar)
            if mavjud:
                continue
            for user in buxgalterlar:
                rec.activity_schedule(
                    'mail.mail_activity_data_todo', user_id=user.id,
                    summary=_("Didox fakturasi kelmadi: %s", rec.name),
                    note=_("«%(kontragent)s» dan tovar %(kun)s kun oldin "
                           "olingan, Didox fakturasi hali kelmadi. QQS "
                           "zachyoti yo'qolmasligi uchun tekshiring.",
                           kontragent=rec.kontragent_id.display_name,
                           kun=rec.faktura_kutish_kuni))
        return True
