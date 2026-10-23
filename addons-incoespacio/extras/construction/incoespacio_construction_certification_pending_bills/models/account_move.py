from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    certification_id = fields.Many2one(
        "construction.certification",
        string="Cubierta en certificación",
        copy=False,
        index=True,
        ondelete="set null",
    )

    def write(self, vals):
        if "project_id" in vals and "certification_id" not in vals:
            vals["certification_id"] = False
        return super().write(vals)
