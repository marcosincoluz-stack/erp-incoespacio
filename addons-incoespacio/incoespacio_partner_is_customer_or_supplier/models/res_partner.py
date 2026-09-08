# -*- coding: utf-8 -*-
from odoo import _, api, fields, models

class ResPartner(models.Model):
    _inherit = 'res.partner'
    _description = 'Res Partner'

    is_customer = fields.Boolean(string='Cliente')
    is_supplier = fields.Boolean(string='Proveedor')
