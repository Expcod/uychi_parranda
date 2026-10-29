# -*- coding: utf-8 -*-
"""Vaqt yordamchilari.

Kassa kitobi — rasmiy kunlik hujjat, shuning uchun «kun» har doim
O'zbekiston vaqtida aniqlanadi (foydalanuvchining tz sozlamasidan qat'i
nazar). Aks holda kechqurun 19:00 dan keyin yozilgan chek UTC bo'yicha
ertangi kunga tushib ketadi va kassa kitobi kun bo'yicha yig'ilmaydi.
"""
from datetime import datetime, time

import pytz

from odoo import fields

UZ_TZ = pytz.timezone('Asia/Tashkent')


def uz_day(dt):
    """UTC datetime (naive) → Asia/Tashkent sanasi."""
    if not dt:
        return False
    return pytz.utc.localize(dt).astimezone(UZ_TZ).date()


def uz_today():
    """Hozirgi O'zbekiston sanasi."""
    return uz_day(fields.Datetime.now())


def uz_day_bounds(sana):
    """UZ sanasining [00:00:00, 23:59:59] chegaralari — UTC (naive)."""
    sana = fields.Date.to_date(sana)

    def _utc(t):
        return UZ_TZ.localize(datetime.combine(sana, t)).astimezone(
            pytz.utc).replace(tzinfo=None)

    return _utc(time(0, 0, 0)), _utc(time(23, 59, 59))


def uz_datetime(sana):
    """UZ sanasi → UTC (naive) datetime.

    Bugungi sana uchun hozirgi vaqt qaytadi (yozuvlar kun ichida vaqt
    bo'yicha tartiblanadi), o'tgan yoki kelgusi sana uchun — soat 12:00
    (UZ), ya'ni qaysi tomonga o'girilsa ham o'sha kunda qoladi.
    """
    if not sana:
        return fields.Datetime.now()
    sana = fields.Date.to_date(sana)
    if sana == uz_today():
        return fields.Datetime.now()
    naive = datetime.combine(sana, time(12, 0))
    return UZ_TZ.localize(naive).astimezone(pytz.utc).replace(tzinfo=None)
