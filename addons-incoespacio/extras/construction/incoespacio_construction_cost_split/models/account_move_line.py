from odoo import _, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def action_split_partida(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Repartir entre partidas"),
            "res_model": "construction.cost.split.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_line_id": self.id},
        }
