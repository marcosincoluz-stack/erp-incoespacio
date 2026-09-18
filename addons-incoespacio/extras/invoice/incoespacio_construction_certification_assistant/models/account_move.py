from odoo import models, _


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_cert_reviewed(self):
        cert = self.env["construction.certification"].browse(
            self.env.context.get("certification_id")
        )
        if not cert:
            return True
        self.write({"certification_id": cert.id})
        cert.message_post(
            body=_("Factura %s marcada como revisada sin certificar.")
            % ", ".join(self.mapped("name"))
        )
        return True
