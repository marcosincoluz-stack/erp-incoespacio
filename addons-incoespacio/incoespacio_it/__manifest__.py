# -*- coding: utf-8 -*-
{
    "name": "Incoespacio: Gestión IT",
    "version": "17.0.1.0.0",
    "author": "Incoespacio",
    "category": "Incoespacio",
    "website": "https://incoespacio.com",
    "license": "LGPL-3",
    "summary": "Inventario de equipos informáticos",
    "depends": ["mail", "incoespacio_security"],
    "data": [
        "security/ir.model.access.csv",
        "data/device_data.xml",
        "views/device_views.xml",
    ],
    "installable": True,
    "application": True,
}
