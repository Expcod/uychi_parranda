# -*- coding: utf-8 -*-
"""
attendance_status maydonini mavjud yozuvlarga to'ldirish.

Odoo yangi Selection maydonini qo'shganda default faqat KEYIN
yaratiladigan yozuvlarga tegishli - eski qatorlarda NULL qoladi.
required=True bo'lgani uchun bu keyinchalik xatoga olib keladi.

Mantiq:
    chiqishi bor      -> normal    (haqiqiy davomat)
    chiqishi yo'q     -> tegilmaydi (cron o'zi hal qiladi)

Ochiq yozuvlarni bu yerda yopmaymiz: ular orasida BUGUN ishlab
turgan xodimlar bo'lishi mumkin. Kechasi cron ishga tushganda
kechagilari yopiladi, bugungilari o'z holicha qoladi.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute("""
        UPDATE hr_attendance
        SET attendance_status = 'normal'
        WHERE attendance_status IS NULL
          AND check_out IS NOT NULL
    """)
    _logger.info(
        "Hikvision: %s ta yopiq davomat 'normal' deb belgilandi", cr.rowcount)

    # Ochiq yozuvlar ham NULL qololmaydi (required=True). Ular hali
    # yopilmagan, lekin "unclosed" ham emas - cron hali tegmagan.
    # 'normal' beramiz: chiqish kelsa yoziladi, kelmasa kechasi cron
    # uni 'unclosed' ga o'tkazadi.
    cr.execute("""
        UPDATE hr_attendance
        SET attendance_status = 'normal'
        WHERE attendance_status IS NULL
    """)
    if cr.rowcount:
        _logger.info(
            "Hikvision: %s ta ochiq davomat vaqtincha 'normal' qilindi",
            cr.rowcount)
