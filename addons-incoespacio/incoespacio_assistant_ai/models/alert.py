from odoo import _, models


class AssistantAlert(models.Model):
    _inherit = "assistant.alert"

    def _chat_footer(self):
        if self.env["assistant.ai.question"]._param_bool("enabled"):
            return _("Puedes preguntarme aquí cómo se hace algo o consultar datos.")
        return super()._chat_footer()
