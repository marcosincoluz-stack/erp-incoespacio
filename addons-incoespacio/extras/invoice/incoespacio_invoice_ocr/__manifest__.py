# -*- coding: utf-8 -*-
{
    'name': "Incoespacio: OCR de Facturas con IA (Core)",
    'version': '17.0.1.0.0',
    'summary': 'Extracción y conciliación contable inteligente de facturas mediante IA',
    'author': 'Incoespacio',
    'category': 'Accounting/Invoicing',
    'license': 'LGPL-3',
    'depends': [
        'account',
        'incoespacio_security',
        'incoespacio_ai_core',
        'incoespacio_partner_is_customer_or_supplier',
    ],
    'data': [
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
