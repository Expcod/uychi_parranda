# -*- coding: utf-8 -*-
from . import models


def _agronova_lot_qoidasini_yumshatish(env):
    """`stock.lot`ning standart korxona-o'qish qoidasini yumshatadi.

    Odoo'ning `stock.stock_production_lot_rule` yozuvi
    `noupdate="1"` bilan yuklangan (`addons/stock/security/
    stock_security.xml`), shuning uchun uni XML `<record>` orqali
    qayta yozib bo'lmaydi — Odoo bunday yozuvlarni har safar modul
    yangilanganda ataylab o'tkazib yuboradi (admin sozlamalarini
    saqlash uchun). Shu sabab bu yerda, hook orqali, to'g'ridan-to'g'ri
    yoziladi — har modul yangilanishida qayta tasdiqlanadi.

    Nega kerak: Odoo'ning standart korxonalararo yetkazib berish/qabul
    sinxronizatsiyasi bitta lot yozuvini ikkala tomon uchun ham
    ishlatadi. Qabul qiluvchi korxona jo'natuvchi korxonaning lotini
    o'qiy olmasa (standart qoida shunday), qabul hujjati "o'qishga
    ruxsati yo'q" xatosi bilan yiqiladi.
    """
    rule = env.ref('stock.stock_production_lot_rule', raise_if_not_found=False)
    if rule and rule.perm_read:
        rule.sudo().write({'perm_read': False})


def post_init_hook(env):
    _agronova_lot_qoidasini_yumshatish(env)
