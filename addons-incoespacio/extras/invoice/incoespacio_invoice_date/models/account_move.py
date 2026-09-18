# -*- coding: utf-8 -*-
from odoo import models, api


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.onchange("invoice_date")
    def _onchange_invoice_date_inherit(self):
        if self.invoice_date:
            self.date = self.invoice_date

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("invoice_date") and not vals.get("date"):
                vals["date"] = vals["invoice_date"]
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("invoice_date") and "date" not in vals:
            vals = dict(vals, date=vals["invoice_date"])
        return super().write(vals)
