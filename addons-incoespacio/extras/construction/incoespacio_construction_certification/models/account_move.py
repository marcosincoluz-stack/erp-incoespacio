from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    project_id = fields.Many2one("project.project", string="Proyecto / Obra", copy=True)
    construction_order_id = fields.Many2one(
        "sale.order",
        string="Obra",
        compute="_compute_construction_order_id",
        store=True,
        index=True,
    )
    retention_order_id = fields.Many2one(
        "sale.order",
        string="Pedido (devolución retención)",
        copy=False,
        ondelete="set null",
    )

    @api.depends("project_id", "retention_order_id", "invoice_line_ids.sale_line_ids.order_id")
    def _compute_construction_order_id(self):
        by_project = {}
        projects = self.mapped("project_id")
        if projects:
            for order in self.env["sale.order"].search(
                [("project_id", "in", projects.ids), ("state", "in", ("sale", "done"))]
            ):
                by_project.setdefault(order.project_id.id, order)
        for move in self:
            if move.retention_order_id:
                move.construction_order_id = move.retention_order_id
            elif move.project_id:
                move.construction_order_id = by_project.get(move.project_id.id, False)
            else:
                move.construction_order_id = move.invoice_line_ids.sale_line_ids.order_id[:1]
