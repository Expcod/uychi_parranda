# -*- coding: utf-8 -*-
"""Kunlik jurnalni Telegram bot orqali to'ldirish — umumiy skelet.

Har bo'limda kunlik jurnal bor: Ona tovuqda tuxum va o'stirish, Boquvda
partiya jurnali, kelajakda Inkubatoriyada harorat jurnali. Ularning
savollari boshqa-boshqa, lekin **suhbat oqimi bir xil**:

    kimman? -> qaysi obyekt? -> savol -> javob -> ... -> xulosa -> saqlash

Shu oqim shu yerda bir marta yozilgan. Bo'lim moduli faqat **o'z
savollarini** beradi.

## Botda nima turadi

Bot bitta modelga murojaat qiladi — `agronova.jurnal.bot`. U barcha
bo'limlarni o'zi topib, ro'yxatni birlashtiradi. Yangi bo'lim qo'shilsa
bot o'zgarmaydi: yangi modul `agronova.jurnal.provider.mixin` dan meros
oladi va ro'yxatga o'zi qo'shiladi.

## Savollar nega dinamik

`_keyingi()` shu paytgacha berilgan javoblarni ko'rib, keyingi savolni
qaytaradi. Shunda shartli savol beriladi yoki tashlab ketiladi: nobud
bo'lmagan kuni «sababi nima?» so'ralmaydi.
"""
from odoo import _, api, models


class AgroNovaJurnalProviderMixin(models.AbstractModel):
    """Bo'lim moduli shu mixindan meros oladi va o'z savollarini beradi."""
    _name = 'agronova.jurnal.provider.mixin'
    _description = "AgroNova — kunlik jurnal bot provayderi"

    # Dispetcher shu ikkitasi bo'yicha tanib oladi
    _agronova_jurnal_provider = True
    _agronova_jurnal_kod = None      # 'ot', 'boquv' — callback data ga sig'sin
    _agronova_jurnal_nomi = None     # "Ona tovuq"

    # ------------------------------------------------------------- ilgaklar
    def _jurnal_obyektlar(self, xodim):
        """Xodim bugun qaysi obyektga jurnal to'ldirishi mumkin.

        Qaytaradi: `[{'tur', 'tur_nomi', 'obyekt_id', 'nom', 'joy',
        'yorliq', 'bosh_soni', 'bugun_toldirilgan'}, ...]`

        `yorliq` — botdagi tugma matni. Uni provayder yasaydi, chunki
        joyni qanday atash bo'limga bog'liq: Ona tovuqda «sex», Boquvda
        «filial, seh».
        """
        raise NotImplementedError

    @api.model
    def _jurnal_yorliq(self, belgi, joy, bosh_soni):
        """Tugma matni: belgi, joy va bosh soni.

        Ichki kod (BQ-2026-0002) tugmaga chiqarilmaydi — brigaderga u
        hech narsa demaydi, faqat joy kerak. Kod tasdiqlash xulosasida
        va Odooda ko'rinadi.
        """
        son = "{:,}".format(int(bosh_soni or 0)).replace(",", " ")
        return "%s %s · %s bosh" % (belgi, joy, son)

    def _jurnal_obyekt(self, tur, obyekt_id):
        """Kod va id bo'yicha yozuv (partiya/sex). Topilmasa bo'sh."""
        raise NotImplementedError

    def _jurnal_savollar(self, tur, obyekt):
        """Savollar ketma-ketligi.

        Har savol: `kalit`, `savol`, `tur` (`int`/`float`/`matn`/`tanlov`),
        ixtiyoriy `yordam`, `majburiy`, `tanlovlar` (tanlov uchun
        `[(qiymat, yorliq), ...]`) va `shart` — javoblar lug'atini oladigan
        funksiya; `False` qaytarsa savol tashlab ketiladi.
        """
        raise NotImplementedError

    def _jurnal_tekshir(self, tur, obyekt, javoblar):
        """Javoblar zid bo'lsa `(kalit, xabar)`, bo'lmasa `None`."""
        return None

    def _jurnal_xulosa(self, tur, obyekt, javoblar):
        """Saqlashdan oldin ko'rsatiladigan qisqacha."""
        return obyekt.display_name

    def _jurnal_yaratish(self, xodim, tur, obyekt, javoblar):
        """Jurnal yozuvini yaratadi va natija lug'atini qaytaradi."""
        raise NotImplementedError

    # ------------------------------------------------------------ yordamchi
    def _jurnal_boshliqmi(self, xodim, guruh_xmlid):
        """Xodim shu bo'limning boshlig'imi.

        Obyektga biriktirilmagan xodimga bo'limning hamma partiyasi
        ko'rsatilmaydi — aks holda Boquv brigadiriga Ona tovuq jurnali
        ham taklif qilinardi. Faqat bo'lim boshlig'i hammasini ko'radi.
        """
        if not xodim.user_id:
            return False
        return xodim.user_id.has_group(guruh_xmlid)

    @api.model
    def _jurnal_xodim(self, chat_id):
        return self.env['hr.employee'].sudo().search(
            [('telegram_chat_id', '=', str(chat_id))], limit=1)

    # -------------------------------------------------------- umumiy oqim
    def _keyingi(self, xodim, tur, obyekt, javoblar):
        """Keyingi savol yoki tugaganlik belgisi."""
        javoblar = dict(javoblar or {})
        xato = self._jurnal_tekshir(tur, obyekt, javoblar)
        if xato:
            return {'ok': True, 'xato': xato[1], 'qayta_kalit': xato[0]}

        for savol in self._jurnal_savollar(tur, obyekt):
            if savol['kalit'] in javoblar:
                continue
            shart = savol.get('shart')
            if shart and not shart(javoblar):
                # So'ralmagan savolga standart qiymat qo'yiladi, aks holda
                # sikl shu savolda tiqilib qolardi.
                javoblar[savol['kalit']] = (
                    '' if savol['tur'] in ('matn', 'tanlov') else 0)
                continue
            natija = {
                'ok': True,
                'kalit': savol['kalit'],
                'savol': savol['savol'],
                'tur': savol['tur'],
                'yordam': savol.get('yordam', ''),
                'majburiy': savol.get('majburiy', False),
                'javoblar': javoblar,
                'tugadi': False,
            }
            if savol.get('tanlovlar'):
                natija['tanlovlar'] = [
                    {'qiymat': q, 'yorliq': y} for q, y in savol['tanlovlar']]
            return natija

        return {'ok': True, 'tugadi': True, 'javoblar': javoblar,
                'xulosa': self._jurnal_xulosa(tur, obyekt, javoblar)}


