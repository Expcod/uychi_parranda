# -*- coding: utf-8 -*-
"""
Ishlatilmaydigan `image` ustunini o'chirish.

hikvision.log.image Binary maydoni model'da e'lon qilingan edi, lekin
hech qachon to'ldirilmagan - qurilmadan rasm olinmaydi. Bo'sh ustun
chalg'itadi, shuning uchun olib tashlanadi.

pre-migration'da: Odoo yangi model sxemasini yuklashdan OLDIN
bajariladi, ya'ni ustun ORM tomonidan hali kutilmayotgan paytda.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute("""
        ALTER TABLE hikvision_log DROP COLUMN IF EXISTS image
    """)
    _logger.info("Hikvision migratsiya: hikvision_log.image ustuni o'chirildi")
