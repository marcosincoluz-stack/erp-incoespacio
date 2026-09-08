# -*- coding: utf-8 -*-
{
    'name': "INCOESPACIO: Tema de Odoo",
    'version': '17.0.1.0.0',
    'author': 'Incoespacio',
    'category': 'Themes/Backend',
    'website': 'https://incoespacio.com',
    'license': 'LGPL-3',
    'summary': """Tema de Odoo personalizado con la identidad corporativa de INCOESPACIO""",
    'description': """Personalización de apariencia, marca blanca, pantallas y colores para INCOESPACIO""",
    'depends': ['base', 'web', 'mail', 'web_responsive', 'portal'],
    'data': [
        'views/web_layout_views.xml',
        'views/web_login_layout_views.xml',
        'views/not_powered_by_odoo.xml',
    ],
    'assets': {
        'web._assets_primary_variables': [
            ('prepend', 'incoespacio_theme/static/src/scss/primary_variables.scss'),
        ],
        'web.assets_backend': [
            'incoespacio_theme/static/src/scss/backend_theme.scss',
            'incoespacio_theme/static/src/js/web_title_widget.js',
            'incoespacio_theme/static/src/js/app_sidebar.js',
            'incoespacio_theme/static/src/xml/app_sidebar.xml',
        ],
        'web.assets_frontend': [
            'incoespacio_theme/static/src/css/frontend_theme.css',
        ],
        'web.report_assets_common': [
            'incoespacio_theme/static/src/css/report_theme.css',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
