from odoo import SUPERUSER_ID, api

from odoo.addons.incoespacio_ai_core.models.secret_store import GEMINI_KEY


def migrate(cr, version):
    # La clave en claro se cifra si el servidor ya tiene la llave maestra.
    # Si no, se queda como estaba y Ajustes avisa.
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["incoespacio.secret"]._get_secret(GEMINI_KEY)
