# -*- coding: utf-8 -*-
{
    'name': "User App Launcher",
    'summary': "Foydalanuvchi formasida ilovalarga kirish huquqini vizual grid orqali boshqarish",
    'description': """
        Foydalanuvchi (res.users) formasiga yangi 'Ilovalar' bo'limi qo'shadi —
        barcha o'rnatilgan ilovalar ikonka shaklida ko'rsatiladi, har biri
        yonida shu foydalanuvchi kira oladigan/olmaydiganini bildiruvchi
        yoqish/o'chirish tugmasi bor. Tugma bosilganda foydalanuvchi shu
        ilovaning asosiy guruhiga qo'shiladi yoki undan chiqariladi.
    """,
    'author': "DonXolm",
    'category': 'Administration',
    'version': '1.0',
    'license': 'LGPL-3',
    'depends': ['base'],
    'data': [
        'views/res_users_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'user_app_launcher/static/src/js/app_access_grid.js',
            'user_app_launcher/static/src/xml/app_access_grid.xml',
            'user_app_launcher/static/src/scss/app_access_grid.scss',
        ],
    },
}
