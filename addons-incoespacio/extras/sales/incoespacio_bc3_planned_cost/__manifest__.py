{
    "name": "Incoespacio: BC3 coste previsto",
    "summary": "P. objetivo = P.U. × (100 − margen objetivo) %. Las cantidades se cambian en el pedido.",
    "version": "17.0.1.2.1",
    "category": "Sales",
    "author": "Incoespacio",
    "license": "LGPL-3",
    "depends": ["bc3_importer"],
    "data": ["views/sale_order_views.xml"],
    "assets": {
        "web.assets_backend": [
            "incoespacio_bc3_planned_cost/static/src/js/price_edit_guard.js",
        ],
        "web.qunit_suite_tests": [
            "incoespacio_bc3_planned_cost/static/tests/price_edit_guard_tests.js",
        ],
    },
    "installable": True,
    "application": False,
}
