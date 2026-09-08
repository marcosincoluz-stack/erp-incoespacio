# -*- coding: utf-8 -*-
{
    'name': "Incoespacio: Vista Partida de Facturas (Split View)",
    'version': '17.0.1.0.0',
    'summary': 'Visualizador de PDF lado a lado integrado en el formulario de la factura',
    'author': 'Incoespacio',
    'category': 'Accounting/Invoicing',
    'license': 'LGPL-3',
    'depends': ['account', 'web'],
    'data': [
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
