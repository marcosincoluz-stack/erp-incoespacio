# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    ocr_price_unit = fields.Float(copy=False)

    @api.depends("product_id", "product_uom_id", "ocr_price_unit")
    def _compute_price_unit(self):
        super()._compute_price_unit()
        for line in self:
            if line.ocr_price_unit:
                line.price_unit = line.ocr_price_unit
        return True
