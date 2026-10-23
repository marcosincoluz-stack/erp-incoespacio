{
    "name": "Incoespacio: Repartir gasto entre partidas",
    "summary": "Asistentes para imputar o repartir una factura de proveedor entre partidas",
    "version": "17.0.1.0.0",
    "category": "Accounting/Sales",
    "author": "Incoespacio",
    "license": "LGPL-3",
    "depends": ["incoespacio_construction_cost"],
    "data": [
        "security/ir.model.access.csv",
        "wizard/split_partida_views.xml",
        "views/account_move_views.xml",
    ],
    "auto_install": True,
    "installable": True,
    "application": False,
}
