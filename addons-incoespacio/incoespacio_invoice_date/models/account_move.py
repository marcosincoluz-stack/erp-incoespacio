# -*- coding: utf-8 -*-
from odoo import models, fields, api

class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.onchange('invoice_date')
    def _onchange_invoice_date_inherit(self):
        self.date = self.invoice_date
