# -*- coding: utf-8 -*-
from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    gemini_api_key = fields.Char(
        string="API Key de Gemini",
        help="Clave de la API de Google Gemini (Google AI Studio).",
        config_parameter="incoespacio_invoice_ocr.gemini_api_key",
    )
    gemini_model = fields.Selection(
        [
            ('gemini-2.5-flash', 'Gemini 2.5 Flash (Recomendado - Rápido y económico)'),
            ('gemini-flash-latest', 'Gemini Flash (Última versión disponible)'),
            ('gemini-2.5-pro', 'Gemini 2.5 Pro (Máxima capacidad)'),
        ],
        string="Modelo Gemini",
        default='gemini-2.5-flash',
        config_parameter="incoespacio_invoice_ocr.gemini_model",
    )
    ocr_auto_create_partner = fields.Boolean(
        string="Crear proveedor automáticamente",
        help="Si el CIF leído de la factura no existe en Odoo, crea automáticamente la ficha del contacto como proveedor (Opción A).",
        default=True,
        config_parameter="incoespacio_invoice_ocr.auto_create_partner",
    )
    ocr_default_expense_account_id = fields.Many2one(
        'account.account',
        string="Cuenta de gasto por defecto",
        help="Cuenta contable aplicada a las líneas de gasto cuando no haya producto o cuenta predeterminada (ej. 600000 o 629000).",
        domain="[('deprecated', '=', False), ('account_type', '=', 'expense')]",
        config_parameter="incoespacio_invoice_ocr.default_expense_account_id",
    )
