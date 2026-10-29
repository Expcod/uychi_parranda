{
    'name': 'Hikvision Face ID Attendance',
    'version': '19.0.1.7.0',
    'category': 'Human Resources',
    'summary': 'Integration with Hikvision Face ID devices for attendance',
    'description': """
        This module integrates Hikvision Face ID devices with Odoo HR Attendance.
        It allows managing devices and fetching attendance logs.
    """,
    'author': 'NovaCode',
    # hr_holidays OLIB TASHLANDI (2026-08-17): ta'til bo'yicha bloklash
    # yo'q qilingandan keyin modul hr.leave ga umuman murojaat qilmaydi.
    'depends': ['base', 'hr', 'hr_attendance'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/hikvision_device_views.xml',
        'views/hikvision_log_views.xml',
        'views/hr_attendance_views.xml',
        'views/hr_employee_views.xml',
        'views/hikvision_menus.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
