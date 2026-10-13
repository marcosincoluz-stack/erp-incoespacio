# -*- coding: utf-8 -*-
{
    'name': "Incoespacio: Procesamiento Asíncrono de OCR",
    'version': '17.0.1.1.0',
    'summary': 'Cola de digitalización con IA, procesada por el cron de Odoo',
    'author': 'Incoespacio',
    'category': 'Accounting/Invoicing',
    'license': 'LGPL-3',
    'depends': ['incoespacio_invoice_ocr', 'bus'],
    'data': [
        'data/ir_cron_data.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
