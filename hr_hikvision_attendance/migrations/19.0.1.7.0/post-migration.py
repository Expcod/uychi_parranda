# -*- coding: utf-8 -*-
"""
last_attendance_id keshini haqiqiy holatga keltirish.

MUAMMO: hr_employee.last_attendance_id (compute, store=True) bir qancha
xodimda NULL yoki eskirgan yozuvga ishora qilib qolgan. Natijada
hr.employee.attendance_state 'checked_out' hisoblanadi va xodim ishga
kelgan bo'lsa ham kartochkada "Absent" ko'rinadi; HR hisoboti ham uni
kelmagan deb sanaydi. hr_attendance qatorlarining o'zi joyida - faqat
kesh maydoni noto'g'ri.

SABABI: _create_log_record dublikat loglarni savepoint + IntegrityError
bilan ushlardi. Fetch oynasi har siklda FETCH_OVERLAP_MINUTES ga orqaga
surilgani uchun dublikat HAR sikl kelardi, ya'ni rollback muntazam
bo'lardi. Odoo'da _FlushingSavepoint.rollback() -> cr.clear() ->
Transaction.clear() zanjiri "discard all fields to recompute" qiladi -
o'sha siklda yaratilgan hr.attendance uchun kutilayotgan compute navbati
tozalanib ketardi.

2026-08-19 holati: bugungi 35 davomatdan 31 tasi shu sababdan "Absent"
edi.

TUZATISH (kodda, 19.0.1.7.0):
  1. _create_log_record endi avval search bilan dublikatni kesadi -
     rollback umuman yuz bermaydi (savepoint faqat poyga holati uchun
     zaxira sifatida qoldi).
  2. _cron_fetch_logs oxirida _refresh_attendance_cache() chaqiriladi -
     kutilmagan rollback bo'lsa ham holat sikl oxirida tiklanadi.

Bu migratsiya esa ALLAQACHON buzilgan yozuvlarni bir marta to'g'rilaydi.

XAVFSIZLIK: hr_attendance ga TEGILMAYDI. Faqat hr_employee ning kesh
ustunlari (last_attendance_id va undan kelib chiqadigan last_check_in /
last_check_out) haqiqiy davomat qatorlaridan qayta hisoblanadi. Ish
soati, ish haqi, davomat vaqtlari o'zgarmaydi.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # Har bir xodim uchun eng oxirgi (check_in bo'yicha) davomat.
    # DISTINCT ON - PostgreSQL'ning shu ish uchun eng arzon usuli.
    cr.execute("""
        WITH oxirgi AS (
            SELECT DISTINCT ON (a.employee_id)
                   a.employee_id, a.id AS att_id, a.check_in, a.check_out
            FROM hr_attendance a
            ORDER BY a.employee_id, a.check_in DESC, a.id DESC
        )
        UPDATE hr_employee e
        SET last_attendance_id = o.att_id,
            last_check_in      = o.check_in,
            last_check_out     = o.check_out
        FROM oxirgi o
        WHERE o.employee_id = e.id
          AND (e.last_attendance_id IS DISTINCT FROM o.att_id
               OR e.last_check_in  IS DISTINCT FROM o.check_in
               OR e.last_check_out IS DISTINCT FROM o.check_out)
    """)
    tuzatilgan = cr.rowcount

    # Davomati umuman yo'q, lekin kesh to'lgan xodimlar (davomat qo'lda
    # o'chirilgan bo'lsa qoladi) - ularni bo'shatamiz.
    cr.execute("""
        UPDATE hr_employee e
        SET last_attendance_id = NULL,
            last_check_in      = NULL,
            last_check_out     = NULL
        WHERE e.last_attendance_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM hr_attendance a WHERE a.employee_id = e.id
          )
    """)
    tozalangan = cr.rowcount

    _logger.info(
        "Hikvision migratsiya 19.0.1.7.0: %s ta xodimning davomat keshi "
        "to'g'rilandi, %s tasi bo'shatildi", tuzatilgan, tozalangan)
