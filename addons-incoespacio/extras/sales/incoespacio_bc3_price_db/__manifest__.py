{
    "name": "Incoespacio: base de precios BC3",
    "summary": "Partidas de un BC3 como productos, buscables por código o nombre en el pedido.",
    "version": "17.0.1.0.0",
    "category": "Sales",
    "author": "Incoespacio",
    "license": "AGPL-3",
    "depends": ["bc3_importer"],
    "data": [
        "security/ir.model.access.csv",
        "data/product_category.xml",
        "data/res_groups.xml",
        "data/generic_products.xml",
        "views/price_db_views.xml",
        "views/sale_order_views.xml",
    ],
    "installable": True,
    "application": True,
    "assets": {
        "web.assets_backend": [
            "incoespacio_bc3_price_db/static/src/js/price_import_continue.js",
        ],
    },
}
