# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AgroNovaKassaModda(models.Model):
    """Kassa moddasi — pul qayerdan keldi yoki nimaga ketdi.

    Modda uch narsani hal qiladi:

      1. **Hisobot** — kassa kitobida va rahbar kesimida kirim/chiqim
         nima maqsadda bo'lganini ko'rsatadi.
      2. **Buxgalteriya** — qo'lda kiritilgan yozuvda provodkaning ikkinchi
         tomoni shu moddaning hisobi bo'ladi (birinchisi — kassa hisobi).
      3. **Xatti-harakat** — modda yozuvning qaysi mexanizmga ulanishini
         belgilaydi: mijoz qarzini yopishmi, depozitga berishmi yoki
         oddiy xo'jalik xarajatimi.

    Bir moddaga bir vaqtda bittadan ortiq maxsus xatti-harakat qo'yilmaydi —
    aks holda bitta pul ikki mexanizmda ikki marta hisoblanardi.
    """
    _name = 'agronova.kassa.modda'
    _description = "Kassa moddasi (kirim/chiqim turi)"
    _order = 'direction, sequence, id'

    name = fields.Char(string="Nomi", required=True, translate=True)
    sequence = fields.Integer(string="Tartib", default=10)
    active = fields.Boolean(string="Faol", default=True)
    direction = fields.Selection([
        ('in', "Kirim"),
        ('out', "Chiqim"),
    ], string="Turi", required=True, default='out', index=True)
    account_id = fields.Many2one(
        'account.account', string="Buxgalteriya hisobi",
        help="Provodkaning ikkinchi tomoni. KIRIM: Dt kassa / Kt shu hisob. "
             "CHIQIM: Dt shu hisob / Kt kassa. Qo'lda kiritiladigan "
             "yozuvlar uchun to'ldirilishi shart.",
    )
    company_id = fields.Many2one(
        'res.company', string="Korxona",
        help="Bo'sh bo'lsa — barcha filiallarda ishlatiladi.",
    )
    izoh_majburiy = fields.Boolean(
        string="Izoh majburiy", default=True,
        help="Belgilansa — bu modda tanlanganda izoh yozilmasa saqlanmaydi.",
    )
    analitik_majburiy = fields.Boolean(
        string="Analitika majburiy", default=False,
        help="Belgilansa — yozuvda analitik taqsimot ko'rsatilmasa "
             "saqlanmaydi. Xarajat moddalarida yoqib qo'yiladi: TZ bo'yicha "
             "analitik kesimga biriktirilmagan xarajat tannarxga tushmaydi.",
    )

    # ------------------------------------------------------------------
    # Maxsus xatti-harakatlar
    # ------------------------------------------------------------------
    qarz_yopish = fields.Boolean(
        string="Mijoz qarzini yopadi", default=False,
        help="Belgilansa — bu modda bo'yicha kirim yozilganda mijozga "
             "to'lov (account.payment) yaratiladi va ochiq hisob-fakturalar "
             "bilan yarashtiriladi, ya'ni qarz avtomat kamayadi.",
    )
    yetkazuvchi_tolov = fields.Boolean(
        string="Yetkazib beruvchi qarzini yopadi", default=False,
        help="Belgilansa — chiqimda yetkazib beruvchiga to'lov yaratiladi "
             "va uning hisob-varaqalari bilan yarashtiriladi.",
    )
    depozit = fields.Boolean(
        string="Depozit harakati", default=False,
        help="Belgilansa — yozuvda depozit egasi tanlanadi. Kassadan "
             "CHIQIM depozitga kirim, kassaga KIRIM esa depozitdan chiqim "
             "bo'lib yoziladi (agronova.depozit).",
    )
    otkazma = fields.Boolean(
        string="Kassalararo transfer", default=False,
        help="Kassalararo transfer hujjati shu moddani qo'yadi. Har "
             "yo'nalish uchun bittadan belgilash kifoya — qo'lda "
             "tanlanmaydi.",
    )
    inkassatsiya = fields.Boolean(
        string="Inkassatsiya", default=False,
        help="Inkassatsiya hujjati (kassa → bank) shu moddani qo'yadi.",
    )
    topshiriq = fields.Boolean(
        string="Topshirilgan summa", default=False,
        help="Belgilansa — bu modda bo'yicha chiqimlar rahbar kesimida "
             "«topshirilgan pul» sifatida alohida ko'rsatiladi.",
    )
    note = fields.Char(string="Tavsif")

    # Faqat hujjat orqali qo'yiladigan moddalar — panelda ro'yxatda
    # ko'rinmasligi kerak, aks holda kassir juftsiz yozuv yaratib qo'yadi.
    faqat_hujjat = fields.Boolean(
        string="Faqat hujjatdan", compute='_compute_faqat_hujjat', store=True,
    )

    @api.depends('otkazma', 'inkassatsiya')
    def _compute_faqat_hujjat(self):
        for rec in self:
            rec.faqat_hujjat = rec.otkazma or rec.inkassatsiya

    @api.depends('name', 'direction')
    def _compute_display_name(self):
        turlar = dict(self._fields['direction'].selection)
        for rec in self:
            rec.display_name = "%s (%s)" % (rec.name or '',
                                            turlar.get(rec.direction, ''))

    @api.constrains('qarz_yopish', 'yetkazuvchi_tolov', 'depozit', 'otkazma',
                    'inkassatsiya', 'direction')
    def _check_xatti_harakat(self):
        for rec in self:
            bayroqlar = [rec.qarz_yopish, rec.yetkazuvchi_tolov, rec.depozit,
                         rec.otkazma, rec.inkassatsiya]
            if sum(1 for b in bayroqlar if b) > 1:
                raise ValidationError(_(
                    "«%s» moddasiga bir vaqtda bittadan ortiq maxsus "
                    "xatti-harakat qo'yib bo'lmaydi — bo'lmasa bitta pul "
                    "ikki mexanizmda ikki marta hisoblanadi.", rec.name))
            if rec.qarz_yopish and rec.direction != 'in':
                raise ValidationError(_(
                    "«%s»: mijoz qarzi faqat KIRIM moddasida yopiladi.",
                    rec.name))
            if rec.yetkazuvchi_tolov and rec.direction != 'out':
                raise ValidationError(_(
                    "«%s»: yetkazib beruvchiga to'lov faqat CHIQIM "
                    "moddasida bo'ladi.", rec.name))

    # ------------------------------------------------------------------
    # Hujjatlar uchun yordamchi
    # ------------------------------------------------------------------

    @api.model
    def _hujjat_moddasi(self, bayroq, direction):
        """Hujjat qo'yadigan moddani topadi (topilmasa — bo'sh recordset)."""
        return self.sudo().search([
            (bayroq, '=', True), ('direction', '=', direction),
        ], limit=1)
