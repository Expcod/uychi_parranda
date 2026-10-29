# -*- coding: utf-8 -*-
"""Markazlashgan ish vaqti kalendari va muddat hisobi.

TZ 21.7: «Ish vaqti kalendari markazlashtirilsin — barcha muddat hisoblari
bitta kalendardan olsin.» Zayavkaga javob berish, ruxsatni tasdiqlash va
eskalatsiya oralig'i — uchalasi ham shu mixin orqali hisoblanadi, hech
qayerda `timedelta(hours=...)` bilan qo'lda sanalmaydi.

Kalendar sozlamada (`agronova_zakupka.kalendar_id`) ko'rsatiladi; ko'rsatilmasa
korxonaning standart kalendari olinadi.
"""
from odoo import api, fields, models


class AgroNovaMuddatMixin(models.AbstractModel):
    _name = 'agronova.muddat.mixin'
    _description = "AgroNova — ish vaqti bo'yicha muddat hisobi"

    # Kechikish maydonlari ataylab **oddiy saqlanadigan** maydon, compute emas:
    # ular «hozirgi payt» ga bog'liq, ORM esa vaqt o'tgani uchun qayta
    # hisoblamaydi. Qiymatni hujjatning o'zi (javob berilganda) va
    # `ir.cron` (muddat o'tganda) yangilaydi — shunda hisobotlarda
    # filtrlash va guruhlash ishlaydi.
    kechikdimi = fields.Boolean(
        "Kechikdi", readonly=True, copy=False,
        help="Javob muddati o'tib ketgan va hujjat hali javobsiz.")
    kechikish_soati = fields.Float(
        "Kechikish (ish soati)", readonly=True, copy=False,
        help="Faqat ish soatlari sanaladi — tunda va dam olishda kechikish "
             "o'smaydi.")
    eskalatsiya_darajasi = fields.Integer(
        "Eskalatsiya darajasi", readonly=True, copy=False, default=0,
        help="0 — muddat ichida, 1 — o'rinbosarga o'tdi, 2 — yuqori rahbarga "
             "ko'tarildi.")

    # ------------------------------------------------------------- kalendar
    @api.model
    def _agronova_kalendar(self):
        """Barcha muddat hisoblari uchun yagona kalendar."""
        param = self.env['ir.config_parameter'].sudo().get_param(
            'agronova_zakupka.kalendar_id')
        if param:
            kalendar = self.env['resource.calendar'].browse(int(param)).exists()
            if kalendar:
                return kalendar
        return self.env.company.resource_calendar_id

    @api.model
    def _agronova_muddat_qoshish(self, boshlanish, soat):
        """`boshlanish` dan `soat` ish soati o'tgandagi muddat (Datetime).

        Kalendar topilmasa astronomik soat bilan hisoblaydi — muddat nazorati
        butunlay ishlamay qolmasligi uchun.
        """
        kalendar = self._agronova_kalendar()
        boshlanish = fields.Datetime.to_datetime(boshlanish)
        if not kalendar or not soat:
            from datetime import timedelta
            return boshlanish + timedelta(hours=soat or 0.0)
        natija = kalendar.plan_hours(soat, boshlanish, compute_leaves=True)
        if not natija:
            from datetime import timedelta
            return boshlanish + timedelta(hours=soat)
        return fields.Datetime.to_datetime(natija.replace(tzinfo=None))

    @api.model
    def _agronova_ish_soatlari(self, boshlanish, tugash):
        """Ikki payt orasidagi **ish** soatlari."""
        if not boshlanish or not tugash:
            return 0.0
        boshlanish = fields.Datetime.to_datetime(boshlanish)
        tugash = fields.Datetime.to_datetime(tugash)
        if tugash <= boshlanish:
            return 0.0
        kalendar = self._agronova_kalendar()
        if not kalendar:
            return (tugash - boshlanish).total_seconds() / 3600.0
        import pytz
        utc = pytz.UTC
        data = kalendar.get_work_duration_data(
            utc.localize(boshlanish), utc.localize(tugash), compute_leaves=True)
        return data.get('hours', 0.0)

    # ----------------------------------------------------- meros oluvchi API
    def _agronova_muddat_maydoni(self):
        """(muddat maydoni nomi, javob maydoni nomi) juftligi.

        Meros oluvchi model qaytaradi: qaysi maydon deadline, qaysi maydon
        «javob berildi» belgisi. Javob maydoni to'lgan bo'lsa kechikish
        o'sishdan to'xtaydi.
        """
        raise NotImplementedError(
            "Model _agronova_muddat_maydoni() metodini yozishi kerak.")

    def _agronova_kechikish_yangilash(self):
        """Kechikish maydonlarini qayta hisoblaydi (hujjat va cron chaqiradi)."""
        muddat_f, javob_f = self._agronova_muddat_maydoni()
        hozir = fields.Datetime.now()
        for rec in self:
            muddat = rec[muddat_f]
            javob = rec[javob_f] if javob_f else False
            if not muddat:
                vals = {'kechikdimi': False, 'kechikish_soati': 0.0}
            else:
                tugash = fields.Datetime.to_datetime(javob or hozir)
                muddat = fields.Datetime.to_datetime(muddat)
                if tugash <= muddat:
                    vals = {'kechikdimi': False, 'kechikish_soati': 0.0}
                else:
                    vals = {
                        'kechikdimi': not javob,
                        'kechikish_soati': rec._agronova_ish_soatlari(muddat, tugash),
                    }
            if any(rec[k] != v for k, v in vals.items()):
                super(AgroNovaMuddatMixin, rec.sudo()).write(vals)
        return True
