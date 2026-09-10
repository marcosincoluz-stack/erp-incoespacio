# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    gemini_api_key = fields.Char(
        string="API Key de Gemini",
        help="Clave de la API de Google Gemini (Google AI Studio).",
        config_parameter="incoluz_invoice_ocr.gemini_api_key",
    )
    gemini_model = fields.Selection([
        ('gemini-2.5-flash', 'Gemini 2.5 Flash (Recomendado - Rápido y económico)'),
        ('gemini-flash-latest', 'Gemini Flash (Última versión disponible)'),
        ('gemini-2.5-pro', 'Gemini 2.5 Pro (Máxima capacidad)'),
    ], string="Modelo Gemini", default='gemini-2.5-flash',
        config_parameter="incoluz_invoice_ocr.gemini_model")
