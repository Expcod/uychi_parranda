# -*- coding: utf-8 -*-
"""
Davomat yozuvining holati.

MUAMMO: core hr.attendance bitta xodimda faqat BITTA ochiq davomatga
ruxsat beradi. Xodim chiqishni unutsa (turniketdan o'tmadi, kartasini
olmadi), yozuv ochiq qoladi va ertasi kuni Face ID dan o'tganda yangi
kirish YOZILMAYDI - hikvision_attendance._process_attendance uni rad
etadi. Ya'ni bitta unutilgan chiqish keyingi kunlarni ham buzadi.

YECHIM: kechasi cron ochiq qolgan yozuvlarni yopadi va ularga
"yopilmagan" holatini beradi. Yozuv o'chirilmaydi - HR uni ko'radi va
haqiqiy chiqish vaqtini bilsa qo'lda tuzatadi. Lekin ish vaqti
hisobiga kirmaydi, chunki xodim qachon ketgani noma'lum.

NEGA check_out = check_in: Odoo yozuvni "yopiq" deb bilishi uchun
check_out to'ldirilishi SHART. Jadval oxirini (masalan 17:00) yozish
yolg'on ma'lumot bo'lardi va ish soatini shishirardi - avvalgi
"Auto Close Attendance" croni aynan shu sababli olib tashlangan
(qarang: data/ir_cron_data.xml). check_in ning o'zini yozsak,
worked_hours tabiiy ravishda 0 bo'ladi.
"""

from odoo import models, fields


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    attendance_status = fields.Selection([
        ('normal', 'Normal'),
        ('unclosed', 'Yopilmagan'),
    ], string='Holat', default='normal', required=True, index=True,
       help="Normal: kirish va chiqish qurilmadan olingan.\n"
            "Yopilmagan: xodim chiqishda qurilmadan o'tmagan. Yozuv "
            "ko'rinadi, lekin ish vaqti hisobiga kirmaydi.")

    def write(self, vals):
        """
        HR haqiqiy chiqish vaqtini kiritsa - yozuv normalga qaytadi.

        Cron check_out = check_in qilib qo'ygan. HR o'sha xodimdan
        so'rab haqiqiy vaqtni yozsa, yozuv yana to'liq hisoblanishi
        kerak - aks holda tuzatishning ma'nosi qolmaydi.

        attendance_status vals ichida bo'lsa tegmaymiz: cron yoki HR
        holatni ataylab o'zgartirayotgan bo'lishi mumkin.
        """
        result = super().write(vals)

        if 'check_out' in vals and 'attendance_status' not in vals:
            fixed = self.filtered(
                lambda r: r.attendance_status == 'unclosed'
                and r.check_out and r.check_out != r.check_in
            )
            if fixed:
                super(HrAttendance, fixed).write({'attendance_status': 'normal'})

        return result
