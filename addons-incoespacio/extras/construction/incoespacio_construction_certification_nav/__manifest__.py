{
    "name": "Incoespacio - Ruta de obra",
    "summary": "Ruta Obra, Presupuesto, Certificación y Factura en la cabecera de los formularios",
    "version": "17.0.1.0.0",
    "category": "Accounting/Sales",
    "author": "Incoespacio",
    "license": "LGPL-3",
    "depends": ["incoespacio_construction_certification"],
    "data": [
        "views/nav_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "incoespacio_construction_certification_nav/static/src/scss/obra_path.scss",
        ],
    },
    "installable": True,
    "application": False,
}
