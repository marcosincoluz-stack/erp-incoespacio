from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    construction_not_job = fields.Boolean(
        string="Excluida de obra",
        copy=False,
        help="Factura de proveedor que no se imputa a una obra.",
    )
    has_unassigned_partida = fields.Boolean(
        compute="_compute_has_unassigned_partida",
        search="_search_has_unassigned_partida",
    )

    @api.depends("invoice_line_ids.construction_line_id", "invoice_line_ids.display_type")
    def _compute_has_unassigned_partida(self):
        for move in self:
            move.has_unassigned_partida = any(
                line.display_type == "product" and not line.construction_line_id
                for line in move.invoice_line_ids
            )

    @api.model
    def _search_has_unassigned_partida(self, operator, value):
        if operator not in ("=", "!="):
            return [("id", "=", False)]
        wanted = (operator == "=" and value) or (operator == "!=" and not value)
        moves = (
            self.env["account.move.line"]
            .search(
                [
                    ("display_type", "=", "product"),
                    ("construction_line_id", "=", False),
                    ("move_id.move_type", "in", ("in_invoice", "in_refund")),
                ]
            )
            .move_id
        )
        return [("id", "in" if wanted else "not in", moves.ids)]

    def action_post(self):
        for move in self:
            if (
                move.move_type in ("in_invoice", "in_refund")
                and not move.project_id
                and not move.construction_not_job
            ):
                raise UserError(
                    _("Elige la obra o marca «No es de obra» antes de publicar.")
                )
        return super().action_post()
