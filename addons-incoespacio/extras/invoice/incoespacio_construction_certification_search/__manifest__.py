{
    "name": "Incoespacio - Buscar partidas en certificación",
    "summary": "Lupa para saltar a una partida por código, nombre o precio",
    "version": "17.0.1.1.0",
    "category": "Accounting/Sales",
    "author": "Incoespacio",
    "license": "LGPL-3",
    "depends": ["incoespacio_construction_certification"],
    "data": [
        "views/construction_certification_views.xml",
        "views/sale_order_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "incoespacio_construction_certification_search/static/src/scss/certification_search.scss",
            "incoespacio_construction_certification_search/static/src/js/certification_line_search.js",
            "incoespacio_construction_certification_search/static/src/xml/certification_line_search.xml",
        ],
        "web.qunit_suite_tests": [
            "incoespacio_construction_certification_search/static/tests/certification_line_search_tests.js",
        ],
    },
    "auto_install": True,
    "installable": True,
    "application": False,
}