class AgroNovaJurnalBot(models.AbstractModel):
    """Bot murojaat qiladigan yagona nuqta."""
    _name = 'agronova.jurnal.bot'
    _description = "AgroNova — kunlik jurnal bot API"

    # ------------------------------------------------------------ provayder
    @api.model
    def _providerlar(self):
        """Registrdagi barcha jurnal provayderlari."""
        natija = []
        for nom, klass in self.env.registry.models.items():
            if (getattr(klass, '_agronova_jurnal_provider', False)
                    and getattr(klass, '_agronova_jurnal_kod', None)):
                natija.append(self.env[nom])
        return natija

    @api.model
    def _provider(self, kod):
        for p in self._providerlar():
            if p._agronova_jurnal_kod == kod:
                return p
        return None

    @api.model
    def _xodim(self, chat_id):
        return self.env['hr.employee'].sudo().search(
            [('telegram_chat_id', '=', str(chat_id))], limit=1)

    # --------------------------------------------------------- 1. ro'yxat
    @api.model
    def tg_jurnal_royxat(self, chat_id):
        """Xodim bugun qaysi jurnallarni to'ldirishi mumkin — hamma bo'lim."""
        xodim = self._xodim(chat_id)
        if not xodim:
            return {'ok': False, 'not_linked': True,
                    'error': "Akkaunt bog'lanmagan."}
        obyektlar = []
        for provider in self._providerlar():
            for o in provider._jurnal_obyektlar(xodim):
                o = dict(o)
                o['kod'] = provider._agronova_jurnal_kod
                o['bolim'] = provider._agronova_jurnal_nomi
                obyektlar.append(o)
        return {'ok': True, 'xodim': xodim.name, 'obyektlar': obyektlar}

    # ------------------------------------------------------- 2. savol-javob
    @api.model
    def tg_jurnal_keyingi(self, chat_id, kod, tur, obyekt_id, javoblar=None):
        xodim = self._xodim(chat_id)
        if not xodim:
            return {'ok': False, 'not_linked': True}
        provider = self._provider(kod)
        # DIQQAT: `if not provider` yozib bo'lmaydi — provayder abstrakt
        # model, ya'ni doim BO'SH recordset, va bo'sh recordset `False`
        # beradi. Topilmagani `None` bilan farqlanadi.
        if provider is None:
            return {'ok': False, 'error': _("Bo'lim topilmadi.")}
        obyekt = provider._jurnal_obyekt(tur, obyekt_id)
        if not obyekt:
            return {'ok': False, 'error': _("Yozuv topilmadi.")}
        return provider._keyingi(xodim, tur, obyekt, javoblar or {})

    # ---------------------------------------------------------- 3. saqlash
    @api.model
    def tg_jurnal_saqlash(self, chat_id, kod, tur, obyekt_id, javoblar):
        xodim = self._xodim(chat_id)
        if not xodim:
            return {'ok': False, 'not_linked': True}
        provider = self._provider(kod)
        # DIQQAT: `if not provider` yozib bo'lmaydi — provayder abstrakt
        # model, ya'ni doim BO'SH recordset, va bo'sh recordset `False`
        # beradi. Topilmagani `None` bilan farqlanadi.
        if provider is None:
            return {'ok': False, 'error': _("Bo'lim topilmadi.")}
        obyekt = provider._jurnal_obyekt(tur, obyekt_id)
        if not obyekt:
            return {'ok': False, 'error': _("Yozuv topilmadi.")}
        xato = provider._jurnal_tekshir(tur, obyekt, javoblar)
        if xato:
            return {'ok': False, 'error': xato[1], 'qayta_kalit': xato[0]}
        return provider._jurnal_yaratish(xodim, tur, obyekt, javoblar)
