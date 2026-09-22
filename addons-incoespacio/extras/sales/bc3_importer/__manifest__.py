{
    "name": "BC3 files importer",
    "summary": "OCA 16 port to 17 + Incoespacio BC3 type fixes",
    "author": "Binhex, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/vertical-construction",
    "category": "BC3",
    "version": "17.0.1.0.10",
    "license": "AGPL-3",
    "depends": ["project", "sale_management"],
    "data": [
        "security/bc3_file_security.xml",
        "security/ir.model.access.csv",
        "wizard/bc3_import_wizard_views.xml",
        "views/bc3_version_views.xml",
        "data/bc3_version_data.xml",
        "views/sale_order_views.xml",
        "data/uom_data.xml",
        "data/product_data.xml",
    ],
    "external_dependencies": {
        "python": ["chardet"],
    },
    "assets": {
        "web.assets_backend": [
            "bc3_importer/static/src/scss/bc3_detail.scss",
            "bc3_importer/static/src/js/bc3_detail.js",
            "bc3_importer/static/src/xml/bc3_detail.xml",
        ],
    },
}
