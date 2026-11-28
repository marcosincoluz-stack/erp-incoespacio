from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    assistant_muted_type_ids = fields.Many2many(
        "assistant.alert.type",
        string="Avisos silenciados",
    )

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ["assistant_muted_type_ids"]

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ["assistant_muted_type_ids"]
