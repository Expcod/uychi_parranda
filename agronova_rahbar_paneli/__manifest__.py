{
    'name': 'Rahbar paneli — Yem zavodi',
    'summary': "Yem zavodi uchun alohida boshqaruv va tahlil paneli",
    'version': '19.0.2.0.0',
    'category': 'AgroNova/Analytics',
    'license': 'LGPL-3',
    'depends': ['agronova_dashboard'],
    'data': ['views/menu.xml', 'views/settings.xml'],
    'assets': {'web.assets_backend': [
        'agronova_rahbar_paneli/static/src/dashboard.js',
        'agronova_rahbar_paneli/static/src/dashboard.scss',
    ]},
    'application': True,
    'installable': True,
}
