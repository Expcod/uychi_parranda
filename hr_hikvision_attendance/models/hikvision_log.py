# -*- coding: utf-8 -*-
"""
Hikvision xom davomat logi.

MUHIM PRINSIP: bu jadval qurilmadan kelgan HODISALARNI saqlaydi,
hisoblangan HOLATNI emas. Shuning uchun muvaffaqiyatli autentifikatsiya
qilingan har bir o'tish shu yerga yoziladi - hr.attendance ga
juftlangan-juftlanmaganidan qat'i nazar.

Ilgari log faqat hr.attendance yaratilsa yozilardi. Natijada kun
ichidagi 3-4-5-chi o'tish hech qayerda qolmasdi va "ish vaqtida
qancha yo'q bo'ldi" kabi hisoblar uchun ma'lumot yetishmasdi.
Tashlab yuborilgan hodisani qaytarib bo'lmaydi, shuning uchun
saqlash va juftlash bir-biridan ajratilgan.
"""

from odoo import models, fields


class HikvisionLog(models.Model):
    _name = 'hikvision.log'
    _description = 'Hikvision Attendance Log'
    _order = 'timestamp desc'

    device_id = fields.Many2one(
        'hikvision.device', string='Device', required=True,
        index=True, ondelete='restrict')
    # required=True: employee_id NULL bo'lsa unique constraint ishlamaydi -
    # Postgres'da NULL hech qachon NULL bilan to'qnashmaydi.
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True,
        index=True, ondelete='restrict')
    timestamp = fields.Datetime(string='Timestamp', required=True, index=True)
    attendance_type = fields.Selection([
        ('check_in', 'Check In'),
        ('check_out', 'Check Out')
    ], string='Attendance Type')

    # =====================================================
    # JUFTLASH NATIJASI
    # =====================================================
    # Log yozilishi juftlashga bog'liq emas. Bu maydonlar juftlash
    # natijasini qayd etadi - HR juftlanmagan hodisalarni ko'rib,
    # sababini tekshira olsin.
    state = fields.Selection([
        ('paired', 'Juftlandi'),
        ('unpaired', 'Juftlanmadi'),
    ], string='Holat', default='unpaired', required=True, index=True,
       help="Juftlandi: log hr.attendance yozuviga bog'landi.\n"
            "Juftlanmadi: hodisa qayd etildi, lekin davomat yozuviga "
            "bog'lanmadi (masalan, chiqishsiz ikkinchi kirish).")

    attendance_id = fields.Many2one(
        'hr.attendance', string='Davomat', index=True, ondelete='set null',
        help="Shu log yaratgan yoki yopgan davomat yozuvi.")

    skip_reason = fields.Char(
        string='Juftlanmaslik sababi',
        help="Log nega davomatga bog'lanmadi.")

    # =====================================================
    # QURILMADAN KELGAN XOM QIYMATLAR
    # =====================================================
    # Diagnostika uchun. Qurilma kutilmagan kod yuborsa yoki
    # juftlash noto'g'ri ishlasa - manbani tekshirish mumkin.
    raw_minor = fields.Integer(
        string='Minor kodi', readonly=True,
        help="Qurilmadan kelgan hodisa turi kodi (75=yuz, 1=karta, ...).")
    serial_no = fields.Char(
        string='Seriya raqami', readonly=True,
        help="Qurilmaning o'z hodisa raqami.")

    # Dedup DB darajasida. Python tomondagi "avval qidir, keyin yoz"
    # tekshiruvi ishonchli emas: cron qayta ishga tushsa yoki qo'lda
    # "Loglarni Olish" tugmasi cron bilan bir vaqtda bosilsa,
    # ikkalasi ham "yo'q ekan" deb topib, ikki marta yozishi mumkin.
    #
    # DIQQAT: Odoo 19 da _sql_constraints ISHLAMAYDI - u faqat
    # ogohlantirish yozib, jimgina e'tiborsiz qoldiriladi
    # (odoo/orm/model_classes.py:162). models.Constraint ishlatiladi.
    _uniq_device_employee_timestamp = models.Constraint(
        'unique(device_id, employee_id, timestamp)',
        'Bu log allaqachon mavjud (qurilma + xodim + vaqt).',
    )
