# -*- coding: utf-8 -*-
"""
Bloklash (blacklist) funksiyasini bazadan tozalash.

Modul endi xodimlarni Hikvision qurilmasida bloklamaydi. Kod olib
tashlandi, lekin bazada eski cron, model va ustunlar qolib ketadi -
Odoo o'chirilgan modelning jadvalini va inherit qilingan ustunni
o'zi o'chirmaydi.

DIQQAT: qurilmadagi haqiqiy holat bu migratsiya bilan o'zgarmaydi.
Xodimlar qurilmada blocklist'da qolgan bo'lsa, ular o'sha yerda
qoladi - migratsiyadan OLDIN blokdan chiqarilishi kerak.
(2026-08-17 da ikkala qurilma tozalangan: 14 + 19 ta -> normal.)
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # 1. Kunlik ta'til croni. XML'dan olib tashlandi, lekin noupdate=0
    #    bo'lgani uchun ham yozuv bazada qoladi - qo'lda o'chiramiz.
    cr.execute("""
        DELETE FROM ir_cron
        WHERE id IN (
            SELECT res_id FROM ir_model_data
            WHERE module = 'hr_hikvision_attendance'
              AND name = 'ir_cron_sync_leave_status'
              AND model = 'ir.cron'
        )
    """)
    if cr.rowcount:
        _logger.info("Hikvision: ta'til sinxronizatsiya croni o'chirildi")

    # ir.cron ir.actions.server'dan meros oladi - server action ham ketadi
    cr.execute("""
        DELETE FROM ir_model_data
        WHERE module = 'hr_hikvision_attendance'
          AND name = 'ir_cron_sync_leave_status'
    """)

    # 2. hikvision.device.user modeli va jadvali
    cr.execute("DROP TABLE IF EXISTS hikvision_device_user CASCADE")
    cr.execute("""
        DELETE FROM ir_model_fields
        WHERE model = 'hikvision.device.user'
    """)
    cr.execute("""
        DELETE FROM ir_model_data
        WHERE module = 'hr_hikvision_attendance'
          AND model IN ('ir.model', 'ir.model.fields', 'ir.model.access')
          AND name LIKE '%hikvision_device_user%'
    """)
    cr.execute("DELETE FROM ir_model WHERE model = 'hikvision.device.user'")
    _logger.info("Hikvision: hikvision.device.user modeli o'chirildi")

    # 3. hr_employee.hikvision_status ustuni.
    #    Ma'lumot bilan birga ketadi - bu Odoo'ning tasavvuri edi,
    #    qurilmaning haqiqiy holati emas, tiklashning ma'nosi yo'q.
    cr.execute("""
        ALTER TABLE hr_employee DROP COLUMN IF EXISTS hikvision_status
    """)
    cr.execute("""
        DELETE FROM ir_model_fields
        WHERE model = 'hr.employee'
          AND name IN ('hikvision_status', 'hikvision_device_user_ids')
    """)
    _logger.info("Hikvision: hr_employee.hikvision_status ustuni o'chirildi")

    # 4. Endi mavjud bo'lmagan view'lar (ir.ui.view yozuvlari
    #    XML'dan olib tashlansa Odoo o'zi o'chiradi, lekin ular
    #    o'chirilgan maydonlarga ishora qilgani uchun yangilanish
    #    paytida xato bermasligi uchun oldindan olib tashlaymiz).
    cr.execute("""
        DELETE FROM ir_ui_view
        WHERE id IN (
            SELECT res_id FROM ir_model_data
            WHERE module = 'hr_hikvision_attendance'
              AND model = 'ir.ui.view'
              AND name IN ('view_employee_form_hikvision',
                           'view_employee_tree_hikvision')
        )
    """)
    cr.execute("""
        DELETE FROM ir_model_data
        WHERE module = 'hr_hikvision_attendance'
          AND model = 'ir.ui.view'
          AND name IN ('view_employee_form_hikvision',
                       'view_employee_tree_hikvision')
    """)
    _logger.info("Hikvision: eski xodim view'lari o'chirildi")
