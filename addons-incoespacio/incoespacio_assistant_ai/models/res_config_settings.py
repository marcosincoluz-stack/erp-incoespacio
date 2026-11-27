from odoo import fields, models

from odoo.addons.incoespacio_ai_core.models.ai_ocr_service import GEMINI_MODELS

from .question import DEFAULT_BUDGET


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Interruptor general de IncoBot (avisos, IA y tachado). Va aquí y no en
    # incoespacio_assistant, que está en el tope de líneas.
    assistant_enabled = fields.Boolean(
        string="IncoBot activo",
        config_parameter="incoespacio_assistant.enabled",
    )
    assistant_ai_enabled = fields.Boolean(
        string="Preguntas a la IA",
        config_parameter="incoespacio_assistant_ai.enabled",
    )
    # El precio va con el modelo (PRICES): no se pide. El tope por persona y
    # día sigue por dentro (daily_limit) como seguro, sin pantalla.
    assistant_ai_model = fields.Selection(
        GEMINI_MODELS,
        string="Modelo",
        config_parameter="incoespacio_assistant_ai.model",
        default=lambda self: self.env["assistant.ai.question"]._model(),
    )
    assistant_ai_monthly_budget = fields.Float(
        string="Gasto máximo al mes (€)",
        config_parameter="incoespacio_assistant_ai.monthly_budget",
        default=DEFAULT_BUDGET,
    )
