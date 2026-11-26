# -*- coding: utf-8 -*-
from odoo import api, fields, models

from .ai_ocr_service import DEFAULT_MODEL, GEMINI_MODELS, MODEL_PARAM
from .secret_store import GEMINI_KEY


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Solo escritura: se pega aquí, se guarda cifrada y nunca se vuelve a mostrar.
    gemini_api_key = fields.Char(
        string="API Key de Gemini",
        help="Pega una clave nueva para sustituir la actual. Se guarda cifrada.",
    )
    # Se rellena en get_values: un compute sin dependencias no llega a la vista
    # de Ajustes (el onchange del registro nuevo lo deja vacío).
    gemini_api_key_status = fields.Char(string="Estado de la clave", readonly=True)
    gemini_model = fields.Selection(
        GEMINI_MODELS,
        string="Modelo Gemini",
        default=DEFAULT_MODEL,
        config_parameter=MODEL_PARAM,
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        res["gemini_api_key_status"] = self.env["incoespacio.secret"]._secret_status(
            GEMINI_KEY
        )
        return res

    def set_values(self):
        res = super().set_values()
        for settings in self:
            if settings.gemini_api_key:
                self.env["incoespacio.secret"]._set_secret(
                    GEMINI_KEY, settings.gemini_api_key
                )
                settings.gemini_api_key = False
        return res

    def action_clear_gemini_api_key(self):
        self.env["incoespacio.secret"]._clear_secret(GEMINI_KEY)
        return {"type": "ir.actions.client", "tag": "reload"}
