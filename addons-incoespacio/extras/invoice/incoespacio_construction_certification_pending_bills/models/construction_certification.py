from odoo import api, fields, models, _


class ConstructionCertification(models.Model):
    _inherit = "construction.certification"

    pending_bill_ids = fields.Many2many(
        "account.move",
        compute="_compute_pending_bills",
        string="Facturas sin certificar",
    )
    pending_bill_count = fields.Integer(compute="_compute_pending_bills")
    pending_bill_amount = fields.Monetary(
        compute="_compute_pending_bills",
        currency_field="currency_id",
        string="Importe sin certificar",
    )

    def _pending_bill_domain(self):
        self.ensure_one()
        if not self.project_id or not self.date:
            return [("id", "=", False)]
        return [
            ("project_id", "=", self.project_id.id),
            ("company_id", "=", self.company_id.id),
            ("move_type", "in", ("in_invoice", "in_refund")),
            ("state", "=", "posted"),
            ("certification_id", "=", False),
            ("invoice_date", "<=", self.date),
        ]

    @api.depends("project_id", "date", "state")
    def _compute_pending_bills(self):
        Move = self.env["account.move"]
        for cert in self:
            bills = (
                Move.search(cert._pending_bill_domain())
                if cert.project_id and cert.date
                else Move
            )
            amount = sum(
                bill.amount_untaxed
                if bill.move_type == "in_invoice"
                else -bill.amount_untaxed
                for bill in bills
            )
            cert.pending_bill_ids = bills
            cert.pending_bill_count = len(bills)
            cert.pending_bill_amount = amount

    def action_confirm(self):
        self.ensure_one()
        bills = self.env["account.move"].search(self._pending_bill_domain())
        res = super().action_confirm()
        if bills:
            bills.write({"certification_id": self.id})
            self.message_post(
                body=_(
                    "Facturas de proveedor cubiertas: %s"
                )
                % ", ".join(bills.mapped("name"))
            )
        return res

    def action_draft(self):
        res = super().action_draft()
        self.env["account.move"].search(
            [("certification_id", "in", self.ids)]
        ).write({"certification_id": False})
        return res

    def action_cancel(self):
        res = super().action_cancel()
        self.env["account.move"].search(
            [("certification_id", "in", self.ids)]
        ).write({"certification_id": False})
        return res

    def action_view_pending_bills(self):
        self.ensure_one()
        return {
            "name": _("Facturas sin certificar"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "tree,form",
            "domain": self._pending_bill_domain(),
        }
