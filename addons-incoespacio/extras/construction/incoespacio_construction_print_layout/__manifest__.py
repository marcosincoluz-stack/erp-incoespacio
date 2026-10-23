{
    "name": "Incoespacio: maquetación del PDF de obra",
    "summary": "PDF personalizado del presupuesto con tabla de mediciones y resumen",
    "version": "17.0.1.0.1",
    "category": "Accounting/Sales",
    "author": "Incoespacio",
    "license": "LGPL-3",
    "depends": ["incoespacio_construction_print_options"],
    "data": [
        "report/report_saleorder_custom.xml",
        "views/print_layout_views.xml",
    ],
    "assets": {
        "web.report_assets_common": [
            "incoespacio_construction_print_layout/static/src/css/print_layout.css",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
