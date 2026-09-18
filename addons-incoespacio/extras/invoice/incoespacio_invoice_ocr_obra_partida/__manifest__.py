{
    "name": "Incoespacio: OCR imputar a partida BC3",
    "summary": "Imputar cada línea de factura de proveedor a una partida del presupuesto, o repartirla",
    "version": "17.0.1.2.1",
    "category": "Accounting/Invoicing",
    "author": "Incoespacio",
    "license": "LGPL-3",
    "depends": ["incoespacio_invoice_ocr_obra"],
    "data": [
        "security/ir.model.access.csv",
        "wizard/split_partida_views.xml",
        "views/account_move_views.xml",
        "views/sale_order_views.xml",
    ],
    "auto_install": True,
    "installable": True,
    "application": False,
}
