from odoo import api, fields, models

_PARAM = "incoespacio_assistant.summary_role_ids"


class ResUsers(models.Model):
    _inherit = "res.users"

    assistant_summary = fields.Boolean(compute="_compute_assistant_summary")

    @api.depends_context("uid")
    def _compute_assistant_summary(self):
        summary_users = self.env["assistant.alert"]._summary_users()
        system = self.env.ref("base.group_system")
        for user in self:
            user.assistant_summary = user in summary_users or system in user.groups_id


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    summary_role_ids = fields.Many2many(
        "res.users.role",
        string="Roles que reciben el resumen",
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        roles = self.env["assistant.alert"]._summary_roles()
        res["summary_role_ids"] = [(6, 0, roles.ids)]
        return res

    def set_values(self):
        super().set_values()
        value = ",".join(str(role.id) for role in self.summary_role_ids)
        self.env["ir.config_parameter"].sudo().set_param(_PARAM, value)
        return True
