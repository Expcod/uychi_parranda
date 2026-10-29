# -*- coding: utf-8 -*-
"""Kunlik jurnalni Telegram bot orqali to'ldirish.

Sex operatori har kuni kompyuter oldiga borib o'tirmaydi — telefonida
botga javob beradi. Bot savolni **bittalab** beradi, operator raqamni
yozadi, keyingisi keladi.

## Nega savollar ro'yxati Odooda

Botda faqat suhbat oqimi turadi: «savol ber → javobni saqla → keyingisini
so'ra». Qaysi savol berilishi, qanday tartibda va qaysi shartda —
hammasi shu yerda. Shunda jurnalga yangi maydon qo'shilsa botni
qayta yozish shart emas, va nazorat qoidalari ikki joyda takrorlanmaydi.

Savollar **dinamik**: `tg_jurnal_keyingi()` shu paytgacha berilgan
javoblarni ko'rib, keyingi savolni qaytaradi. Masalan nobud bo'lmagan
kuni «shundan nechtasi xo'roz?» va «nobud sababi?» so'ralmaydi.

## Nima uchun qoralama bo'lib saqlanadi

Jurnal tasdiqlanganda yem ombordan hisobdan chiqadi va analitik xarajat
yoziladi. Bu buxgalteriya amali — uni telefondan bir tugma bilan qilish
xavfli: operator xato raqam yozsa, storno qilish kerak bo'ladi. Shuning
uchun bot **qoralama** ochadi, sex boshlig'i ko'rib tasdiqlaydi.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Jurnal turlari: kod -> (model, to'liq nom, tugma uchun qisqa nom)
TURLAR = {
    'tuxum': ('agronova.ona_tovuq.jurnal.tuxum', "Ona tovuq (tuxum davri)",
              "Ona tovuq"),
    'ostirish': ('agronova.ona_tovuq.jurnal.ostirish', "Jo'ja o'stirish",
                 "Jo'ja o'stirish"),
}


class AgroNovaOnaTovuqBot(models.AbstractModel):
    """Ona tovuqning kunlik jurnal provayderi.

    Suhbat oqimi `agronova.jurnal.provider.mixin` da — bu yerda faqat
    Ona tovuqqa xos savollar va tekshiruvlar.
    """
    _name = 'agronova.ona_tovuq.bot'
    _description = "Ona tovuq — kunlik jurnal bot provayderi"
    _inherit = ['agronova.jurnal.provider.mixin']

    _agronova_jurnal_kod = 'ot'
    _agronova_jurnal_nomi = "Ona tovuq"

    # ------------------------------------------------------------- yordamchi
    @api.model
    def _jurnal_obyekt(self, tur, partiya_id):
        model = ('agronova.ona_tovuq.partiya.tuxum' if tur == 'tuxum'
                 else 'agronova.ona_tovuq.partiya.ostirish')
        return self.env[model].sudo().browse(int(partiya_id)).exists()

    # ---------------------------------------------------------- 1. ro'yxat
    def _jurnal_obyektlar(self, xodim):
        """Xodim bugun qaysi partiyaga jurnal to'ldirishi mumkin.

        Xodim o'z sexiga biriktirilgan bo'lsa, faqat o'sha sexning faol
        partiyalari chiqadi. Biriktirilmagan xodimga esa **hech narsa**
        ko'rsatilmaydi — bo'lim boshlig'idan tashqari. Aks holda boshqa
        bo'lim xodimiga (masalan Boquv brigadiriga) Ona tovuq jurnali
        taklif qilinardi.
        """
        bugun = fields.Date.context_today(self)
        sex = xodim.agronova_ot_sex_id
        if not sex and not self._jurnal_boshliqmi(
                xodim, 'agronova_ona_tovuq.group_ot_boshliq'):
            return []
        natija = []
        for tur, (jurnal_model, nom, qisqa) in TURLAR.items():
            partiya_model = ('agronova.ona_tovuq.partiya.tuxum' if tur == 'tuxum'
                             else 'agronova.ona_tovuq.partiya.ostirish')
            domain = [('holat', '=', 'active')]
            if sex:
                domain.append(('sex_id', '=', sex.id))
            for p in self.env[partiya_model].sudo().search(domain):
                bor = self.env[jurnal_model].sudo().search_count([
                    ('partiya_id', '=', p.id), ('date', '=', bugun)])
                # Sex nomida qavs ichida bo'lim nomi bor («1-sex (ona
                # tovuq)») — tugmada u ortiqcha, belgi allaqachon aytadi.
                joy = (p.sex_id.name or '').split('(')[0].strip()
                natija.append({
                    'tur': tur,
                    'tur_nomi': nom,
                    'obyekt_id': p.id,
                    'nom': p.name,
                    'joy': p.sex_id.display_name or '',
                    'yorliq': self._jurnal_yorliq(
                        '🥚' if tur == 'tuxum' else '🐣',
                        "%s · %s" % (qisqa, joy) if joy else qisqa,
                        p.joriy_son),
                    'bosh_soni': p.joriy_son,
                    'bugun_toldirilgan': bool(bor),
                })
        return natija

    # --------------------------------------------------------- 2. savollar
    def _jurnal_savollar(self, tur, partiya):
        """Jurnal turi bo'yicha savollar ketma-ketligi.

        Har savol: kalit, savol matni, tur (`int`/`float`/`matn`),
        `majburiy` va ixtiyoriy `shart` — javoblar lug'atini oladigan
        funksiya, u `False` qaytarsa savol o'tkazib yuboriladi.
        """
        umumiy_bosh = [
            {'kalit': 'nobud_son', 'tur': 'int', 'majburiy': True,
             'savol': "Bugun nechta bosh nobud bo'ldi?",
             'yordam': "Bo'lmasa 0 yozing."},
        ]
        if tur == 'tuxum':
            umumiy_bosh.append({
                'kalit': 'nobud_xoroz', 'tur': 'int', 'majburiy': True,
                'savol': "Shundan nechtasi xo'roz?",
                'yordam': "Bilmasangiz 0 yozing.",
                'shart': lambda j: j.get('nobud_son', 0) > 0,
            })
        umumiy_bosh += [
            {'kalit': 'brak_son', 'tur': 'int', 'majburiy': True,
             'savol': "Nechta bosh brak qilindi?",
             'yordam': "Bo'lmasa 0 yozing."},
            {'kalit': 'nobud_sabab', 'tur': 'matn', 'majburiy': True,
             'savol': "Nobud/brak sababi nima?",
             'yordam': "Qisqacha yozing: kasallik, jarohat, issiq...",
             'shart': lambda j: (j.get('nobud_son', 0)
                                 + j.get('brak_son', 0)) > 0},
        ]

        if tur == 'tuxum':
            xos = [
                {'kalit': 'jami_tuxum', 'tur': 'int', 'majburiy': True,
                 'savol': "Bugun jami nechta tuxum yig'ildi?"},
                {'kalit': 'sifatli_tuxum', 'tur': 'int', 'majburiy': True,
                 'savol': "Shundan nechtasi sifatli?",
                 'shart': lambda j: j.get('jami_tuxum', 0) > 0},
                {'kalit': 'brak_tuxum', 'tur': 'int', 'majburiy': True,
                 'savol': "Nechtasi brak?",
                 'shart': lambda j: j.get('jami_tuxum', 0) > 0},
                {'kalit': 'inkubatsiyaga_yarokli', 'tur': 'int',
                 'majburiy': True,
                 'savol': "Inkubatsiyaga nechtasi yaroqli?",
                 'yordam': "Sifatlilardan inkubatsiyaga o'tadigani.",
                 'shart': lambda j: j.get('sifatli_tuxum', 0) > 0},
            ]
        else:
            xos = [
                {'kalit': 'ortacha_vazn', 'tur': 'float', 'majburiy': False,
                 'savol': "O'rtacha vazn (kg)?",
                 'yordam': "Bugun tortilmagan bo'lsa 0 yozing."},
            ]

        oxiri = []
        if partiya.yem_product_id:
            oxiri.append({
                'kalit': 'yem_kg', 'tur': 'float', 'majburiy': True,
                'savol': "Bugun necha kg «%s» sarflandi?"
                         % partiya.yem_product_id.display_name,
                'yordam': "Sarflanmagan bo'lsa 0 yozing."})
        oxiri += [
            {'kalit': 'suv_litr', 'tur': 'float', 'majburiy': False,
             'savol': "Suv sarfi (litr)?", 'yordam': "Bilmasangiz 0 yozing."},
            {'kalit': 'harorat', 'tur': 'float', 'majburiy': False,
             'savol': "Sexdagi harorat (°C)?",
             'yordam': "O'lchanmagan bo'lsa 0 yozing."},
            {'kalit': 'izoh', 'tur': 'matn', 'majburiy': False,
             'savol': "Qo'shimcha izoh bormi?",
             'yordam': "Bo'lmasa «yo'q» deb yozing."},
        ]
        return umumiy_bosh + xos + oxiri

    def _jurnal_tekshir(self, tur, partiya, javoblar):
        """Javoblar bir-biriga zid emasligini tekshiradi.

        Xato topilsa `(kalit, xabar)` qaytadi — bot o'sha savolni qayta
        beradi. Shunda noto'g'ri raqam bilan jurnal ochilmaydi.
        """
        nobud = javoblar.get('nobud_son', 0)
        brak = javoblar.get('brak_son', 0)

        if 'nobud_xoroz' in javoblar and javoblar['nobud_xoroz'] > nobud:
            return ('nobud_xoroz',
                    "Xo'roz soni (%s) nobud sonidan (%s) ko'p bo'lmaydi."
                    % (javoblar['nobud_xoroz'], nobud))

        if 'brak_son' in javoblar and (nobud + brak) > partiya.joriy_son:
            return ('brak_son',
                    "Podada %s bosh bor, siz %s bosh nobud/brak yozdingiz."
                    % (partiya.joriy_son, nobud + brak))

        if tur == 'tuxum':
            jami = javoblar.get('jami_tuxum', 0)
            sifatli = javoblar.get('sifatli_tuxum', 0)
            brak_t = javoblar.get('brak_tuxum', 0)
            yaroqli = javoblar.get('inkubatsiyaga_yarokli', 0)
            if 'sifatli_tuxum' in javoblar and sifatli > jami:
                return ('sifatli_tuxum',
                        "Sifatli tuxum (%s) jamidan (%s) ko'p bo'lmaydi."
                        % (sifatli, jami))
            if 'brak_tuxum' in javoblar and (sifatli + brak_t) > jami:
                return ('brak_tuxum',
                        "Sifatli (%s) + brak (%s) jamidan (%s) oshib ketdi."
                        % (sifatli, brak_t, jami))
            if 'inkubatsiyaga_yarokli' in javoblar and yaroqli > sifatli:
                return ('inkubatsiyaga_yarokli',
                        "Inkubatsiyaga yaroqli (%s) sifatlidan (%s) ko'p "
                        "bo'lmaydi." % (yaroqli, sifatli))
        return None

    def _jurnal_xulosa(self, tur, partiya, javoblar):
        """Saqlashdan oldin ko'rsatiladigan qisqacha."""
        q = ["%s · %s" % (partiya.name, partiya.sex_id.display_name or '')]
        q.append("Nobud: %s, brak: %s" % (javoblar.get('nobud_son', 0),
                                          javoblar.get('brak_son', 0)))
        if tur == 'tuxum':
            q.append("Tuxum: %s (sifatli %s, brak %s, inkubatsiyaga %s)"
                     % (javoblar.get('jami_tuxum', 0),
                        javoblar.get('sifatli_tuxum', 0),
                        javoblar.get('brak_tuxum', 0),
                        javoblar.get('inkubatsiyaga_yarokli', 0)))
        elif javoblar.get('ortacha_vazn'):
            q.append("O'rtacha vazn: %s kg" % javoblar['ortacha_vazn'])
        if javoblar.get('yem_kg'):
            q.append("Yem: %s kg" % javoblar['yem_kg'])
        if javoblar.get('suv_litr'):
            q.append("Suv: %s litr" % javoblar['suv_litr'])
        if javoblar.get('harorat'):
            q.append("Harorat: %s °C" % javoblar['harorat'])
        return "\n".join(q)

    # --------------------------------------------------------- 3. saqlash
    def _jurnal_yaratish(self, xodim, tur, partiya, javoblar):
        """Jurnalni qoralama holatida yaratadi."""
        jurnal_model = TURLAR[tur][0]
        bugun = fields.Date.context_today(self)
        if self.env[jurnal_model].sudo().search_count([
                ('partiya_id', '=', partiya.id), ('date', '=', bugun)]):
            return {'ok': False,
                    'error': "«%s» uchun bugungi jurnal allaqachon "
                             "ochilgan." % partiya.name}

        vals = {'partiya_id': partiya.id, 'date': bugun}
        maydonlar = self.env[jurnal_model]._fields
        for kalit, qiymat in javoblar.items():
            if kalit in maydonlar and kalit != 'yem_kg':
                vals[kalit] = qiymat
        izoh = (javoblar.get('izoh') or '').strip()
        vals['izoh'] = _(
            "Telegram orqali kiritdi: %(kim)s.%(izoh)s",
            kim=xodim.name,
            izoh=("\n" + izoh) if izoh and izoh.lower() != "yo'q" else "")

        yem = javoblar.get('yem_kg') or 0.0
        if yem and partiya.yem_product_id:
            vals['sarf_ids'] = [(0, 0, {
                'product_id': partiya.yem_product_id.id,
                'miqdor': yem,
                'uom_id': partiya.yem_product_id.uom_id.id,
            })]

        try:
            jurnal = self.env[jurnal_model].sudo().create(vals)
        except UserError as e:
            return {'ok': False, 'error': str(e)}

        self.env['agronova.telegram.log'].tg_log(
            "Kunlik jurnal", chat_id=xodim.telegram_chat_id,
            employee_id=xodim.id,
            payload="%s / %s" % (partiya.name, bugun))
        jurnal.message_post(body=_(
            "Telegram bot orqali %(kim)s kiritdi.", kim=xodim.name))
        return {
            'ok': True,
            'jurnal_id': jurnal.id,
            'partiya': partiya.name,
            'sana': str(bugun),
            'kun_oxiri': jurnal.kun_oxiri_son,
            'ogohlantirish': getattr(jurnal, 'ogohlantirish', '') or '',
        }
