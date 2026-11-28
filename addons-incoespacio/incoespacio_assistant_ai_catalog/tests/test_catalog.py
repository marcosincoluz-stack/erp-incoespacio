from unittest.mock import patch

from odoo.tests.common import TransactionCase

from odoo.addons.incoespacio_assistant_ai_catalog.models.question import CatalogError

PARTNERS = {
    "model": "res.partner",
    "help": "Contactos de prueba.",
    "domain": [("ref", "=", "catalogo-test")],
    "order": "name",
    "labels": ["name"],
    "fields": {
        "nombre": ("name", "Nombre."),
        "ciudad": ("city", "Ciudad."),
        "es_empresa": ("is_company", "Si es una empresa."),
        "tipo": ("type", "Tipo de contacto."),
        "color": ("color", "Un número."),
        "matriz": ("parent_id", "Empresa a la que pertenece."),
        "nombre_visible": ("display_name", "Calculado: no se puede ordenar."),
    },
}


class TestCatalog(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Ana Catálogo",
                    "login": "ana.catalogo",
                    "groups_id": [(6, 0, [cls.env.ref("base.group_user").id])],
                }
            )
        )
        Partner = cls.env["res.partner"]
        cls.big = Partner.create(
            {
                "name": "Grande SL",
                "city": "Sevilla",
                "is_company": True,
                "color": 7,
                "ref": "catalogo-test",
            }
        )
        cls.small = Partner.create(
            {
                "name": "Pequeña SL",
                "city": "Cádiz",
                "is_company": True,
                "color": 2,
                "ref": "catalogo-test",
            }
        )
        cls.person = Partner.create(
            {
                "name": "Luisa",
                "parent_id": cls.big.id,
                "type": "invoice",
                "color": 0,
                "ref": "catalogo-test",
            }
        )
        Partner.create({"name": "Fuera del catálogo", "city": "Sevilla"})

    def setUp(self):
        super().setUp()
        self.entries = {"contactos": PARTNERS}
        Question = type(self.env["assistant.ai.question"])
        patcher = patch.object(Question, "_catalog", lambda q: dict(self.entries))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.question = self.env["assistant.ai.question"].create(
            {"user_id": self.user.id, "text": "x"}
        )

    def _ask(self, **args):
        reply = self.question._run_tool(self.question._tools(), "consultar", args)
        return reply.get("result", reply)

    def _names(self, reply):
        return [row["nombre"] for row in reply["filas"]]

    def test_filters_order_and_limit(self):
        reply = self._ask(
            que="contactos",
            filtros=[{"campo": "ciudad", "operador": "=", "valor": "Sevilla"}],
        )
        # La base fija del catálogo se aplica siempre.
        self.assertEqual(self._names(reply), ["Grande SL"])
        reply = self._ask(
            que="contactos",
            orden="color",
            descendente=True,
            campos=["nombre", "color"],
            limite=2,
        )
        self.assertEqual(self._names(reply), ["Grande SL", "Pequeña SL"])
        self.assertEqual(reply["total"], 3)
        self.assertEqual(set(reply["filas"][0]), {"id", "_link", "nombre", "color"})
        reply = self._ask(
            que="contactos",
            filtros=[
                {"campo": "color", "operador": ">=", "valor": "2,0"},
                {"campo": "es_empresa", "operador": "=", "valor": "sí"},
                {"campo": "matriz", "operador": "vacio", "valor": "si"},
            ],
        )
        self.assertEqual(sorted(self._names(reply)), ["Grande SL", "Pequeña SL"])
        reply = self._ask(
            que="contactos",
            filtros=[{"campo": "matriz", "operador": "contiene", "valor": "grande"}],
        )
        self.assertEqual(self._names(reply), ["Luisa"])
        self.assertEqual(reply["filas"][0]["matriz"], "Grande SL")

    def test_options_by_key_or_label(self):
        label = dict(
            self.env["res.partner"]._fields["type"]._description_selection(self.env)
        )["invoice"]
        for value in ("invoice", label.upper()):
            reply = self._ask(
                que="contactos",
                filtros=[{"campo": "tipo", "operador": "=", "valor": value}],
            )
            self.assertEqual(self._names(reply), ["Luisa"])
        reply = self._ask(
            que="contactos",
            filtros=[{"campo": "tipo", "operador": "en", "valor": "invoice, contact"}],
        )
        self.assertEqual(reply["total"], 3)

    def test_anything_outside_the_catalog_is_refused(self):
        cases = [
            dict(que="usuarios"),
            dict(que="contactos", campos=["vat"]),
            dict(que="contactos", orden="nombre_visible"),
            dict(
                que="contactos",
                filtros=[{"campo": "vat", "operador": "=", "valor": "x"}],
            ),
            dict(
                que="contactos",
                filtros=[{"campo": "ciudad", "operador": ">", "valor": "a"}],
            ),
            dict(
                que="contactos",
                filtros=[{"campo": "color", "operador": "=", "valor": "mucho"}],
            ),
            dict(
                que="contactos",
                filtros=[{"campo": "tipo", "operador": "=", "valor": "jefe"}],
            ),
            dict(que="contactos", filtros=["('id', '>', 0)"]),
        ]
        for args in cases:
            reply = self._ask(**args)
            self.assertIn("error", reply, args)
        # Lo de fuera de la base fija nunca sale, ni pidiéndolo por nombre.
        reply = self._ask(
            que="contactos",
            filtros=[{"campo": "nombre", "operador": "contiene", "valor": "Fuera"}],
        )
        self.assertEqual(reply["total"], 0)

    def test_limit_is_capped(self):
        reply = self._ask(que="contactos", limite=500)
        self.assertEqual(len(reply["filas"]), 3)
        reply = self._ask(que="contactos", limite="muchas")
        self.assertEqual(len(reply["filas"]), 3)

    def test_catalog_never_reaches_blocked_things(self):
        self.entries = {"usuarios": dict(PARTNERS, model="res.users")}
        with self.assertRaises(CatalogError):
            self.question._tools()
        self.entries = {"contactos": dict(PARTNERS, fields={"nif": ("vat", "x")})}
        with self.assertRaises(CatalogError):
            self.question._tools()

    def test_spec_lists_fields_and_options_for_the_ai(self):
        spec = self.question._tools()["consultar"][0]
        self.assertEqual(spec["parameters"]["properties"]["que"]["enum"], ["contactos"])
        self.assertIn("ciudad [texto]: Ciudad.", spec["description"])
        self.assertIn("invoice (", spec["description"])

    def test_runs_as_the_user_and_links_records(self):
        seen = {}
        original = type(self.question)._rows

        def spy(question, env, *args, **kwargs):
            seen.update(uid=env.uid, su=env.su)
            return original(question, env, *args, **kwargs)

        with patch.object(type(self.question), "_rows", spy):
            reply = self._ask(que="contactos", campos=["ciudad"])
        self.assertEqual(seen, {"uid": self.user.id, "su": False})
        row = reply["filas"][0]
        self.assertEqual(row["_link"][:2], ["res.partner", row["id"]])
        self.assertNotIn("nombre", row)

    # ------------------------------------------------------------------ #
    # Sprint 2: agrupar y sumar
    # ------------------------------------------------------------------ #
    def test_group_and_sum(self):
        reply = self._ask(que="contactos", agrupar="ciudad", sumar=["color"])
        self.assertEqual(reply["total"], 3)
        self.assertEqual(
            reply["grupos"],
            [
                {"ciudad": "Sevilla", "cantidad": 1, "color": 7},
                {"ciudad": "Cádiz", "cantidad": 1, "color": 2},
                {"ciudad": "(sin ciudad)", "cantidad": 1, "color": 0},
            ],
        )
        reply = self._ask(
            que="contactos",
            agrupar="es_empresa",
            filtros=[{"campo": "color", "operador": ">", "valor": "0"}],
        )
        self.assertEqual(reply["grupos"], [{"es_empresa": "sí", "cantidad": 2}])

    def test_group_refuses_what_makes_no_sense(self):
        for args in (
            dict(que="contactos", agrupar="nombre_visible"),
            dict(que="contactos", agrupar="ciudad", sumar=["nombre"]),
            dict(que="contactos", agrupar="vat"),
        ):
            self.assertIn("error", self._ask(**args), args)

    def test_sum_without_grouping_gives_the_totals(self):
        reply = self._ask(
            que="contactos",
            sumar=["color"],
            filtros=[{"campo": "es_empresa", "operador": "=", "valor": "si"}],
        )
        self.assertEqual(reply, {"que": "contactos", "total": 2, "sumas": {"color": 9}})

    def test_direction_can_come_inside_the_order(self):
        for orden in ("color desc", "-color", "COLOR DESC"):
            reply = self._ask(que="contactos", orden=orden, limite=1)
            self.assertEqual(self._names(reply), ["Grande SL"], orden)
        reply = self._ask(
            que="contactos", orden="color asc", descendente=True, limite=1
        )
        self.assertEqual(self._names(reply), ["Luisa"])

    def test_summing_a_computed_field_explains_how_to_sort_instead(self):
        computed = dict(PARTNERS["fields"], numero_calculado=("partner_share", "x"))
        self.entries = {"contactos": dict(PARTNERS, fields=computed)}
        reply = self._ask(que="contactos", agrupar="ciudad", sumar=["nombre"])
        self.assertIn("no es un número", reply["error"])

    def test_dates_default_to_most_recent_first(self):
        dated = dict(PARTNERS["fields"], alta=("create_date", "Alta."))
        self.entries = {"contactos": dict(PARTNERS, fields=dated)}
        self.env.cr.execute(
            "UPDATE res_partner SET create_date = %s WHERE id = %s",
            ("2020-01-01", self.small.id),
        )
        self.env["res.partner"].invalidate_model(["create_date"])
        newest = self._ask(que="contactos", orden="alta", limite=3)
        self.assertEqual(self._names(newest)[-1], "Pequeña SL")
        oldest = self._ask(que="contactos", orden="alta", descendente=False, limite=1)
        self.assertEqual(self._names(oldest), ["Pequeña SL"])

    def test_equal_on_a_relation_searches_by_name(self):
        reply = self._ask(
            que="contactos",
            filtros=[{"campo": "matriz", "operador": "=", "valor": "Grande SL"}],
        )
        self.assertEqual(self._names(reply), ["Luisa"])
