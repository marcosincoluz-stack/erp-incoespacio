from odoo import models, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_post(self):
        if not self.env.user.has_group("incoespacio_security.group_invoice_validator"):
            raise UserError(_("No tienes permiso para confirmar y publicar facturas."))
        return super().action_post()
