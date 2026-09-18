{
    "name": "Incoespacio: Lupa de partida",
    "summary": "Comparar presupuesto BC3, factura y certificación en una ficha por partida",
    "version": "17.0.1.2.0",
    "category": "Accounting/Sales",
    "author": "Incoespacio",
    "license": "LGPL-3",
    "depends": [
        "incoespacio_construction_certification_assistant",
        "incoespacio_construction_margins",
    ],
    "data": [
        "security/ir.model.access.csv",
        "wizard/certification_line_lens_views.xml",
        "views/construction_certification_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "incoespacio_construction_certification_assistant_lens/static/src/scss/lens.scss",
        ],
    },
    "installable": True,
    "application": False,
}
