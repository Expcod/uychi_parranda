# -*- coding: utf-8 -*-
"""
Eski (bridge'li, 1.0) moduldan yangi kodga o'tish.

KONTEKST
--------
Ba'zi o'rnatmalar 1.0 versiyada qotib qolgan edi: ularda N1Sync.exe
uchun /api/hk/... ko'prigi, ta'til bo'yicha bloklash va per-employee
`hikvision_status` bor. Yangi kodda bularning hech biri yo'q -
u 19.0.1.6.0 gacha rivojlanib, bloklashni butunlay tashlagan.

Bu migratsiya Donxolm uchun yozilgan, keyin AgroNovaga ham
kerak bo'ldi: u ham xuddi shu eski bridge'li versiyada turgan edi.

Qurilmalar endi Tailscale orqali to'g'ridan-to'g'ri ko'rinadi, ya'ni
exe (va u bilan birga ko'prik) kerak emas.

Bu fayl 19.0.1.0.1 da turadi - filtruz'ning eng eski migratsiyasidan
(19.0.1.1.0) OLDIN ishlaydi, shuning uchun qolgan zanjir toza bazada
boshlanadi.

NIMA QILINADI
-------------
Faqat eski versiyada mavjud bo'lgan, yangi kod bilmaydigan qoldiqlar
tozalanadi. Davomat ma'lumotlariga (hikvision_log, hr_attendance)
TEGILMAYDI - ular tarixiy ma'lumot.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # ------------------------------------------------------------------
    # 1. Ko'prik (bridge) qoldiqlari
    # ------------------------------------------------------------------
    # models/hikvision_bridge.py `hikvision.bridge` modelini e'lon
    # qilgan edi. Kod olib tashlandi; Odoo o'chirilgan modelning
    # ir_model yozuvini o'zi tozalamaydi.
    cr.execute("SELECT to_regclass('public.hikvision_bridge')")
    if cr.fetchone()[0]:
        cr.execute("DROP TABLE IF EXISTS hikvision_bridge CASCADE")
        _logger.info("Eski versiyadan migratsiya: hikvision_bridge jadvali o'chirildi")

    cr.execute("""
        DELETE FROM ir_model_fields WHERE model = 'hikvision.bridge'
    """)
    cr.execute("""
        DELETE FROM ir_model_data
        WHERE module = 'hr_hikvision_attendance'
          AND model IN ('ir.model', 'ir.model.fields', 'ir.model.access')
          AND name LIKE '%hikvision_bridge%'
    """)
    cr.execute("DELETE FROM ir_model WHERE model = 'hikvision.bridge'")

    # ------------------------------------------------------------------
    # 2. Exe uchun saqlangan sozlamalar
    # ------------------------------------------------------------------
    # Token va exe sync intervali endi hech kim o'qimaydi. Token -
    # maxfiy qiymat, bazada keraksiz yotishi noto'g'ri.
    cr.execute("""
        DELETE FROM ir_config_parameter
        WHERE key IN ('hr_hikvision_attendance.exe_api_token',
                      'hr_hikvision_attendance.exe_sync_interval')
    """)
    if cr.rowcount:
        _logger.info("Eski versiyadan migratsiya: exe sozlamalari o'chirildi "
                     "(%s ta parametr)", cr.rowcount)

    # ------------------------------------------------------------------
    # 3. hr.employee dagi eski maydonlar
    # ------------------------------------------------------------------
    # Yangi kod (filtruz) hr.employee ga faqat `barcode` index qo'shadi.
    # Quyidagilar eski versiyaga xos edi va ORM ularni endi bilmaydi.
    #
    # DIQQAT: hikvision_person_id ustuni SAQLANADI (o'chirilmaydi).
    # Yangi kod xodimni `barcode` bo'yicha topadi, lekin eskisida
    # terminaldagi employeeNo aynan shu maydonda bo'lishi mumkin -
    # ustunni yo'qotsak, barcode bo'sh xodimlarni qayta bog'lash
    # imkoni yo'qoladi. Ustun ORM'dan tashqarida, zararsiz yotadi.
    for ustun in ('face_enrolled_at', 'face_sync_claimed_at',
                  'face_deleted_hik'):
        cr.execute(
            "ALTER TABLE hr_employee DROP COLUMN IF EXISTS %s" % ustun)
    _logger.info("Eski versiyadan migratsiya: face_* ustunlari o'chirildi")

    # hikvision_status: filtruz 1.5.0 buni o'chiradi ("Odoo'ning
    # tasavvuri edi, qurilmaning haqiqiy holati emas"). Lekin 1.3.0
    # undan hikvision_device_user ga ko'chirmoqchi bo'ladi, ya'ni
    # 1.3.0 ishlagunicha ustun TURISHI kerak. Shuning uchun bu yerda
    # tegmaymiz - zanjir o'zi hal qiladi.

    cr.execute("""
        DELETE FROM ir_model_fields
        WHERE model = 'hr.employee'
          AND name IN ('face_enrolled_at', 'face_sync_claimed_at',
                       'face_deleted_hik')
    """)

    # ------------------------------------------------------------------
    # 4. Endi mavjud bo'lmagan cronlar
    # ------------------------------------------------------------------
    # Eski XML'da bor edi, yangisida yo'q. noupdate=0 bo'lsa
    # ham Odoo o'chirilgan yozuvni har doim ham tozalamaydi; qolib
    # ketsa mavjud bo'lmagan metodni chaqirib xato beradi.
    #
    # ir_cron_sync_leave_status ni filtruz 1.5.0 ham o'chiradi, lekin
    # u post-bosqichda - unga qadar cron bir marta ishga tushishi
    # mumkin. Shuning uchun bu yerda, pre-bosqichda olib tashlaymiz.
    cr.execute("""
        DELETE FROM ir_cron
        WHERE id IN (
            SELECT res_id FROM ir_model_data
            WHERE module = 'hr_hikvision_attendance'
              AND model = 'ir.cron'
              AND name = 'ir_cron_sync_leave_status'
        )
    """)
    if cr.rowcount:
        _logger.info("Eski versiyadan migratsiya: ta'til sinxronizatsiya croni "
                     "o'chirildi")
    cr.execute("""
        DELETE FROM ir_model_data
        WHERE module = 'hr_hikvision_attendance'
          AND name = 'ir_cron_sync_leave_status'
    """)

    # ------------------------------------------------------------------
    # 5. res.config.settings maydonlari
    # ------------------------------------------------------------------
    # Eski versiyada exe tokenini boshqaradigan sozlamalar oynasi bor edi.
    # res.config.settings TransientModel - jadvali yo'q, faqat
    # ir_model_fields yozuvlari qoladi.
    cr.execute("""
        DELETE FROM ir_model_fields
        WHERE model = 'res.config.settings'
          AND name LIKE '%hikvision%'
    """)
    if cr.rowcount:
        _logger.info("Eski versiyadan migratsiya: res.config.settings maydonlari "
                     "o'chirildi (%s ta)", cr.rowcount)

    # ------------------------------------------------------------------
    # 6. Olib tashlangan view'lar
    # ------------------------------------------------------------------
    # Bu view'lar yuqorida o'chirilgan maydonlarga ishora qiladi.
    # Odoo ularni yangilash paytida qayta ishlashga urinsa
    # "Field does not exist" bilan yiqiladi - oldindan olib tashlaymiz.
    cr.execute("""
        DELETE FROM ir_ui_view
        WHERE id IN (
            SELECT res_id FROM ir_model_data
            WHERE module = 'hr_hikvision_attendance'
              AND model = 'ir.ui.view'
              AND name LIKE '%config_settings%'
        )
    """)
    cr.execute("""
        DELETE FROM ir_model_data
        WHERE module = 'hr_hikvision_attendance'
          AND model = 'ir.ui.view'
          AND name LIKE '%config_settings%'
    """)

    _logger.info("Eski versiyadan migratsiya 19.0.1.0.1: yakunlandi")
