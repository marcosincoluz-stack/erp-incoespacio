from unittest.mock import patch

from odoo.tests.common import TransactionCase


class TestAIQueue(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # IncoBot está apagado si no se enciende (así arranca al instalar).
        cls.env["ir.config_parameter"].sudo().set_param(
            "incoespacio_assistant.enabled", "True"
        )
        cls.bot = cls.env.ref("incoespacio_assistant.partner_incobot_assistant")
        cls.user = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Ana Pregunta",
                    "login": "ana.pregunta",
                    "email": "ana.pregunta@example.com",
                    "groups_id": [(6, 0, [cls.env.ref("base.group_user").id])],
                }
            )
        )
        cls.Question = cls.env["assistant.ai.question"]
        cls.channel = (
            cls.env["discuss.channel"].with_user(cls.user).channel_get([cls.bot.id])
        )
        cls._set("enabled", "True")

    @classmethod
    def _set(cls, key, value):
        cls.env["ir.config_parameter"].sudo().set_param(
            "incoespacio_assistant_ai.%s" % key, value
        )

    def _ask(self, text="¿Cómo meto una obra de Presto?"):
        self.channel.with_user(self.user).message_post(
            body=text, message_type="comment", subtype_xmlid="mail.mt_comment"
        )
        return self.Question.search([("user_id", "=", self.user.id)], limit=1)

    def _patch(self, **kwargs):
        return patch.object(type(self.Question), "_ask", autospec=True, **kwargs)

    def _bot_bodies(self):
        messages = self.env["mail.message"].search(
            [
                ("model", "=", "discuss.channel"),
                ("res_id", "=", self.channel.id),
                ("author_id", "=", self.bot.id),
            ]
        )
        return " ".join(messages.mapped("body"))

    def test_question_is_queued_and_answer_replaces_thinking(self):
        question = self._ask()
        self.assertEqual(question.state, "pending")
        self.assertIn("Pensando", question.reply_message_id.body)
        self.assertEqual(question.text, "¿Cómo meto una obra de Presto?")
        usage = {"tokens_in": 120, "tokens_out": 40, "cost": 0.0004}
        answer = "<script>alert(1)</script> Ventas → BC3 → Importar BC3"
        with self._patch(return_value=(answer, usage)):
            self.Question._cron_answer()
        self.assertEqual(question.state, "done")
        self.assertEqual(question.tokens_in, 120)
        self.assertAlmostEqual(question.cost, 0.0004)
        body = question.reply_message_id.body
        # La respuesta reemplaza al «Pensando…» y llega escapada.
        self.assertNotIn("Pensando", body)
        self.assertNotIn("<script>", body)
        self.assertIn("&lt;script&gt;", body)
        self.assertIn("Importar BC3", body)

    def test_switch_off_refuses_without_calling_the_model(self):
        self._set("enabled", "False")
        with self._patch() as ask:
            question = self._ask()
            self.Question._cron_answer()
        ask.assert_not_called()
        self.assertEqual(question.state, "refused")
        self.assertIn("desactivadas", self._bot_bodies())

    def test_daily_limit_and_one_question_at_a_time(self):
        self._set("daily_limit", "2")
        first = self._ask("Primera")
        second = self._ask("Segunda")
        self.assertEqual(first.state, "pending")
        self.assertEqual(second.state, "refused")
        self.assertIn("pregunta anterior", second.answer)
        with self._patch(return_value=("ok", {})):
            self.Question._cron_answer()
            self.assertEqual(self._ask("Tercera").state, "pending")
            self.Question._cron_answer()
        with self._patch() as ask:
            last = self._ask("Cuarta")
            self.Question._cron_answer()
        ask.assert_not_called()
        self.assertEqual(last.state, "refused")
        self.assertIn("límite de preguntas de hoy", last.answer)

    def test_monthly_budget_stops_everyone(self):
        self._set("monthly_budget", "1")
        self.Question.create(
            {"user_id": self.env.user.id, "state": "done", "cost": 1.2, "text": "x"}
        )
        question = self._ask()
        self.assertEqual(question.state, "refused")
        self.assertIn("gasto máximo del mes", question.answer)

    def test_long_question_is_refused(self):
        question = self._ask("a" * 1001)
        self.assertEqual(question.state, "refused")
        self.assertIn("demasiado larga", question.answer)

    def test_model_failure_answers_sorry(self):
        question = self._ask()
        with self._patch(side_effect=RuntimeError("caído")):
            self.Question._cron_answer()
        self.assertEqual(question.state, "error")
        self.assertIn("caído", question.error)
        self.assertIn("No he podido contestar", question.reply_message_id.body)

    def test_bot_posts_and_other_chats_are_ignored(self):
        self.Question._post(self.channel, "Aviso del bot")
        group = self.env["discuss.channel"].create(
            {"name": "Obra", "channel_type": "channel"}
        )
        group.add_members(self.user.partner_id.ids)
        group.with_user(self.user).message_post(
            body="Hola", message_type="comment", subtype_xmlid="mail.mt_comment"
        )
        self.assertFalse(self.Question.search([("user_id", "=", self.user.id)]))

    def test_alert_footer_follows_the_switch(self):
        alerts = self.env["assistant.alert"]
        self.assertIn("preguntarme", alerts._chat_footer())
        self._set("enabled", "False")
        self.assertIn("no responde mensajes", alerts._chat_footer())

    def test_browser_gets_the_question_before_thinking(self):
        # El chat pinta los mensajes en el orden en que le llegan: si el
        # «Pensando…» llegara antes, saldría encima de la pregunta.
        order = []
        Bus = type(self.env["bus.bus"])
        original = Bus._sendone

        def spy(bus, target, notification_type, message):
            if notification_type == "discuss.channel/new_message":
                order.append(message["message"]["id"])
            return original(bus, target, notification_type, message)

        with patch.object(Bus, "_sendone", spy):
            question = self._ask()
        user_message = self.env["mail.message"].search(
            [
                ("res_id", "=", self.channel.id),
                ("author_id", "=", self.user.partner_id.id),
            ],
            limit=1,
        )
        self.assertEqual(order, [user_message.id, question.reply_message_id.id])

    def test_switched_off_incobot_does_not_answer(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "incoespacio_assistant.enabled", False
        )
        question = self.env["assistant.ai.question"]._refusal(self.user, "hola")
        self.assertEqual(question, "IncoBot está desactivado ahora mismo.")
