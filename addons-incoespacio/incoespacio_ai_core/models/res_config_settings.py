# -*- coding: utf-8 -*-
from odoo import fields, models

from .secret_store import GEMINI_KEY


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Solo escritura: se pega aquí, se guarda cifrada y nunca se vuelve a mostrar.
    gemini_api_key = fields.Char(
        string="API Key de Gemini",
        help="Pega una clave nueva para sustituir la actual. Se guarda cifrada.",
    )
    gemini_api_key_status = fields.Char(
        string="Estado de la clave",
        compute="_compute_gemini_api_key_status",
    )
    gemini_model = fields.Selection(
        [
            ("gemini-2.5-flash", "Gemini 2.5 Flash (Recomendado - Rápido y económico)"),
            ("gemini-flash-latest", "Gemini Flash (Última versión disponible)"),
            ("gemini-2.5-pro", "Gemini 2.5 Pro (Máxima capacidad)"),
        ],
        string="Modelo Gemini",
        default="gemini-2.5-flash",
        config_parameter="incoespacio_invoice_ocr.gemini_model",
    )

    def _compute_gemini_api_key_status(self):
        status = self.env["incoespacio.secret"]._secret_status(GEMINI_KEY)
        for settings in self:
            settings.gemini_api_key_status = status

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
