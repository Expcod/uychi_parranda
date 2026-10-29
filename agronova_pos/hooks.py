# -*- coding: utf-8 -*-
"""O'rnatishdan keyingi avtomatik sozlash.

**POS uchun debitor hisobi.** Smena yopilganda Odoo naqd tushum uchun
oraliq («outstanding») provodka yozadi va uning hisobi
`res.company.account_default_pos_receivable_account_id` dan olinadi. Bu
maydon bo'sh bo'lsa smena umuman yopilmaydi — bazada
`account_move_line_check_accountable_required_fields` cheklovi buziladi
va kassir tushunarsiz SQL xatosini ko'radi.

AgroNova bazasida bu maydon bo'sh edi (buxgalteriya auditida
qayd etilgan), shuning uchun modul uni o'zi to'ldiradi.

**Nega 4010 emas.** 4010 — xaridorlarning haqiqiy qarzi. POS oraliq
hisobi esa bir kun ichida ochilib yopiladigan texnik hisob: smena
yopilguncha pul unda turadi. Ikkalasini bitta hisobga qo'yish debitor
qarz hisobotini POS aylanmasi bilan ifloslantiradi, shuning uchun
alohida **4011** ochiladi.
"""
import logging

_logger = logging.getLogger(__name__)

POS_HISOB_KODI = '4011'
POS_HISOB_NOMI = "POS hisob-kitoblari (oraliq)"
# Yangi hisob shu hisobning oilasidan ajratiladi — hisoblar rejasidagi
# joyi va turi o'sha yerdan olinadi.
ASOS_HISOB_KODI = '4010'


def _pos_hisobini_topish(env, company):
    """Korxona uchun POS oraliq hisobi (bo'lmasa — yaratadi)."""
    Account = env['account.account'].sudo()
    zanjir = company.parent_ids.ids or [company.id]
    base = [('company_ids', 'in', zanjir)]

    hisob = Account.search(base + [('code', '=', POS_HISOB_KODI)], limit=1)
    if hisob:
        return hisob

    asos = Account.search(base + [('code', '=', ASOS_HISOB_KODI)], limit=1)
    if not asos:
        # Hisoblar rejasi o'rnatilmagan — buxgalter qo'lda tanlaydi.
        return Account.browse()
    return Account.create({
        'code': POS_HISOB_KODI,
        'name': POS_HISOB_NOMI,
        'account_type': 'asset_receivable',
        'reconcile': True,
        'company_ids': [(6, 0, asos.company_ids.ids)],
    })


def _korxonalarni_sozlash(env):
    for company in env['res.company'].sudo().search([]):
        if company.account_default_pos_receivable_account_id:
            continue
        if not company.chart_template:
            continue
        hisob = _pos_hisobini_topish(env, company)
        if hisob:
            company.account_default_pos_receivable_account_id = hisob.id
            _logger.info(
                "«%s» korxonasiga POS debitor hisobi biriktirildi (%s).",
                company.name, hisob.code)
        else:
            _logger.warning(
                "«%s» korxonasi uchun POS debitor hisobi topilmadi — "
                "buxgalter qo'lda tanlashi kerak, aks holda smena "
                "yopilmaydi.", company.name)


def _agronova_pos_post_init(env):
    """Odoo 19: post_init_hook `env` bilan chaqiriladi."""
    try:
        _korxonalarni_sozlash(env)
    except Exception as e:  # noqa: BLE001 — o'rnatish yiqilmasin
        _logger.warning("POS debitor hisobini sozlab bo'lmadi: %s", e)
