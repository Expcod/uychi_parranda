# -*- coding: utf-8 -*-
"""
Mavjud loglarni yangi `state` maydoniga moslashtirish.

Bu versiyagacha log FAQAT hr.attendance yaratilganda yozilardi -
ya'ni bazadagi har bir mavjud log ta'rifi bo'yicha juftlangan.
Shuning uchun hammasiga state='paired' qo'yiladi.

attendance_id esa orqaga qarab to'ldirilmaydi: qaysi log qaysi
davomatni yaratgani yozib qolinmagan, taxmin qilish esa noto'g'ri
bog'lanish berishi mumkin. Yangi loglarda u to'ldiriladi.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # state maydoni default='unpaired' bilan yaratiladi, lekin eski
    # yozuvlar uchun bu noto'g'ri - ular juftlangan edi.
    cr.execute("""
        UPDATE hikvision_log
        SET state = 'paired'
        WHERE state IS NULL OR state = 'unpaired'
    """)
    _logger.info(
        "Hikvision migratsiya: %s ta mavjud log 'paired' deb belgilandi",
        cr.rowcount)
