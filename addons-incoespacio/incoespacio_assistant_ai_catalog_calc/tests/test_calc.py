from unittest.mock import patch

from odoo.tests.common import TransactionCase

PARTNERS = {
    "model": "res.partner",
    "help": "Contactos de prueba.",
    "domain": [("ref", "=", "calc-test")],
    "order": "name",
    "labels": ["name"],
    "requires": ["ciudad"],
    "fields": {
        "nombre": ("name", "Nombre."),
        "ciudad": ("city", "Ciudad."),
        "color": ("color", "Un número."),
    },
}


class TestCatalogCalc(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Ana Calc",
                    "login": "ana.calc",
                    "groups_id": [(6, 0, [cls.env.ref("base.group_user").id])],
                }
            )
        )
        for name, city, color in (("Uno", "Sevilla", 3), ("Dos", "Sevilla", 4)):
            cls.env["res.partner"].create(
                {"name": name, "city": city, "color": color, "ref": "calc-test"}
            )

    def setUp(self):
        super().setUp()
        Question = type(self.env["assistant.ai.question"])
        patcher = patch.object(Question, "_catalog", lambda q: {"contactos": PARTNERS})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.question = self.env["assistant.ai.question"].create(
            {"user_id": self.user.id, "text": "x"}
        )

    def _ask(self, **args):
        reply = self.question._run_tool(self.question._tools(), "consultar", args)
        return reply.get("result", reply)

    def test_entry_asks_for_its_required_filter(self):
        reply = self._ask(que="contactos")
        self.assertEqual(reply["error"], "Para consultar contactos filtra por ciudad.")
        city = [{"campo": "ciudad", "operador": "=", "valor": "Sevilla"}]
        self.assertEqual(self._ask(que="contactos", filtros=city)["total"], 2)
        # Lo guardado en la base de datos sigue por el camino de siempre.
        totals = self._ask(que="contactos", filtros=city, sumar=["color"])
        self.assertEqual(totals["sumas"], {"color": 7})
