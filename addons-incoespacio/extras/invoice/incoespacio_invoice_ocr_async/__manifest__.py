# -*- coding: utf-8 -*-
{
    'name': "Incoespacio: Procesamiento Asíncrono de OCR",
    'version': '17.0.1.0.0',
    'summary': 'Ejecución en segundo plano mediante hilos y cron de la digitalización con IA',
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
