import copy
from unittest.mock import patch

from odoo.tests.common import TransactionCase

from odoo.addons.incoespacio_assistant_ai.models.question_ai import MAX_ROUNDS


def _text(text, tokens_in=100, tokens_out=20, thoughts=0):
    return {
        "candidates": [{"content": {"role": "model", "parts": [{"text": text}]}}],
        "usageMetadata": {
            "promptTokenCount": tokens_in,
            "candidatesTokenCount": tokens_out,
            "thoughtsTokenCount": thoughts,
        },
    }


def _call(name, args=None):
    part = {"functionCall": {"name": name, "args": args or {}}}
    return {
        "candidates": [{"content": {"role": "model", "parts": [part]}}],
        "usageMetadata": {"promptTokenCount": 50, "candidatesTokenCount": 5},
    }


class TestAIGemini(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Pedro Pregunta",
                    "login": "pedro.pregunta",
                    "groups_id": [(6, 0, [cls.env.ref("base.group_user").id])],
                }
            )
        )
        cls.partner = cls.env["res.partner"].create({"name": "Proveedor intacto"})
        cls.Question = cls.env["assistant.ai.question"]
        cls.question = cls.Question.create(
            {"user_id": cls.user.id, "text": "¿Qué avisos tengo?"}
        )

    def _tools(self, **methods):
        spec = {"description": "x", "parameters": {"type": "object"}}
        tools = {name: (dict(spec, name=name), m) for name, m in methods.items()}
        return patch.object(type(self.Question), "_tools", lambda self: tools)

    def _gemini(self, *responses):
        """Simula Gemini y guarda una copia de lo que se le manda en cada vuelta."""
        self.sent = []
        queue = list(responses)

        def fake(system, contents, tools, last=False):
            self.sent.append(copy.deepcopy(contents))
            self.last = last
            return queue.pop(0)

        return patch.object(type(self.Question), "_gemini_call", side_effect=fake)

    def _tool_reply(self, round_):
        return self.sent[round_][-1]["parts"][0]["functionResponse"]["response"]

    def test_trap_tool_cannot_write(self):
        partner = self.partner

        def orm_write(env):
            env["res.partner"].sudo().browse(partner.id).write({"name": "Hackeado"})
            return "escrito"

        def sql_write(env):
            env.cr.execute(
                "UPDATE res_partner SET name = 'Hackeado' WHERE id = %s", (partner.id,)
            )
            return "escrito"

        with (
            self._tools(orm=orm_write, sql=sql_write),
            self._gemini(_call("orm"), _call("sql"), _text("No he podido.")),
        ):
            text, usage = self.question._ask()
        self.assertEqual(text, "No he podido.")
        for round_ in (1, 2):
            reply = self._tool_reply(round_)
            self.assertIn("error", reply)
            self.assertNotIn("result", reply)
        partner.invalidate_recordset()
        self.assertEqual(partner.name, "Proveedor intacto")
        # Tras la herramienta la base vuelve a admitir escrituras normales.
        partner.write({"name": "Cambio legítimo"})
        partner.flush_recordset()
        self.assertEqual(usage["tokens_in"], 200)

    def test_tool_runs_as_the_user_without_sudo(self):
        seen = {}

        def whoami(env):
            seen.update(uid=env.uid, su=env.su)
            return {"login": env.user.login}

        with self._tools(whoami=whoami), self._gemini(_call("whoami"), _text("Ok")):
            self.question._ask()
        self.assertEqual(seen, {"uid": self.user.id, "su": False})

    def test_usage_and_cost_add_up(self):
        # El precio va con el modelo: 3.8 Flash, a 1,50 / 7,50 € el millón.
        self.env["ir.config_parameter"].sudo().set_param(
            "incoespacio_assistant_ai.model", "gemini-3.8-flash"
        )
        with (
            self._tools(nada=lambda env: []),
            self._gemini(
                _call("nada"),
                _text("Hecho", tokens_in=1000, tokens_out=100, thoughts=50),
            ),
        ):
            text, usage = self.question._ask()
        self.assertEqual(text, "Hecho")
        self.assertEqual(usage["tokens_in"], 1050)
        # Lo que piensa el modelo cuenta como salida.
        self.assertEqual(usage["tokens_out"], 155)
        self.assertAlmostEqual(usage["cost"], (1050 * 1.5 + 155 * 7.5) / 1e6)

    def test_model_is_its_own_and_unknown_prices_count_high(self):
        icp = self.env["ir.config_parameter"].sudo()
        Question = self.env["assistant.ai.question"]
        # Sin elegir: el del OCR. Elegido: el suyo, sin tocar el del OCR.
        icp.set_param("incoespacio_invoice_ocr.gemini_model", "gemini-3.8-flash")
        icp.set_param("incoespacio_assistant_ai.model", "")
        self.assertEqual(Question._model(), "gemini-3.8-flash")
        icp.set_param("incoespacio_assistant_ai.model", "gemini-3.5-flash-lite")
        self.assertEqual(Question._model(), "gemini-3.5-flash-lite")
        self.assertEqual(
            icp.get_param("incoespacio_invoice_ocr.gemini_model"), "gemini-3.8-flash"
        )
        usage = {"tokens_in": 1_000_000, "tokens_out": 1_000_000}
        self.assertAlmostEqual(Question._cost(usage)["cost"], 0.30 + 2.50)
        # «Última versión» no tiene precio fijo: se cuenta al más caro.
        icp.set_param("incoespacio_assistant_ai.model", "gemini-flash-latest")
        self.assertAlmostEqual(Question._cost(usage)["cost"], 1.50 + 7.50)
        # Un modelo que ya no está en la lista vuelve al recomendado.
        icp.set_param("incoespacio_assistant_ai.model", "gemini-2.5-flash")
        self.assertEqual(Question._model(), "gemini-3.5-flash-lite")

    def test_too_many_rounds_and_unknown_tool(self):
        with self._tools(), self._gemini(*[_call("inventada")] * MAX_ROUNDS):
            text, _usage = self.question._ask()
        self.assertIn("demasiadas consultas", text)
        self.assertEqual(len(self.sent), MAX_ROUNDS)
        # En la última vuelta ya no puede pedir más consultas.
        self.assertTrue(self.last)
        self.assertIn("error", self._tool_reply(1))

    def test_missing_key_ends_in_error_state(self):
        channel = (
            self.env["discuss.channel"]
            .with_user(self.user)
            .channel_get(
                [self.env.ref("incoespacio_assistant.partner_incobot_assistant").id]
            )
        )
        self.question.channel_id = channel
        self.env["ir.config_parameter"].sudo().set_param(
            "incoespacio_invoice_ocr.gemini_api_key", ""
        )
        self.question._answer_one()
        self.assertEqual(self.question.state, "error")
        self.assertIn("clave de Gemini", self.question.error)
