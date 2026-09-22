{
    "name": "Incoespacio: Márgenes de obra",
    "summary": "Comparativa venta / objetivo ejecutado / coste real por partida",
    "version": "17.0.1.2.2",
    "category": "Sales",
    "author": "Incoespacio",
    "license": "LGPL-3",
    "depends": [
        "incoespacio_construction_certification",
        "incoespacio_bc3_planned_cost",
        "incoespacio_invoice_ocr_obra_partida",
        "incoespacio_section_fold",
    ],
    "data": ["views/sale_order_views.xml"],
    "assets": {
        "web.assets_backend": [
            "incoespacio_construction_margins/static/src/scss/margins.scss",
            "incoespacio_construction_margins/static/src/js/margin_lines.js",
        ],
        "web.qunit_suite_tests": [
            "incoespacio_construction_margins/static/tests/margin_lines_tests.js",
        ],
    },
    "auto_install": True,
    "installable": True,
    "application": False,
}
