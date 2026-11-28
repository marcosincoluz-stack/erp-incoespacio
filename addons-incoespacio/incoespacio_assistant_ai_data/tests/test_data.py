import copy
from unittest.mock import patch

from odoo import fields
from odoo.tests.common import TransactionCase


class TestAIData(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.users = [
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": name,
                    "login": name.lower(),
                    "groups_id": [(6, 0, [cls.env.ref("base.group_user").id])],
                }
            )
            for name in ("Ana", "Luis")
        ]
        cls.atype = cls.env["assistant.alert.type"].create(
            {"name": "Prueba", "code": "prueba_ia", "collector": "_collect_prueba"}
        )
        ana, luis = cls.users
        today = fields.Date.today()
        Alert = cls.env["assistant.alert"]
        cls.alerts = {}
        for user, state, message, record in (
            (ana, "open", "De Ana", ana.partner_id),
            (ana, "open", "Arreglado", luis.partner_id),
            (ana, "resolved", "Ana resuelto", cls.env.company.partner_id),
            (luis, "open", "De Luis", luis.partner_id),
        ):
            cls.alerts[message] = Alert.create(
                {
                    "type_id": cls.atype.id,
                    "user_id": user.id,
                    "res_model": "res.partner",
                    "res_id": record.id,
                    "message": message,
                    "state": state,
                    "first_seen": today,
                    "last_seen": today,
                }
            )

    def setUp(self):
        super().setUp()
        # La regla «de verdad» ahora mismo: qué registros siguen pendientes.
        self.live = self.users[0].partner_id | self.users[1].partner_id
        Type = type(self.env["assistant.alert.type"])
        patcher = patch.object(
            Type, "_collect", lambda atype: [(p, None, "x") for p in self.live]
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _my_alerts(self, user):
        question = self.env["assistant.ai.question"].create(
            {"user_id": user.id, "text": "¿Qué avisos tengo?"}
        )
        reply = question._run_tool(question._tools(), "mis_avisos", {})
        return [row["message"] for row in reply["result"]["filas"]]

    def test_fixed_alert_disappears_without_waiting_for_the_cron(self):
        self.assertEqual(
            sorted(self._my_alerts(self.users[0])), ["Arreglado", "De Ana"]
        )
        # Ana arregla lo de Luis: la regla ya no lo ve, aunque el aviso siga
        # abierto en la base hasta la próxima revisión.
        self.live = self.users[0].partner_id
        self.assertEqual(self._my_alerts(self.users[0]), ["De Ana"])
        self.assertEqual(self.alerts["Arreglado"].state, "open")

    def test_broken_rule_keeps_the_alerts(self):
        Type = type(self.env["assistant.alert.type"])
        with patch.object(Type, "_collect", side_effect=RuntimeError("boom")):
            mine = self._my_alerts(self.users[0])
        self.assertEqual(sorted(mine), ["Arreglado", "De Ana"])

    def test_my_alerts_are_only_mine_and_open(self):
        question = self.env["assistant.ai.question"].create(
            {"user_id": self.users[0].id, "text": "¿Qué avisos tengo?"}
        )
        reply = question._run_tool(question._tools(), "mis_avisos", {})
        rows = reply["result"]["filas"]
        self.assertEqual(
            sorted(row["message"] for row in rows), ["Arreglado", "De Ana"]
        )
        self.assertEqual(rows[0]["dias"], 0)
        self.assertIsInstance(rows[0]["type_id"], str)

    def test_answer_links_the_records_the_tools_returned(self):
        ana = self.users[0]
        bot = self.env.ref("incoespacio_assistant.partner_incobot_assistant")
        channel = self.env["discuss.channel"].with_user(ana).channel_get([bot.id])
        question = self.env["assistant.ai.question"].create(
            {"user_id": ana.id, "text": "¿Qué avisos tengo?", "channel_id": channel.id}
        )
        sent = []
        call = {"functionCall": {"name": "mis_avisos", "args": {}}}
        text = 'Tienes 1 aviso: De Ana. <a href="https://malo">pincha</a>'
        answers = [
            {"candidates": [{"content": {"role": "model", "parts": [call]}}]},
            {"candidates": [{"content": {"role": "model", "parts": [{"text": text}]}}]},
        ]

        def fake(system, contents, tools):
            sent.append(copy.deepcopy(contents))
            return answers.pop(0)

        Alert = type(self.env["assistant.alert"])
        with (
            patch.object(type(question), "_gemini_call", side_effect=fake),
            patch.object(Alert, "_link_message", autospec=True) as linked,
        ):
            question._answer_one()
        self.assertEqual(question.state, "done")
        self.assertNotIn("_link", str(sent[1]))
        # El aviso enlazado queda apuntado en la respuesta, para tacharlo ahí.
        alert = self.alerts["De Ana"]
        _self, alerts, message = linked.call_args.args
        self.assertEqual(alerts, alert)
        self.assertEqual(message, question.reply_message_id)
        body = question.reply_message_id.body
        partner = ana.partner_id.id
        self.assertIn('data-oe-model="res.partner"', body)
        self.assertIn('data-oe-id="%s"' % partner, body)
        chip = 'class="o_incobot_link o_incobot_alert_%s">De Ana</a>' % alert.id
        self.assertIn(chip, body)
        # Lo que escribe la IA nunca se convierte en enlace.
        self.assertNotIn('<a href="https://malo"', body)
        self.assertIn("&lt;a href=", body)

    def test_answer_from_memory_keeps_the_links(self):
        ana = self.users[0]
        bot = self.env.ref("incoespacio_assistant.partner_incobot_assistant")
        channel = self.env["discuss.channel"].with_user(ana).channel_get([bot.id])
        call = {"functionCall": {"name": "mis_avisos", "args": {}}}

        def ask(answers):
            question = self.env["assistant.ai.question"].create(
                {
                    "user_id": ana.id,
                    "text": "¿Qué avisos tengo?",
                    "channel_id": channel.id,
                }
            )
            with patch.object(
                type(question), "_gemini_call", side_effect=lambda *a: answers.pop(0)
            ):
                question._answer_one()
            return question

        text = {
            "candidates": [
                {"content": {"role": "model", "parts": [{"text": "De Ana."}]}}
            ]
        }
        tool = {"candidates": [{"content": {"role": "model", "parts": [call]}}]}
        first = ask([tool, copy.deepcopy(text)])
        self.assertIn("o_incobot_link", first.reply_message_id.body)
        # La segunda no consulta nada (contesta con lo ya hablado): el enlace sale igual.
        second = ask([copy.deepcopy(text)])
        self.assertFalse(second.link_data)
        self.assertIn("o_incobot_link", second.reply_message_id.body)

    def test_links_never_go_inside_html_tags_or_entities(self):
        question = self.env["assistant.ai.question"].create(
            {"user_id": self.users[0].id, "text": "x"}
        )
        body = question._to_html("Obra A & B\nfin")
        links = [["res.partner", 1, ["amp", "br/", "fin"]]]
        html = str(question._linkify(body, links))
        self.assertIn("A &amp; B<br/>", html)
        self.assertEqual(html.count("<a "), 1)
        self.assertIn(">fin</a></p>", html)
