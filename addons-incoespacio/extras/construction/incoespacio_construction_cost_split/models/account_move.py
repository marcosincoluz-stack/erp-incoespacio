from odoo import _, models


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_assign_partida(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Imputar a partidas"),
            "res_model": "construction.cost.assign.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_move_id": self.id},
        }
