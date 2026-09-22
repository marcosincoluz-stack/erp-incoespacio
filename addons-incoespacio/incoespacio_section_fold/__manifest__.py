# -*- coding: utf-8 -*-
{
    "name": "Incoespacio - Capítulos plegables",
    "summary": "Plegar secciones de líneas y ver el total de cada capítulo",
    "version": "17.0.1.0.7",
    "category": "Web",
    "author": "Incoespacio",
    "license": "LGPL-3",
    "depends": ["account"],
    "assets": {
        "web.assets_backend": [
            "incoespacio_section_fold/static/src/scss/section_fold.scss",
            "incoespacio_section_fold/static/src/js/section_fold.js",
        ],
        "web.qunit_suite_tests": [
            "incoespacio_section_fold/static/tests/section_fold_tests.js",
        ],
    },
    "auto_install": True,
    "installable": True,
    "application": False,
}
