# -*- coding: utf-8 -*-
"""Boquv kunlik jurnalini Telegram bot orqali to'ldirish.

Brigader binoda turadi, kompyuter oldiga bormaydi — telefonida botga
javob beradi. Suhbat oqimi `agronova.jurnal.provider.mixin` da, bu yerda
faqat Boquvga xos savollar.

Ona tovuqdan farqi:

* nobud sababi **ro'yxatdan** tanlanadi (TZ 12-band talabi: har yozuvda
  sabab bo'lsin, lekin matn erkin yozilsa hisobotda guruhlab bo'lmaydi);
* tuxum yo'q — o'rniga o'rtacha vazn va yem sarfi muhim, chunki FCR
  (yem konversiyasi) shulardan hisoblanadi;
* obyekt — bino ichidagi partiya, brigader o'z binosiga biriktirilgan.
"""
from odoo import _, api, fields, models

JURNAL = 'agronova.boquv.jurnal'


class AgroNovaBoquvBot(models.AbstractModel):
    _name = 'agronova.boquv.bot'
    _description = "Boquv — kunlik jurnal bot provayderi"
    _inherit = ['agronova.jurnal.provider.mixin']

    _agronova_jurnal_kod = 'boquv'
    _agronova_jurnal_nomi = "Boquv"

    # ------------------------------------------------------------- obyektlar
    @api.model
    def _jurnal_obyekt(self, tur, partiya_id):
        return self.env['agronova.boquv.partiya'].sudo().browse(
            int(partiya_id)).exists()

    def _jurnal_obyektlar(self, xodim):
        """Brigaderning binosidagi faol partiyalar.

        Xodim binoga biriktirilgan bo'lsa — faqat o'sha bino; filialga
        biriktirilgan bo'lsa — filialdagi hamma bino. Hech qayerga
        biriktirilmagan xodimga **hech narsa** ko'rsatilmaydi, bo'lim
        boshlig'idan tashqari: aks holda Ona tovuq operatoriga Boquv
        jurnali taklif qilinardi.
        """
        bugun = fields.Date.context_today(self)
        if not xodim.agronova_boquv_bino_id and not xodim.agronova_boquv_filial_id                 and not self._jurnal_boshliqmi(
                    xodim, 'agronova_boquv.group_boquv_boshliq'):
            return []
        domain = [('holat', '=', 'active')]
        if xodim.agronova_boquv_bino_id:
            domain.append(('bino_id', '=', xodim.agronova_boquv_bino_id.id))
        elif xodim.agronova_boquv_filial_id:
            domain.append(('filial_id', '=', xodim.agronova_boquv_filial_id.id))

        natija = []
        for p in self.env['agronova.boquv.partiya'].sudo().search(domain):
            bor = self.env[JURNAL].sudo().search_count([
                ('partiya_id', '=', p.id), ('sana', '=', bugun)])
            # Bino nomi «BQ01 / B1-01 · 1-seh» ko'rinishida — kodlar
            # brigaderga kerak emas, unga filial va seh nomi yetarli.
            joy = " · ".join(x for x in (p.filial_id.name, p.bino_id.name)
                             if x)
            natija.append({
                'tur': 'partiya',
                'tur_nomi': "Boquv partiyasi",
                'obyekt_id': p.id,
                'nom': p.name,
                'joy': p.bino_id.display_name or '',
                'yorliq': self._jurnal_yorliq('🐥', "Boquv · %s" % joy,
                                              p.joriy_son),
                'bosh_soni': p.joriy_son,
                'bugun_toldirilgan': bool(bor),
            })
        return natija

    # -------------------------------------------------------------- savollar
    def _jurnal_savollar(self, tur, partiya):
        sabablar = self.env[JURNAL]._fields['nobud_sabab'].selection
        savollar = [
            {'kalit': 'nobud_son', 'tur': 'int', 'majburiy': True,
             'savol': "Bugun nechta bosh nobud bo'ldi?",
             'yordam': "Bo'lmasa 0 yozing."},
            {'kalit': 'nobud_sabab', 'tur': 'tanlov', 'majburiy': True,
             'savol': "Nobud sababi nima?",
             'tanlovlar': list(sabablar),
             'shart': lambda j: j.get('nobud_son', 0) > 0},
            {'kalit': 'harorat', 'tur': 'float', 'majburiy': True,
             'savol': "Binodagi o'rtacha harorat (°C)?",
             'yordam': "O'lchanmagan bo'lsa 0 yozing."},
            {'kalit': 'suv_litr', 'tur': 'float', 'majburiy': False,
             'savol': "Suv sarfi (litr)?", 'yordam': "Bilmasangiz 0 yozing."},
        ]
        # Boquv partiyasida «asosiy yem» maydoni yo'q — qaysi yem
        # berilayotgani kunma-kun o'zgaradi (start, o'sish, finish).
        # Shuning uchun oxirgi ishlatilgani taklif qilinadi, u ham
        # bo'lmasa ro'yxatdan tanlanadi.
        oxirgi = self._oxirgi_yem(partiya)
        if oxirgi:
            savollar.append({
                'kalit': 'yem_product_id', 'tur': 'tanlov', 'majburiy': True,
                'savol': "Qaysi yem berildi?",
                'yordam': "Kecha «%s» edi." % oxirgi.display_name,
                'tanlovlar': self._yem_tanlovlari(partiya, oxirgi)})
        else:
            tanlovlar = self._yem_tanlovlari(partiya)
            if tanlovlar:
                savollar.append({
                    'kalit': 'yem_product_id', 'tur': 'tanlov',
                    'majburiy': True, 'savol': "Qaysi yem berildi?",
                    'tanlovlar': tanlovlar})
        savollar.append({
            'kalit': 'yem_kg', 'tur': 'float', 'majburiy': True,
            'savol': "Necha kg yem sarflandi?",
            'yordam': "Sarflanmagan bo'lsa 0 yozing.",
            'shart': lambda j: bool(j.get('yem_product_id'))})
        savollar.append({
            'kalit': 'izoh', 'tur': 'matn', 'majburiy': False,
            'savol': "Qo'shimcha izoh bormi?",
            'yordam': "Bo'lmasa «yo'q» deb yozing."})
        return savollar

    def _oxirgi_yem(self, partiya):
        """Shu partiyaga oxirgi marta berilgan yem."""
        qator = self.env['agronova.boquv.jurnal.sarf'].sudo().search(
            [('jurnal_id.partiya_id', '=', partiya.id), ('tur', '=', 'yem')],
            order='id desc', limit=1)
        return qator.product_id

    def _yem_tanlovlari(self, partiya, birinchi=None):
        """Tanlov uchun yem mahsulotlari.

        Qamrovi «Mahsulot guruhlari» ma'lumotnomasidagi `yem` guruhidan
        olinadi — shunda dori yoki dezinfeksiya vositasi ro'yxatga
        tushmaydi. Tugmalar ko'p bo'lib ketmasligi uchun o'ntasi bilan
        cheklanadi; oxirgi ishlatilgani doim birinchi turadi.
        """
        domain = self.env['agronova.mahsulot.filtr.mixin']._agronova_mahsulot_domain(
            'yem', [('is_storable', '=', True)])
        mahsulotlar = self.env['product.product'].sudo().search(
            domain, order='name', limit=10)
        if birinchi:
            mahsulotlar = birinchi | (mahsulotlar - birinchi)
        return [(str(m.id), m.display_name) for m in mahsulotlar]

    def _jurnal_tekshir(self, tur, partiya, javoblar):
        nobud = javoblar.get('nobud_son', 0)
        if nobud and nobud > partiya.joriy_son:
            return ('nobud_son',
                    "Binoda %s bosh bor, siz %s bosh nobud yozdingiz."
                    % (partiya.joriy_son, nobud))
        harorat = javoblar.get('harorat')
        if harorat and not (0 < harorat < 60):
            return ('harorat',
                    "Harorat %s °C — bu haqiqatga o'xshamaydi. "
                    "Qaytadan kiriting." % harorat)
        return None

    def _jurnal_xulosa(self, tur, partiya, javoblar):
        sabablar = dict(self.env[JURNAL]._fields['nobud_sabab'].selection)
        q = ["%s · %s" % (partiya.name, partiya.bino_id.display_name or '')]
        nobud = javoblar.get('nobud_son', 0)
        q.append("Nobud: %s%s" % (
            nobud,
            (" (%s)" % sabablar.get(javoblar.get('nobud_sabab'), ''))
            if nobud else ""))
        if javoblar.get('harorat'):
            q.append("Harorat: %s °C" % javoblar['harorat'])
        if javoblar.get('suv_litr'):
            q.append("Suv: %s litr" % javoblar['suv_litr'])
        if javoblar.get('yem_kg') and javoblar.get('yem_product_id'):
            mahsulot = self.env['product.product'].sudo().browse(
                int(javoblar['yem_product_id']))
            q.append("Yem: %s — %s kg" % (mahsulot.display_name,
                                          javoblar['yem_kg']))
        return "\n".join(q)

    # --------------------------------------------------------------- saqlash
    def _jurnal_yaratish(self, xodim, tur, partiya, javoblar):
        bugun = fields.Date.context_today(self)
        if self.env[JURNAL].sudo().search_count([
                ('partiya_id', '=', partiya.id), ('sana', '=', bugun)]):
            return {'ok': False,
                    'error': "«%s» uchun bugungi jurnal allaqachon "
                             "ochilgan." % partiya.name}

        maydonlar = self.env[JURNAL]._fields
        vals = {'partiya_id': partiya.id, 'sana': bugun}
        for kalit, qiymat in javoblar.items():
            # `yem_kg` jurnalda hisoblanadigan maydon — sarf qatoridan
            # chiqadi, to'g'ridan-to'g'ri yozilmaydi.
            if kalit in maydonlar and kalit not in (
                    'yem_kg', 'yem_product_id', 'izoh'):
                if kalit == 'nobud_sabab' and not qiymat:
                    continue
                vals[kalit] = qiymat
        if xodim:
            vals['mas_ul_id'] = xodim.id

        izoh = (javoblar.get('izoh') or '').strip()
        vals['izoh'] = _(
            "Telegram orqali kiritdi: %(kim)s.%(izoh)s",
            kim=xodim.name,
            izoh=("\n" + izoh) if izoh and izoh.lower() != "yo'q" else "")

        yem = javoblar.get('yem_kg') or 0.0
        yem_id = javoblar.get('yem_product_id')
        if yem and yem_id:
            mahsulot = self.env['product.product'].sudo().browse(int(yem_id))
            vals['sarf_ids'] = [(0, 0, {
                'product_id': mahsulot.id,
                'tur': 'yem',
                'miqdor': yem,
                'uom_id': mahsulot.uom_id.id,
            })]

        jurnal = self.env[JURNAL].sudo().create(vals)
        self.env['agronova.telegram.log'].tg_log(
            "Kunlik jurnal (Boquv)", chat_id=xodim.telegram_chat_id,
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
            'ogohlantirish': '',
        }
