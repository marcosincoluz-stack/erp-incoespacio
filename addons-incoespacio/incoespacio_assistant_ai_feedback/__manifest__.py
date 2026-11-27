{
    "name": "Incoespacio: Asistente con IA, valoraciones",
    "summary": "Valorar las respuestas de IncoBot y apuntar lo que no sabe contestar",
    "version": "17.0.1.0.0",
    "author": "Incoespacio",
    "license": "LGPL-3",
    "depends": ["incoespacio_assistant_ai"],
    "data": [
        "views/question_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "incoespacio_assistant_ai_feedback/static/src/js/rating.js",
            "incoespacio_assistant_ai_feedback/static/src/scss/rating.scss",
        ],
    },
    "installable": True,
}
