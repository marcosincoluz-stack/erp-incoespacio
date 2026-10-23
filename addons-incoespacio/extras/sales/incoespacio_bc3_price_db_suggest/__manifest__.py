{
    "name": "Incoespacio: sugerir partida de la base de precios",
    "summary": "Sugerencias al escribir en la línea y sincronía del código BC3 con el producto",
    "version": "17.0.1.0.0",
    "category": "Sales",
    "author": "Incoespacio",
    "license": "AGPL-3",
    "depends": ["incoespacio_bc3_price_db"],
    "data": [
        "views/sale_order_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "incoespacio_bc3_price_db_suggest/static/src/scss/price_db_suggest.scss",
            "incoespacio_bc3_price_db_suggest/static/src/js/price_db_suggest.js",
            "incoespacio_bc3_price_db_suggest/static/src/xml/price_db_suggest.xml",
        ],
    },
    "auto_install": True,
    "installable": True,
    "application": False,
}
