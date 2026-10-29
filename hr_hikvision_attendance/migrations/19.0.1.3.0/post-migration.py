# -*- coding: utf-8 -*-
"""
Umumiy hikvision_status ni per-device yozuvlarga ko'chirish.

Bu versiyagacha holat hr_employee.hikvision_status da bitta maydonda
saqlanardi - ya'ni barcha qurilmalar uchun bitta qiymat. Endi har
(qurilma, xodim) juftligi uchun alohida yozuv bor.

Migratsiya eski qiymatni HAR BIR tasdiqlangan qurilma uchun
nusxalaydi. Bu eng xavfsiz taxmin: shu paytgacha kod hamma
qurilmaga bir xil holat yuborishga urinardi.

Taxmin noto'g'ri bo'lishi mumkin (aynan shu bug tufayli qurilmalar
ajralib ketgan bo'lishi ehtimoli bor), shuning uchun migratsiyadan
keyin har bir qurilmada "Holatlarni Solishtirish" tugmasini bosish
kerak - u qurilmadagi HAQIQIY holatni o'qib yozuvlarni tuzatadi.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # Jadval yangi model bilan yaratilgan bo'lishi kerak (post bosqichi
    # model yuklangandan keyin ishlaydi), lekin ishonch uchun tekshiramiz.
    cr.execute("SELECT to_regclass('public.hikvision_device_user')")
    if not cr.fetchone()[0]:
        _logger.warning("Hikvision migratsiya: hikvision_device_user jadvali "
                        "topilmadi, holatlar ko'chirilmadi")
        return

    cr.execute("SELECT id, name FROM hikvision_device WHERE state = 'confirmed'")
    devices = cr.fetchall()
    if not devices:
        _logger.info("Hikvision migratsiya: tasdiqlangan qurilma yo'q, "
                     "holatlar ko'chirilmadi")
        return

    for device_id, device_name in devices:
        # ON CONFLICT ishlatilmaydi: _sql_constraints migratsiyadan
        # KEYIN qo'llanadi, shuning uchun unique index bu paytda hali
        # mavjud emas (InvalidColumnReference beradi).
        cr.execute("""
            INSERT INTO hikvision_device_user
                (device_id, employee_id, status, last_sync,
                 create_uid, create_date, write_uid, write_date)
            SELECT %(device)s, e.id, COALESCE(e.hikvision_status, 'normal'), NULL,
                   1, NOW() AT TIME ZONE 'UTC', 1, NOW() AT TIME ZONE 'UTC'
            FROM hr_employee e
            WHERE e.barcode IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM hikvision_device_user du
                  WHERE du.device_id = %(device)s AND du.employee_id = e.id
              )
        """, {'device': device_id})
        _logger.info(
            "Hikvision migratsiya [%s]: %s ta xodim holati ko'chirildi",
            device_name, cr.rowcount)

    # 'partial' yangi qiymat - eski yozuvlarda uchramaydi, lekin
    # umumlashtirilgan maydon endi qurilmalardan hisoblanadi.
    _logger.warning(
        "Hikvision migratsiya: holatlar eski umumiy qiymatdan ko'chirildi. "
        "Har bir qurilmada 'Holatlarni Solishtirish' tugmasini bosing - "
        "qurilmadagi haqiqiy holat bilan moslashtirish uchun.")
