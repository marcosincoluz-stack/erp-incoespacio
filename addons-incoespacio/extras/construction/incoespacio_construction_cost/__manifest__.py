{
    "name": "Incoespacio: Imputación de gastos a obra",
    "summary": "Capítulo, partida y pedido de compra de una obra, sin OCR",
    "version": "17.0.1.0.0",
    "category": "Accounting/Sales",
    "author": "Incoespacio",
    "license": "LGPL-3",
    "depends": ["incoespacio_construction_certification"],
    "data": [
        "views/account_move_views.xml",
        "views/sale_order_views.xml",
        "views/purchase_order_views.xml",
    ],
    "pre_init_hook": "pre_init_hook",
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
