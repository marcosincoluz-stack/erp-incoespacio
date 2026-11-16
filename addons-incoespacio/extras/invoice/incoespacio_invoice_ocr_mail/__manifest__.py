# -*- coding: utf-8 -*-
{
    "name": "Incoespacio: Facturas desde el correo",
    "version": "17.0.1.1.0",
    "summary": "Un buzón Outlook crea borradores, clasifica por CIF y deja lo dudoso en revisión",
    "author": "Incoespacio",
    "category": "Accounting/Invoicing",
    "license": "LGPL-3",
    "depends": [
        "incoespacio_invoice_ocr_async",
        "microsoft_outlook",
    ],
    "data": [
        "data/ir_cron_data.xml",
        "views/account_move_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
