# -*- coding: utf-8 -*-
{
    'name': "Incoluz: OCR de Facturas con IA (Gemini)",
    'version': '14.0.1.0.0',
    'summary': 'Digitalización de facturas de proveedor y cliente con IA (Google Gemini): extracción fiscal, cortafuegos de empresa, alerta IBAN y cola en segundo plano',
    'description': """
Port a Odoo 14 de la suite incoespacio_invoice_ocr (Odoo 17).
Foto fija del código 17 en el momento del port: las mejoras posteriores de 17 NO se auto-portan.
Autor: Incoespacio (ingenieria@incoespacio.com).
    """,
    'author': 'Incoespacio',
    'category': 'Accounting/Invoicing',
    'license': 'LGPL-3',
    'depends': ['account', 'mail'],
    'data': [
        'data/ir_cron_data.xml',
        'views/res_config_settings_views.xml',
        'views/account_move_views.xml',
        'views/templates.xml',
    ],
    'qweb': [
        'static/src/xml/ocr_drawer.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
