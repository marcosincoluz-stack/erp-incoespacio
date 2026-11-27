from odoo import api, models


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    @api.returns("mail.message", lambda value: value.id)
    def message_post(self, **kwargs):
        # Después de super(), no en _message_post_after_hook: ese gancho corre
        # antes de avisar al navegador del mensaje del usuario, y el «Pensando…»
        # le llegaba primero y salía encima de la pregunta.
        message = super().message_post(**kwargs)
        user = self.env.user
        if self._is_ai_question(message, user):
            # sudo: la cola solo la leen los administradores; el usuario no la ve.
            self.env["assistant.ai.question"].sudo()._receive(self, message, user)
        return message

    def _is_ai_question(self, message, user):
        if len(self) != 1 or self.channel_type != "chat":
            return False
        if message.message_type != "comment" or user.share or user._is_public():
            return False
        bot = self.env.ref(
            "incoespacio_assistant.partner_incobot_assistant", raise_if_not_found=False
        )
        if not bot or message.author_id != user.partner_id:
            return False
        members = self.sudo().channel_member_ids.partner_id
        return members == (bot | user.partner_id)
