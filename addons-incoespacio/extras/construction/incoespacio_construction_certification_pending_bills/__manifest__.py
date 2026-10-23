{
    "name": "Incoespacio: Facturas de proveedor sin certificar",
    "summary": "Avisar en la certificación de las facturas de la obra aún no cubiertas",
    "version": "17.0.1.0.1",
    "category": "Accounting/Sales",
    "author": "Incoespacio",
    "license": "LGPL-3",
    "depends": ["incoespacio_construction_certification"],
    "data": [
        "views/construction_certification_views.xml",
        "views/account_move_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
