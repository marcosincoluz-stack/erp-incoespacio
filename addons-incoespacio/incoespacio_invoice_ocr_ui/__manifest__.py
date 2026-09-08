# -*- coding: utf-8 -*-
{
    'name': "Incoespacio: Interfaz Reactiva OCR (OWL 2)",
    'version': '17.0.1.0.0',
    'summary': 'Componentes OWL 2: Drawer lateral de progreso en tiempo real y asistente drag-and-drop',
    'author': 'Incoespacio',
    'category': 'Accounting/Invoicing',
    'license': 'LGPL-3',
    'depends': ['incoespacio_invoice_ocr_async', 'web', 'bus'],
    'assets': {
        'web.assets_backend': [
            'incoespacio_invoice_ocr_ui/static/src/components/ocr_upload_wizard/ocr_upload_utils.js',
            'incoespacio_invoice_ocr_ui/static/src/components/ocr_upload_wizard/ocr_upload_wizard_dialog.scss',
            'incoespacio_invoice_ocr_ui/static/src/components/ocr_upload_wizard/ocr_upload_wizard_dialog.xml',
            'incoespacio_invoice_ocr_ui/static/src/components/ocr_upload_wizard/ocr_upload_wizard_dialog.js',
            'incoespacio_invoice_ocr_ui/static/src/components/ocr_upload_wizard/account_file_uploader_patch.js',
            'incoespacio_invoice_ocr_ui/static/src/components/ocr_batch_drawer/ocr_batch_drawer.scss',
            'incoespacio_invoice_ocr_ui/static/src/components/ocr_batch_drawer/ocr_batch_drawer.js',
            'incoespacio_invoice_ocr_ui/static/src/components/ocr_batch_drawer/ocr_batch_drawer.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
