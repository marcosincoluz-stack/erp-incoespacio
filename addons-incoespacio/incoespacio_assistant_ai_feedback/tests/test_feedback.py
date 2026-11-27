from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase


class TestFeedback(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        group = cls.env.ref("base.group_user").id
        cls.ana, cls.luis = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create({"name": name, "login": login, "groups_id": [(6, 0, [group])]})
            for name, login in (("Ana", "ana.valora"), ("Luis", "luis.valora"))
        )
        bot = cls.env.ref("incoespacio_assistant.partner_incobot_assistant")
        cls.channel = (
            cls.env["discuss.channel"].with_user(cls.ana).channel_get([bot.id])
        )

    def _answer(self, text, fail=False):
        question = self.env["assistant.ai.question"].create(
            {"user_id": self.ana.id, "text": "¿Algo?", "channel_id": self.channel.id}
        )
        reply = {"candidates": [{"content": {"parts": [{"text": text}]}}]}
        effect = RuntimeError("caído") if fail else [reply]
        with patch.object(type(question), "_gemini_call", side_effect=effect):
            question._answer_one()
        return question

    def test_answers_it_cannot_give_are_kept_for_later(self):
        data = self._answer("Lo siento, eso no lo puedo consultar todavía.")
        wiki = self._answer("Eso aún no está en la wiki.")
        fine = self._answer("Tienes 2 avisos.")
        self.assertEqual(data.gap, "data")
        self.assertEqual(wiki.gap, "wiki")
        self.assertFalse(fine.gap)

    def test_each_answer_brings_its_rating_buttons(self):
        question = self._answer("Tienes 2 avisos.")
        body = str(question.reply_message_id.body)
        tag = "o_incobot_q_%s" % question.id
        self.assertIn("Tienes 2 avisos.", body)
        self.assertIn('o_incobot_rate_up %s"' % tag, body)
        self.assertIn('o_incobot_rate_down %s"' % tag, body)
        self.assertIn('class="fa fa-thumbs-o-up"', body)
        # Un fallo no se valora: no lleva botones.
        failed = self._answer("", fail=True)
        self.assertEqual(failed.state, "error")
        self.assertNotIn("o_incobot_rating", str(failed.reply_message_id.body))

    def test_rating_paints_the_chosen_icon_and_toggles(self):
        question = self._answer("Tienes 2 avisos.")
        Question = self.env["assistant.ai.question"].with_user(self.ana)
        self.assertEqual(Question.rate(question.id, "down"), "down")
        body = str(question.reply_message_id.body)
        self.assertIn(
            "o_incobot_rate_down o_incobot_q_%s o_incobot_rated" % question.id, body
        )
        self.assertIn('class="fa fa-thumbs-down"', body)
        self.assertIn('class="fa fa-thumbs-o-up"', body)
        # Cambia de opinión y luego lo quita pulsando otra vez.
        Question.rate(question.id, "up")
        self.assertEqual(question.rating, "up")
        self.assertIn(
            'class="fa fa-thumbs-o-down"', str(question.reply_message_id.body)
        )
        Question.rate(question.id, "up")
        self.assertFalse(question.rating)
        self.assertNotIn("o_incobot_rated", str(question.reply_message_id.body))

    def test_only_who_asked_can_rate(self):
        question = self._answer("Tienes 2 avisos.")
        with self.assertRaises(AccessError):
            self.env["assistant.ai.question"].with_user(self.luis).rate(
                question.id, "up"
            )
        with self.assertRaises(UserError):
            self.env["assistant.ai.question"].with_user(self.ana).rate(
                question.id, "meh"
            )
        self.assertFalse(question.rating)
