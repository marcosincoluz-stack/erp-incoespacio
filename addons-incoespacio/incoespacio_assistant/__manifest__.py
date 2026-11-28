{
    "name": "Incoespacio: Asistente",
    "summary": "Avisos por reglas en el chat de IncoBot Asistente",
    "version": "17.0.1.7.0",
    "author": "Incoespacio",
    "license": "LGPL-3",
    "depends": ["mail", "base_user_role"],
    "data": [
        "security/ir.model.access.csv",
        "security/assistant_rules.xml",
        "data/assistant_data.xml",
        "views/assistant_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "incoespacio_assistant/static/src/scss/incobot_links.scss",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
}
