from odoo import fields, models


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    construction_line_id = fields.Many2one(
        "sale.order.line",
        string="Partida de obra",
        domain="[('display_type', '=', False)]",
        ondelete="set null",
    )

    def _prepare_account_move_line(self, move=False):
        res = super()._prepare_account_move_line(move=move)
        if self.construction_line_id:
            res["construction_line_id"] = self.construction_line_id.id
        return res
