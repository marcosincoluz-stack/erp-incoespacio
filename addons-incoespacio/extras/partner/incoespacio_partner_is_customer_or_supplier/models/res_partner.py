# -*- coding: utf-8 -*-
from odoo import _, api, fields, models

class ResPartner(models.Model):
    _inherit = 'res.partner'
    _description = 'Res Partner'

    is_customer = fields.Boolean(
        string='Cliente', compute='_compute_is_customer_supplier', inverse='_inverse_is_customer')
    is_supplier = fields.Boolean(
        string='Proveedor', compute='_compute_is_customer_supplier', inverse='_inverse_is_supplier')

    @api.depends('customer_rank', 'supplier_rank')
    def _compute_is_customer_supplier(self):
        for partner in self:
            partner.is_customer = partner.customer_rank > 0
            partner.is_supplier = partner.supplier_rank > 0

    def _inverse_is_customer(self):
        for partner in self:
            if partner.is_customer:
                if partner.customer_rank <= 0:
                    partner.customer_rank = 1
            else:
                partner.customer_rank = 0

    def _inverse_is_supplier(self):
        for partner in self:
            if partner.is_supplier:
                if partner.supplier_rank <= 0:
                    partner.supplier_rank = 1
            else:
                partner.supplier_rank = 0
