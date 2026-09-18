# -*- coding: utf-8 -*-
{
    "name": "Incoespacio - Chatter plegable",
    "summary": "Plegar el panel de mensajes del formulario para ganar espacio",
    "version": "17.0.1.0.5",
    "category": "Web",
    "author": "Incoespacio",
    "license": "LGPL-3",
    "depends": ["mail"],
    "assets": {
        "web.assets_backend": [
            "incoespacio_chatter_fold/static/src/scss/chatter_fold.scss",
            "incoespacio_chatter_fold/static/src/xml/chatter_fold.xml",
            "incoespacio_chatter_fold/static/src/js/chatter_fold.js",
        ],
        "web.qunit_suite_tests": [
            "incoespacio_chatter_fold/static/tests/chatter_fold_tests.js",
        ],
    },
    "auto_install": True,
    "installable": True,
    "application": False,
}
