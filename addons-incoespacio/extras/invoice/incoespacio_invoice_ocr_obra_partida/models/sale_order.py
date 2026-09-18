from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_view_gastos_sin_partida(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "incoespacio_invoice_ocr_obra_partida.action_gastos_sin_partida"
        )
        action["domain"] = [
            ("move_type", "in", ("in_invoice", "in_refund")),
            ("state", "=", "posted"),
            ("project_id", "=", self.project_id.id),
            ("has_unassigned_partida", "=", True),
        ]
        action["context"] = {
            "search_default_gastos_sin_partida": 1,
            "default_project_id": self.project_id.id,
        }
        return action
