# -*- coding: utf-8 -*-
"""Smena ma'lumotlarini Telegram bot orqali kiritish (TZ 13.1).

Daftarga yoziladigan narsalar — liniya to'xtashi, brak, smena izohi —
botdan kiritiladi. Suhbat oqimi `agronova.jurnal.provider.mixin` da
(Boquv va Ona tovuq bilan bir xil), bu yerda faqat yem zavodi savollari.
Ishlab chiqarilgan miqdor botdan so'ralmaydi: u buyurtmalardan va
tarozidan keladi, qo'lda yozilsa ikki xil raqam paydo bo'lardi.

Rahbar hisobotlari (`tg_yem_hisobot`) ham shu yerda — bot qisqa matn
qaytaradi, raqamlar ERP dan hisoblanadi.
"""
from datetime import datetime, time, timedelta

from odoo import _, api, fields, models

from .agronova_yem_toxtash import SABABLAR
from .agronova_yem_yoqotish import TURLAR as YOQOTISH_TURLARI


class AgroNovaYemBot(models.AbstractModel):
    _name = 'agronova.yem.bot'
    _description = "Yem zavodi — Telegram bot provayderi"
    _inherit = ['agronova.jurnal.provider.mixin']

    _agronova_jurnal_kod = 'yem'
    _agronova_jurnal_nomi = "Yem zavodi"

    # ------------------------------------------------------------- obyektlar
    @api.model
    def _jurnal_obyekt(self, tur, liniya_id):
        return self.env['agronova.yem.liniya'].sudo().browse(int(liniya_id)).exists()

    def _jurnal_obyektlar(self, xodim):
        if not self._jurnal_boshliqmi(xodim, 'agronova_yem_zavodi.group_yem_ishchi'):
            return []
        natija = []
        for l in self.env['agronova.yem.liniya'].sudo().search([]):
            smena = self._joriy_smena(l)
            natija.append({
                'tur': 'liniya',
                'tur_nomi': "Yem zavodi liniyasi",
                'obyekt_id': l.id,
                'nom': l.name,
                'joy': smena.smena_turi_id.name if smena else '',
                'yorliq': "🏭 %s · %s" % (l.name, smena.smena_turi_id.name if smena else ''),
                'bosh_soni': 0,
                'bugun_toldirilgan': bool(smena and smena.bot_kiritdi),
            })
        return natija

    @api.model
    def _joriy_smena_turi(self):
        hozir = fields.Datetime.context_timestamp(self, fields.Datetime.now())
        soat = hozir.hour + hozir.minute / 60.0
        for s in self.env['agronova.yem.smena.turi'].sudo().search([]):
            if s.boshlanish <= s.tugash:
                if s.boshlanish <= soat < s.tugash:
                    return s
            elif soat >= s.boshlanish or soat < s.tugash:
                return s
        return self.env['agronova.yem.smena.turi'].sudo().search([], limit=1)

    @api.model
    def _joriy_smena(self, liniya, yaratilsin=False):
        turi = self._joriy_smena_turi()
        bugun = fields.Date.context_today(self)
        Smena = self.env['agronova.yem.smena'].sudo()
        smena = Smena.search([('liniya_id', '=', liniya.id), ('smena_turi_id', '=', turi.id),
                              ('sana', '=', bugun)], limit=1)
        if not smena and yaratilsin and turi:
            smena = Smena.create({'liniya_id': liniya.id, 'smena_turi_id': turi.id, 'sana': bugun,
                                  'company_id': liniya.company_id.id})
        return smena

    # -------------------------------------------------------------- savollar
    def _jurnal_savollar(self, tur, liniya):
        return [
            {'kalit': 'toxtash_min', 'tur': 'int', 'majburiy': True,
             'savol': "Smenada liniya necha daqiqa to'xtadi?", 'yordam': "To'xtamagan bo'lsa 0 yozing."},
            {'kalit': 'toxtash_sabab', 'tur': 'tanlov', 'majburiy': True,
             'savol': "To'xtash sababi?", 'tanlovlar': list(SABABLAR),
             'shart': lambda j: j.get('toxtash_min', 0) > 0},
            {'kalit': 'uskuna', 'tur': 'matn', 'majburiy': False,
             'savol': "Qaysi uskuna?", 'yordam': "Masalan: granulyator. Bo'lmasa «yo'q».",
             'shart': lambda j: j.get('toxtash_sabab') == 'uskuna'},
            {'kalit': 'brak_kg', 'tur': 'float', 'majburiy': True,
             'savol': "Brak yoki to'kilgan yem (kg)?", 'yordam': "Bo'lmasa 0 yozing."},
            {'kalit': 'brak_turi', 'tur': 'tanlov', 'majburiy': True,
             'savol': "Yo'qotish sababi?",
             'tanlovlar': [t for t in YOQOTISH_TURLARI if t[0] != 'texnologik'],
             'shart': lambda j: j.get('brak_kg', 0) > 0},
            {'kalit': 'izoh', 'tur': 'matn', 'majburiy': False,
             'savol': "Smena bo'yicha izoh?", 'yordam': "Bo'lmasa «yo'q» deb yozing."},
        ]

    def _jurnal_tekshir(self, tur, liniya, javoblar):
        m = javoblar.get('toxtash_min', 0)
        if m and not (0 < m <= 720):
            return ('toxtash_min', "Smena 12 soatdan oshmaydi — daqiqalarni qayta kiriting.")
        b = javoblar.get('brak_kg', 0)
        if b and b > 20000:
            return ('brak_kg', "%s kg — juda katta. Qayta kiriting." % b)
        return None

    def _jurnal_xulosa(self, tur, liniya, javoblar):
        q = ["🏭 %s" % liniya.name]
        if javoblar.get('toxtash_min'):
            q.append("To'xtash: %s daq. (%s)" % (javoblar['toxtash_min'],
                                                  dict(SABABLAR).get(javoblar.get('toxtash_sabab'), '')))
        else:
            q.append("To'xtash: yo'q")
        if javoblar.get('brak_kg'):
            q.append("Yo'qotish: %s kg (%s)" % (javoblar['brak_kg'],
                                                dict(YOQOTISH_TURLARI).get(javoblar.get('brak_turi'), '')))
        izoh = (javoblar.get('izoh') or '').strip()
        if izoh and izoh.lower() != "yo'q":
            q.append("Izoh: %s" % izoh)
        return "\n".join(q)

    # --------------------------------------------------------------- saqlash
    def _jurnal_yaratish(self, xodim, tur, liniya, javoblar):
        smena = self._joriy_smena(liniya, yaratilsin=True)
        if not smena:
            return {'ok': False, 'error': "Smena turlari sozlanmagan."}
        if smena.state == 'tasdiqlangan':
            return {'ok': False, 'error': "Bu smena hisoboti tasdiqlangan."}
        now = fields.Datetime.now()
        if javoblar.get('toxtash_min'):
            uskuna = (javoblar.get('uskuna') or '').strip()
            self.env['agronova.yem.toxtash'].sudo().create({
                'liniya_id': liniya.id, 'smena_id': smena.id,
                'boshlanish': now - timedelta(minutes=int(javoblar['toxtash_min'])), 'tugash': now,
                'sabab': javoblar.get('toxtash_sabab') or 'boshqa',
                'uskuna': uskuna if uskuna.lower() != "yo'q" else False,
                'masul_id': xodim.id, 'izoh': _("Telegram orqali: %s", xodim.name),
                'company_id': liniya.company_id.id,
            })
        if javoblar.get('brak_kg'):
            mo = smena.production_ids[:1]
            self.env['agronova.yem.yoqotish'].sudo().create({
                'liniya_id': liniya.id, 'smena_id': smena.id, 'production_id': mo.id,
                'product_id': mo.product_id.id or self.env['product.product'].sudo().search(
                    [('agronova_yem_turi', '=', 'yem')], limit=1).id,
                'turi': javoblar.get('brak_turi') or 'brak',
                'miqdor_kg': javoblar['brak_kg'], 'masul_id': xodim.id,
                'state': 'tekshiruvda', 'sabab': _("Telegram orqali: %s", xodim.name),
                'company_id': liniya.company_id.id,
            })
        izoh = (javoblar.get('izoh') or '').strip()
        vals = {'bot_kiritdi': True}
        if izoh and izoh.lower() != "yo'q":
            vals['izoh'] = ((smena.izoh + "\n") if smena.izoh else "") + "%s: %s" % (xodim.name, izoh)
        smena.write(vals)
        smena.message_post(body=_("Telegram bot orqali %s kiritdi.", xodim.name))
        self.env['agronova.telegram.log'].sudo().tg_log(
            "Smena (Yem zavodi)", chat_id=xodim.telegram_chat_id, employee_id=xodim.id,
            payload=smena.name)
        return {'ok': True, 'jurnal_id': smena.id, 'partiya': smena.name,
                'sana': str(smena.sana), 'kun_oxiri': 0, 'ogohlantirish': ''}

    # ---------------------------------------------------- rahbar hisobotlari
    @api.model
    def tg_yem_hisobot(self, chat_id, savol='bugun'):
        """Rahbar uchun qisqa hisobot. `savol`: bugun | kecha_bugun | xomashyo |
        yoqotish_oy | jonatma_tafovut | smena_reja."""
        xodim = self._jurnal_xodim(chat_id)
        if not xodim or not self._jurnal_boshliqmi(xodim, 'agronova_yem_zavodi.group_yem_boshliq'):
            return {'ok': False, 'error': "Bu hisobot faqat rahbariyat uchun."}
        fn = getattr(self, '_hisobot_%s' % savol, None)
        if not fn:
            return {'ok': False, 'error': "Noma'lum so'rov."}
        return {'ok': True, 'matn': fn()}

    def _kun_oraligi(self, kun):
        tz = self.env.user.tz or 'Asia/Tashkent'
        import pytz
        z = pytz.timezone(tz)
        dan = z.localize(datetime.combine(kun, time.min)).astimezone(pytz.utc).replace(tzinfo=None)
        return dan, dan + timedelta(days=1)

    def _kun_kg(self, kun):
        dan, gacha = self._kun_oraligi(kun)
        mos = self.env['mrp.production'].sudo().search([
            ('state', '=', 'done'), ('agronova_yem', '=', True),
            ('date_finished', '>=', dan), ('date_finished', '<', gacha)])
        return mos

    def _hisobot_bugun(self):
        bugun = fields.Date.context_today(self)
        mos = self._kun_kg(bugun)
        kg = sum(mos.mapped('agronova_miqdor_kg'))
        q = ["📊 Bugun: %.1f t yem ishlab chiqarildi (%s buyurtma)" % (kg / 1000.0, len(mos))]
        mahsulot = {}
        for m in mos:
            mahsulot[m.product_id.display_name] = mahsulot.get(m.product_id.display_name, 0) + m.agronova_miqdor_kg
        for nom, v in sorted(mahsulot.items(), key=lambda x: -x[1]):
            q.append("• %s — %.1f t" % (nom, v / 1000.0))
        return "\n".join(q)

    def _hisobot_kecha_bugun(self):
        bugun = fields.Date.context_today(self)
        a = sum(self._kun_kg(bugun - timedelta(days=1)).mapped('agronova_miqdor_kg'))
        b = sum(self._kun_kg(bugun).mapped('agronova_miqdor_kg'))
        farq = ((b - a) / a * 100.0) if a else 0.0
        return "Kecha: %.1f t\nBugun: %.1f t\nFarq: %+.1f%%" % (a / 1000.0, b / 1000.0, farq)

    def _hisobot_xomashyo(self):
        z = self.env['agronova.yem.zaxira'].sudo().search([('holat', 'in', ('kritik', 'kam'))])
        if not z:
            return "✅ Minimumdan past xomashyo yo'q."
        return "\n".join(["⚠️ Xomashyo zaxirasi:"] + [
            "• %s — %.1f t (%s kunga)" % (r.product_id.display_name, r.qoldiq_kg / 1000.0, round(r.yetadi_kun, 1))
            for r in z[:15]])

    def _hisobot_yoqotish_oy(self):
        bugun = fields.Date.context_today(self)
        y = self.env['agronova.yem.yoqotish'].sudo().search([
            ('state', '!=', 'rad'), ('sana', '>=', fields.Datetime.to_datetime(bugun.replace(day=1)))])
        jami = sum(y.mapped('miqdor_kg'))
        ortiq = sum(y.mapped('ortiqcha_kg'))
        qiymat = sum(y.mapped('qiymat'))
        return ("📉 Bu oy yo'qotish: %.1f t\nMe'yordan ortiq: %.1f t\nQiymati: %s"
                % (jami / 1000.0, ortiq / 1000.0, "{:,.0f}".format(qiymat).replace(",", " ")))

    def _hisobot_jonatma_tafovut(self):
        bugun = fields.Date.context_today(self)
        dan, gacha = self._kun_oraligi(bugun)
        t = self.env['agronova.tarozi.tortish'].sudo().search([
            ('state', '=', 'done'), ('sana', '>=', dan), ('sana', '<', gacha),
            ('tafovut', 'in', ('ogohlantirish', 'tasdiq', 'kritik'))])
        if not t:
            return "✅ Bugungi tortishlarda tafovut yo'q."
        return "\n".join(["⚖️ Bugungi tafovutlar:"] + [
            "• %s %s: %+.0f kg (%+.2f%%)" % (r.name, r.avto_raqam or '', r.farq_kg, r.farq_pct) for r in t[:15]])

    def _hisobot_smena_reja(self):
        bugun = fields.Date.context_today(self)
        s = self.env['agronova.yem.smena'].sudo().search([('sana', '>=', bugun - timedelta(days=7)),
                                                          ('bajarilish', '<', 95), ('bajarilish', '>', 0)])
        if not s:
            return "✅ Oxirgi 7 kunda reja barcha smenalarda bajarilgan."
        return "\n".join(["Reja bajarilmagan smenalar:"] + [
            "• %s — %.0f%%" % (r.name, r.bajarilish) for r in s[:15]])
