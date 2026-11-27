from unittest.mock import patch

from odoo.tests.common import TransactionCase

from odoo.addons.incoespacio_assistant_ai_catalog.tests.gold import (
    assert_never_more_than_the_screen,
)


class TestAIConstruction(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        income = cls.env["account.account"].search(
            [("account_type", "=", "income"), ("company_id", "=", cls.env.company.id)],
            limit=1,
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Partida",
                "type": "service",
                "taxes_id": [(5, 0, 0)],
                "property_account_income_id": income.id if income else False,
            }
        )
        cls.client = cls.env["res.partner"].create({"name": "Promotora Sur"})
        own = cls.env.ref("sales_team.group_sale_salesman")
        projects = cls.env.ref("project.group_project_user")
        cls.pedro = cls._user("Pedro Obras", [own.id, projects.id])
        cls.luis = cls._user("Luis Obras", [own.id, projects.id])
        cls.boss = cls._user(
            "Dirección Obras",
            [cls.env.ref("sales_team.group_sale_manager").id, projects.id],
        )
        cls.north = cls._obra("Colegio Norte", cls.pedro)
        cls.south = cls._obra("Colegio Sur", cls.luis)
        cls.cert = cls.env["construction.certification"].create(
            {"order_id": cls.north.id}
        )

    @classmethod
    def _user(cls, name, groups):
        return (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": name,
                    "login": name.lower().replace(" ", "."),
                    "groups_id": [(6, 0, [cls.env.ref("base.group_user").id] + groups)],
                }
            )
        )

    @classmethod
    def _obra(cls, name, user):
        order = cls.env["sale.order"].create(
            {
                "partner_id": cls.client.id,
                "user_id": user.id,
                "bc3": True,
                "order_line": [
                    (0, 0, {"product_id": cls.product.id, "price_unit": 1000})
                ],
            }
        )
        order.action_confirm()
        order.project_id.name = name
        return order

    def _run(self, user, name, **args):
        question = self.env["assistant.ai.question"].create(
            {"user_id": user.id, "text": "x"}
        )
        return question._run_tool(question._tools(), name, args)

    def test_job_summary_only_shows_what_the_user_can_see(self):
        mine = self._run(self.pedro, "resumen_obra", obra="Colegio")["result"]
        self.assertEqual([row["id"] for row in mine["filas"]], [self.north.id])
        row = mine["filas"][0]
        self.assertEqual(row["project_id"], "Colegio Norte")
        self.assertEqual(row["amount_untaxed"], 1000)
        self.assertEqual(row["ultima_certificacion"]["name"], self.cert.name)
        self.assertEqual(row["facturas_sin_partida"], 0)
        # Sin permiso de compras, el comprometido no se ve, pero el resto sí.
        self.assertEqual(row["amount_job_po"], "sin permiso")
        # Sin Facturación no ve todas las facturas de proveedor: ni coste ni
        # margen (saldrían calculados solo con lo que ve, y engañarían).
        self.assertEqual(row["amount_job_cost"], "sin permiso")
        self.assertEqual(row["amount_job_margin"], "sin permiso")
        everyone = self._run(self.boss, "resumen_obra", obra="Colegio")["result"]
        self.assertEqual(
            {row["id"] for row in everyone["filas"]}, {self.north.id, self.south.id}
        )

    def test_certifications_filter_and_validate(self):
        def ask(*filters):
            return self._run(
                self.boss,
                "consultar",
                que="certificaciones",
                filtros=[
                    {"campo": c, "operador": o, "valor": v} for c, o, v in filters
                ],
            )

        result = ask(("obra", "contiene", "Norte"))["result"]
        self.assertEqual([row["id"] for row in result["filas"]], [self.cert.id])
        self.assertEqual(result["filas"][0]["estado"], "Borrador")
        self.assertEqual(ask(("estado", "=", "invoiced"))["result"]["total"], 0)
        self.assertIn("error", ask(("estado", "=", "x")))
        self.assertIn("error", self._run(self.boss, "resumen_obra", obra=""))

    # ------------------------------------------------------------------ #
    # Catálogo: «consultar» sobre obras
    # ------------------------------------------------------------------ #
    def test_catalog_obras_respect_who_sees_what(self):
        mine = self._run(
            self.pedro, "consultar", que="obras", campos=["obra", "importe", "margen"]
        )["result"]
        # Pedro solo ve su obra, y sin permiso de contabilidad no ve el margen.
        self.assertEqual([row["id"] for row in mine["filas"]], [self.north.id])
        self.assertEqual(mine["filas"][0]["obra"], "Colegio Norte")
        self.assertEqual(mine["filas"][0]["importe"], 1000)
        self.assertEqual(mine["filas"][0]["margen"], "sin permiso")
        boss = self._run(
            self.boss,
            "consultar",
            que="obras",
            filtros=[{"campo": "obra", "operador": "contiene", "valor": "Colegio"}],
            orden="importe",
            descendente=True,
        )["result"]
        self.assertEqual(boss["total"], 2)
        self.assertEqual(
            self._run(
                self.pedro,
                "consultar",
                que="obras",
                filtros=[{"campo": "margen", "operador": ">", "valor": "0"}],
            )["error"][:14],
            "No tienes perm",
        )
        accountant = self._user(
            "Contable Obras",
            [
                self.env.ref("sales_team.group_sale_manager").id,
                self.env.ref("account.group_account_invoice").id,
            ],
        )
        full = self._run(accountant, "consultar", que="obras", campos=["margen"])
        self.assertEqual({row["margen"] for row in full["result"]["filas"]}, {0.0})

    def _bill(self, order, amount):
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.client.id,
                "invoice_date": "2026-11-20",
                "project_id": order.project_id.id,
                "invoice_line_ids": [
                    (0, 0, {"name": "Material", "quantity": 1, "price_unit": amount})
                ],
            }
        )
        bill.action_post()
        return bill

    def test_catalog_sorts_and_filters_by_margin(self):
        # Sin certificar, el margen es menos el coste: Norte -300, Sur -100.
        self._bill(self.north, 300)
        self._bill(self.south, 100)
        accountant = self._user(
            "Contable Margen",
            [
                self.env.ref("sales_team.group_sale_manager").id,
                self.env.ref("account.group_account_invoice").id,
            ],
        )
        best = self._run(
            accountant,
            "consultar",
            que="obras",
            campos=["obra", "margen"],
            orden="margen",
            descendente=True,
        )["result"]
        self.assertEqual(
            [(row["obra"], row["margen"]) for row in best["filas"]],
            [("Colegio Sur", -100), ("Colegio Norte", -300)],
        )
        losing = self._run(
            accountant,
            "consultar",
            que="obras",
            filtros=[{"campo": "margen", "operador": "<", "valor": "-200"}],
        )["result"]
        self.assertEqual([row["id"] for row in losing["filas"]], [self.north.id])
        self.assertEqual(losing["total"], 1)
        # Sin Facturación no se puede ordenar por el margen.
        self.assertIn(
            "error", self._run(self.boss, "consultar", que="obras", orden="margen")
        )

    def test_catalog_scan_has_a_cap(self):
        from odoo.addons.incoespacio_assistant_ai_catalog.models import question_more

        accountant = self._user(
            "Contable Tope",
            [
                self.env.ref("sales_team.group_sale_manager").id,
                self.env.ref("account.group_account_invoice").id,
            ],
        )
        with patch.object(question_more, "SCAN", 1):
            reply = self._run(accountant, "consultar", que="obras", orden="margen")
        self.assertIn("filtra", reply["error"])

    def test_catalog_gold_never_more_than_the_screen(self):
        buyer = self._user(
            "Compras Obras",
            [
                self.env.ref("sales_team.group_sale_manager").id,
                self.env.ref("purchase.group_purchase_user").id,
                self.env.ref("project.group_project_user").id,
            ],
        )
        self.env["purchase.order"].create(
            {"partner_id": self.client.id, "project_id": self.north.project_id.id}
        )
        assert_never_more_than_the_screen(self, [self.pedro, self.boss, buyer])
        # Con permiso de compras ve los pedidos; sin él, no.
        reply = self._run(buyer, "consultar", que="compras", campos=["obra"])
        self.assertEqual(reply["result"]["filas"][0]["obra"], "Colegio Norte")
        self.assertIn("error", self._run(self.pedro, "consultar", que="compras"))

    def test_catalog_certifications_and_projects(self):
        reply = self._run(self.pedro, "consultar", que="certificaciones")["result"]
        self.assertEqual([row["id"] for row in reply["filas"]], [self.cert.id])
        self.assertEqual(reply["filas"][0]["obra"], "Colegio Norte")
        projects = self._run(
            self.boss,
            "consultar",
            que="proyectos",
            filtros=[{"campo": "nombre", "operador": "contiene", "valor": "Colegio"}],
        )["result"]
        self.assertEqual(projects["total"], 2)

    def test_catalog_sums_certified_although_it_is_computed(self):
        # «Lo facturado» de una obra es un dato calculado: ahora se suma igual
        # (incoespacio_assistant_ai_catalog_calc).
        reply = self._run(
            self.boss, "consultar", que="obras", agrupar="obra", sumar=["certificado"]
        )["result"]
        self.assertEqual(reply["total"], 2)
        self.assertEqual({g["certificado"] for g in reply["grupos"]}, {0.0})

    # ------------------------------------------------------------------ #
    # Partidas (docs/asistente-ia-margenes.md, sprint 2)
    # ------------------------------------------------------------------ #
    def _obra_con_capitulos(self):
        def line(name, qty=0, price=0, section=False):
            vals = {"name": name, "sequence": len(lines) + 1}
            if section:
                vals["display_type"] = "line_section"
            else:
                vals.update(
                    product_id=self.product.id, product_uom_qty=qty, price_unit=price
                )
            lines.append((0, 0, vals))

        lines = []
        line("Capítulo A", section=True)
        line("Tabique", 10, 100)
        line("Techo", 10, 50)
        line("Capítulo B", section=True)
        line("Pintura", 10, 20)
        order = self.env["sale.order"].create(
            {
                "partner_id": self.client.id,
                "user_id": self.pedro.id,
                "bc3": True,
                "planned_percent": 20.0,
                "order_line": lines,
            }
        )
        order.action_confirm()
        order.project_id.name = "Nave Capítulos"
        partidas = order.order_line.filtered(lambda l: not l.display_type)
        action = order.action_create_certification()
        cert = self.env["construction.certification"].browse(action["res_id"])
        for cline in cert.line_ids.filtered(lambda l: not l.display_type):
            # Tabique y techo al 50 %; la pintura sin empezar.
            if cline.sale_order_line_id.name != "Pintura":
                cline.qty_origin = 5
        cert.action_confirm()
        cert.action_create_invoice()
        tabique, techo, pintura = partidas
        # Objetivo ejecutado: tabique 5 × 80 = 400, techo 5 × 40 = 200.
        for partida, amount in ((tabique, 600), (techo, 150), (pintura, 90)):
            bill = self._bill(order, amount)
            bill.button_draft()
            bill.invoice_line_ids.construction_line_id = partida
            bill.action_post()
        return order, partidas

    def _accountant(self):
        return self._user(
            "Contable Partidas",
            [
                self.env.ref("sales_team.group_sale_manager").id,
                self.env.ref("account.group_account_invoice").id,
            ],
        )

    def test_partidas_need_a_filter(self):
        reply = self._run(self._accountant(), "consultar", que="partidas")
        self.assertIn("filtra por obra", reply["error"])

    def test_partidas_by_chapter_and_worst_first(self):
        self._obra_con_capitulos()
        accountant = self._accountant()
        obra = [{"campo": "obra", "operador": "contiene", "valor": "Nave Capítulos"}]
        grouped = self._run(
            accountant,
            "consultar",
            que="partidas",
            filtros=obra,
            agrupar="capitulo",
            sumar=["coste", "desviacion", "adelantado"],
        )["result"]

        def by_chapter(name):
            found = [g for g in grouped["grupos"] if g["capitulo"] == name]
            self.assertTrue(found, grouped["grupos"])
            return found[0]

        # A: coste 600 + 150, desviación (400 − 600) + (200 − 150) = −150.
        self.assertAlmostEqual(by_chapter("Capítulo A")["coste"], 750)
        self.assertAlmostEqual(by_chapter("Capítulo A")["desviacion"], -150)
        # B: la pintura, sin empezar, es coste adelantado, no desviación.
        self.assertAlmostEqual(by_chapter("Capítulo B")["desviacion"], 0)
        self.assertAlmostEqual(by_chapter("Capítulo B")["adelantado"], 90)
        worst = self._run(
            accountant,
            "consultar",
            que="partidas",
            filtros=obra,
            campos=["descripcion", "desviacion"],
            orden="desviacion",
            descendente=False,
            limite=1,
        )["result"]
        self.assertEqual(worst["filas"][0]["descripcion"], "Tabique")
        self.assertAlmostEqual(worst["filas"][0]["desviacion"], -200)

    def test_partidas_costs_only_with_billing(self):
        self._obra_con_capitulos()
        obra = [{"campo": "obra", "operador": "contiene", "valor": "Nave Capítulos"}]
        rows = self._run(
            self.pedro,
            "consultar",
            que="partidas",
            filtros=obra,
            campos=["descripcion", "venta", "coste"],
        )["result"]["filas"]
        self.assertEqual({r["coste"] for r in rows}, {"sin permiso"})
        self.assertEqual(sorted(r["venta"] for r in rows), [200, 500, 1000])
        reply = self._run(
            self.pedro,
            "consultar",
            que="partidas",
            filtros=obra,
            agrupar="capitulo",
            sumar=["coste"],
        )
        self.assertIn("permiso", reply["error"])
