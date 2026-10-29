# -*- coding: utf-8 -*-
"""
Auto-close cronni bazadan o'chirish va indekslarni qo'shish.

Auto-close cron ochiq davomatlarga jadval bo'yicha soxta check_out
yozardi. XML dan olib tashlangan, lekin bazadagi ir.cron yozuvi
qolib ketadi va mavjud bo'lmagan metodni chaqirib xato beradi.

MUHIM: Eski (soxta) yozuvlar O'CHIRILMAYDI - ular tarixiy ma'lumot
sifatida qoladi.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # ------------------------------------------------------------------
    # 1. Olib tashlangan cronlarni bazadan o'chirish
    # ------------------------------------------------------------------
    # XML dan olib tashlash yetarli emas: bazadagi ir.cron yozuvi qoladi
    # va mavjud bo'lmagan metodni chaqirib har safar xato beradi.
    obsolete = [
        ('_cron_auto_close_attendance', 'ir_cron_auto_close_attendance'),
        ('_cron_send_logs_to_telegram', 'ir_cron_send_logs_telegram'),
        ('_cron_cleanup_logs', 'ir_cron_cleanup_logs'),
    ]

    for method, xmlid in obsolete:
        pattern = '%' + method + '%'
        cr.execute("""
            DELETE FROM ir_cron
            WHERE id IN (
                SELECT c.id FROM ir_cron c
                JOIN ir_act_server a ON a.id = c.ir_actions_server_id
                WHERE a.code LIKE %s
            )
        """, (pattern,))
        removed = cr.rowcount

        cr.execute("DELETE FROM ir_act_server WHERE code LIKE %s", (pattern,))

        cr.execute("""
            DELETE FROM ir_model_data
            WHERE module = 'hr_hikvision_attendance' AND name = %s
        """, (xmlid,))

        if removed:
            _logger.info("Hikvision migratsiya: %s cron o'chirildi", method)

    # ------------------------------------------------------------------
    # 2. Ishlatilmaydigan tizim parametrlarini tozalash
    # ------------------------------------------------------------------
    # Telegram: modul endi o'z log faylini yozmaydi.
    # Webhook: controller olib tashlandi, loglar faqat cron orqali olinadi.
    cr.execute("""
        DELETE FROM ir_config_parameter
        WHERE key IN ('hikvision.telegram_bot_token',
                      'hikvision.telegram_chat_id',
                      'hikvision.webhook_token')
    """)

    # ------------------------------------------------------------------
    # 3. Xodimsiz loglarni o'chirish
    # ------------------------------------------------------------------
    # employee_id endi required=True. Sabab: NULL bo'lsa unique
    # constraint ishlamaydi - Postgres'da NULL hech qachon NULL bilan
    # to'qnashmaydi, ya'ni dublikat oldini olinmaydi.
    # Xodimsiz loglar ma'nosiz (ular qurilma hodisalari edi).
    cr.execute("DELETE FROM hikvision_log WHERE employee_id IS NULL")
    if cr.rowcount:
        _logger.warning(
            "Hikvision migratsiya: %s ta xodimsiz log o'chirildi", cr.rowcount)

    # ------------------------------------------------------------------
    # 4. Dublikatlarni tozalash
    # ------------------------------------------------------------------
    # models.Constraint unique(device_id, employee_id, timestamp) qo'shadi.
    # Bazada allaqachon dublikat bo'lsa constraint yaratilmaydi va modul
    # yangilanishi xato bilan to'xtaydi. Har guruhdan eng kichik id qoladi.
    cr.execute("""
        DELETE FROM hikvision_log
        WHERE id IN (
            SELECT id FROM (
                SELECT id, ROW_NUMBER() OVER (
                    PARTITION BY device_id, employee_id, timestamp
                    ORDER BY id
                ) AS rn
                FROM hikvision_log
            ) t WHERE t.rn > 1
        )
    """)
    if cr.rowcount:
        _logger.warning(
            "Hikvision migratsiya: %s ta dublikat log o'chirildi", cr.rowcount)

    # ------------------------------------------------------------------
    # 5. Ochiq davomat qidiruvi uchun qisman indeks
    # ------------------------------------------------------------------
    # Bu indeksni field index=True bilan berib bo'lmaydi (WHERE sharti
    # bor). Qolgan indekslar model maydonlarida index=True orqali
    # e'lon qilingan - ular yangi bazalarda ham yaratiladi.
    cr.execute("""
        CREATE INDEX IF NOT EXISTS hr_attendance_open_idx
        ON hr_attendance (employee_id, check_in)
        WHERE check_out IS NULL
    """)

    _logger.info("Hikvision migratsiya: yakunlandi")
