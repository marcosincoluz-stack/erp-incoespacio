{
    "name": "Incoespacio: OCR imputar a obra",
    "summary": "Tras el OCR, sugerir obra (historial proveedor) y capítulo BC3",
    "version": "17.0.1.1.1",
    "category": "Accounting/Invoicing",
    "author": "Incoespacio",
    "license": "LGPL-3",
    "depends": [
        "incoespacio_invoice_ocr",
        "incoespacio_invoice_ocr_async",
        "incoespacio_construction_certification",
    ],
    "data": [
        "views/account_move_views.xml",
        "views/sale_order_views.xml",
    ],
    "installable": True,
    "application": False,
}
