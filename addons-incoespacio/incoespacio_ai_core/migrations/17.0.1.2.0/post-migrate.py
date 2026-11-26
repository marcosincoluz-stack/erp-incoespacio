from odoo import SUPERUSER_ID, api

from odoo.addons.incoespacio_ai_core.models.ai_ocr_service import (
    DEFAULT_MODEL,
    GEMINI_MODELS,
    MODEL_PARAM,
)


def migrate(cr, version):
    # gemini-2.5-* se apaga el 2026-12-01 y no está en la lista nueva.
    env = api.Environment(cr, SUPERUSER_ID, {})
    params = env["ir.config_parameter"].sudo()
    if params.get_param(MODEL_PARAM) not in dict(GEMINI_MODELS):
        params.set_param(MODEL_PARAM, DEFAULT_MODEL)
