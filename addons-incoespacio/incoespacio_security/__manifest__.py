# -*- coding: utf-8 -*-
{
    'name': "Incoespacio: Seguridad",
    'version': '17.0.1.0.0',
    'author': 'Incoespacio',
    'category': 'Incoespacio',
    'website': 'https://incoespacio.com',
    'license': 'LGPL-3',
    'summary': """Grupos de seguridad y permisos de facturación, soporte e IT""",
    'description': """
        Módulo de seguridad de Incoespacio (adaptado de incoluz_security):
        - Grupos de Soporte técnico (Lectura, Usuario, Administrador).
        - Grupos de Gestión IT (Usuario, Administrador).
        - Grupo especial de Validadores de Facturación (los únicos autorizados a confirmar facturas oficiales).
    """,
    'depends': ['base', 'account'],
    'data': [
        'security/support_groups.xml',
        'security/it_groups.xml',
        'security/invoice_security.xml',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
