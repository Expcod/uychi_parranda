# -*- coding: utf-8 -*-
"""O'rnatishdan keyingi avtomatik sozlash.

Kassir modulni o'rnatgan zahoti ishlata olishi kerak, shuning uchun:

  * moddalarga O'zbekiston hisoblar rejasi kodlari bo'yicha hisob topiladi;
  * har bir korxona (bosh + 7 filial) uchun naqd jurnal va kassa yaratiladi;
  * kassa hisobi (5010) va yo'ldagi pul hisobi (5710) biriktiriladi.

Topilmagan narsani buxgalter qo'lda to'ldiradi — o'rnatish bloklanmaydi.
"""
import logging

_logger = logging.getLogger(__name__)

# Modda xmlid → O'zbekiston hisoblar rejasi kodi
MODDA_HISOBLARI = {
    # KIRIM
    'modda_sotuv': '4010',            # Xaridorlardan olinadigan qarz
    'modda_bankdan': '5110',          # Hisob raqam
    'modda_depozit_qaytdi': '4790',   # Xodimlarning boshqa qarzlari
    'modda_boshqa_kirim': '9390',     # Boshqa operatsion daromadlar
    # CHIQIM
    'modda_oylik': '6710',            # Ish haqi bo'yicha hisob-kitoblar
    'modda_yetkazuvchi': '6010',      # Yetkazib beruvchilarga to'lovlar
    'modda_depozit_berildi': '4790',  # Hisobdor shaxsga berilgan pul
    'modda_xojalik': '9420',          # Ma'muriy xarajatlar
    'modda_transport': '9410',        # Sotish (yo'l) xarajatlari
    'modda_boshqa_chiqim': '9430',    # Boshqa operatsion xarajatlar
}

KASSA_HISOB_KODI = '5010'                  # Naqd pul (milliy valyuta)
VALYUTA_HISOB_KODLARI = ('5020', '5210')   # Naqd pul (chet el valyutasi)
TRANSIT_HISOB_KODI = '5710'                # Yo'ldagi pul


def _hisob_topish(env, kod, company):
    """Kod bo'yicha hisob (aniq mos kelmasa — shu kod bilan boshlanadigan).

    Odoo 19 da `account.account` ko'p korxonali (`company_ids`), filial esa
    ota korxonaning hisoblar rejasini ulashadi — shuning uchun qidiruv
    korxonaning butun ota zanjiri bo'yicha ketadi.
    """
    Account = env['account.account'].sudo()
    base = []
    if company:
        zanjir = company.parent_ids.ids or [company.id]
        base = [('company_ids', 'in', zanjir)]
    hisob = Account.search(base + [('code', '=', kod)], limit=1)
    if not hisob:
        hisob = Account.search(base + [('code', '=like', kod + '%')], limit=1)
    return hisob


def _moddalarni_sozlash(env):
    for xmlid, kod in MODDA_HISOBLARI.items():
        modda = env.ref('agronova_kassa.%s' % xmlid, raise_if_not_found=False)
        if not modda or modda.account_id:
            continue
        hisob = _hisob_topish(env, kod, env.company)
        if hisob:
            modda.account_id = hisob.id
        else:
            _logger.info(
                "Kassa moddasi «%s» uchun %s hisobi topilmadi — buxgalter "
                "qo'lda tanlaydi.", modda.name, kod)


def _naqd_jurnal(env, company, band_kodlar):
    """Korxonaning bo'sh naqd jurnali; bo'lmasa — yangisini yaratadi."""
    Journal = env['account.journal'].sudo()
    band_jurnallar = set(env['agronova.kassa'].sudo().search([]).mapped('journal_id').ids)
    mavjud = Journal.search([
        ('type', '=', 'cash'), ('company_id', '=', company.id),
    ], order='id').filtered(lambda j: j.id not in band_jurnallar)
    if mavjud:
        return mavjud[0]

    kod = 'KASSA'
    n = 1
    while kod in band_kodlar or Journal.search_count([
            ('code', '=', kod), ('company_id', '=', company.id)]):
        n += 1
        kod = 'KSS%d' % n
    band_kodlar.add(kod)
    try:
        jurnal = Journal.create({
            'name': "Kassa (naqd)",
            'type': 'cash',
            'code': kod,
            'company_id': company.id,
        })
        _logger.info("«%s» korxonasi uchun naqd jurnal yaratildi (%s).",
                     company.name, jurnal.code)
        return jurnal
    except Exception as e:  # noqa: BLE001 — jurnalsiz ham modul o'rnatilsin
        _logger.warning("«%s» uchun naqd jurnal yaratib bo'lmadi: %s",
                        company.name, e)
        return Journal.browse()


def _kassalarni_yaratish(env):
    Kassa = env['agronova.kassa'].sudo()
    band_kodlar = set()
    # Bosh korxona birinchi bo'lsin — «markaziy kassa» o'sha yerda.
    korxonalar = env['res.company'].sudo().search([], order='parent_path')
    for company in korxonalar:
        if Kassa.search_count([('company_id', '=', company.id)]):
            continue
        jurnal = _naqd_jurnal(env, company, band_kodlar)
        markaziy = not company.parent_id
        Kassa.create({
            'name': ("Markaziy kassa" if markaziy
                     else "%s — kassa" % company.name),
            'code': 'KASSA' if markaziy else (company.name or '')[:8].upper(),
            'turi': 'markaziy' if markaziy else 'filial',
            'sequence': 5 if markaziy else 10,
            'company_id': company.id,
            'currency_id': company.currency_id.id,
            'journal_id': jurnal.id if jurnal else False,
            'account_id': _hisob_topish(env, KASSA_HISOB_KODI, company).id or False,
            'transit_account_id': _hisob_topish(
                env, TRANSIT_HISOB_KODI, company).id or False,
        })
        _logger.info("«%s» korxonasi uchun kassa yaratildi.", company.name)

    # Mavjud kassalar uchun ham naqd jurnalning «outstanding» hisobini
    # to'ldiramiz — Odoo 19 da usiz to'lov provodkasi umuman yozilmaydi.
    Kassa.search([])._jurnal_outstanding_sozlash()


def _agronova_kassa_post_init(env):
    """Odoo 19: post_init_hook `env` bilan chaqiriladi."""
    try:
        _moddalarni_sozlash(env)
    except Exception as e:  # noqa: BLE001 — o'rnatish yiqilmasin
        _logger.warning("Kassa moddalarini sozlab bo'lmadi: %s", e)
    try:
        _kassalarni_yaratish(env)
    except Exception as e:  # noqa: BLE001
        _logger.warning("Kassalarni yaratib bo'lmadi: %s", e)
