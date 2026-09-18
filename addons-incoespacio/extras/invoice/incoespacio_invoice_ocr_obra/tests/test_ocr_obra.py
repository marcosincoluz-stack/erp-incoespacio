from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestOcrObra(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        income = cls.env["account.account"].search(
            [("account_type", "=", "income"), ("company_id", "=", company.id)],
            limit=1,
        )
        expense = cls.env["account.account"].search(
            [("account_type", "=", "expense"), ("company_id", "=", company.id)],
            limit=1,
        )
        cls.partner = cls.env["res.partner"].create(
            {"name": "Subcontrata Pladur", "is_company": True}
        )
        cls.customer = cls.env["res.partner"].create(
            {"name": "Cliente Obra", "is_company": True}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Partida",
                "type": "service",
                "invoice_policy": "order",
                "list_price": 100,
                "taxes_id": [(5, 0, 0)],
                "supplier_taxes_id": [(5, 0, 0)],
                "property_account_income_id": income.id if income else False,
                "property_account_expense_id": expense.id if expense else False,
            }
        )
        cls.order_a, cls.project_a = cls._make_obra("P2600991", "Movimiento de tierras")
        cls.order_b, cls.project_b = cls._make_obra("P2600992", "Tabiques de pladur")

    @classmethod
    def _make_obra(cls, name, chapter):
        order = cls.env["sale.order"].create(
            {
                "partner_id": cls.customer.id,
                "bc3": True,
                "order_line": [
                    (0, 0, {"display_type": "line_section", "name": chapter}),
                    (
                        0,
                        0,
                        {
                            "product_id": cls.product.id,
                            "product_uom_qty": 10,
                            "price_unit": 100,
                            "tax_id": [(6, 0, [])],
                        },
                    ),
                ],
            }
        )
        order.action_confirm()
        order.name = name
        return order, order.project_id

    def _bill(self, project=None, state="posted", lines=None):
        line_vals = lines or [
            (
                0,
                0,
                {
                    "name": "Trabajo",
                    "product_id": self.product.id,
                    "quantity": 1,
                    "price_unit": 50,
                    "tax_ids": [(6, 0, [])],
                },
            )
        ]
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "invoice_date": self.order_a.date_order,
                "project_id": project.id if project else False,
                "invoice_line_ids": line_vals,
            }
        )
        if project:
            bill.ocr_obra_state = "confirmed"
        if state == "posted":
            bill.action_post()
        return bill

    def test_vendor_one_obra_suggests(self):
        self._bill(self.project_a)
        draft = self._bill(state="draft")
        draft._suggest_obra({})
        self.assertFalse(draft.project_id)
        self.assertEqual(draft.ocr_obra_suggested_id, self.project_a)
        self.assertEqual(draft.ocr_obra_state, "suggested")
        draft.action_confirm_obra()
        self.assertEqual(draft.project_id, self.project_a)
        self.assertEqual(draft.ocr_obra_state, "confirmed")

    def test_vendor_two_obras_uses_sticky(self):
        self._bill(self.project_a)
        self._bill(self.project_b)
        draft = self._bill(state="draft")
        draft._suggest_obra({})
        self.assertFalse(draft.project_id)
        self.assertIn(draft.ocr_obra_suggested_id, self.project_a | self.project_b)
        self.assertEqual(draft.ocr_obra_state, "suggested")

    def test_two_obras_no_confirmed_stays_empty(self):
        a = self._bill(self.project_a)
        b = self._bill(self.project_b)
        a.ocr_obra_state = "none"
        b.ocr_obra_state = "none"
        draft = self._bill(state="draft")
        draft._suggest_obra({})
        self.assertFalse(draft.project_id)
        self.assertEqual(draft.ocr_obra_state, "none")

    def test_so_code_bonus(self):
        draft = self._bill(state="draft")
        draft._suggest_obra({"lineas": [{"descripcion": "Certificación marzo %s" % self.order_a.name}]})
        self.assertEqual(draft.project_id, self.project_a)

    def test_chapter_match(self):
        draft = self._bill(
            self.project_b,
            state="draft",
            lines=[
                (
                    0,
                    0,
                    {
                        "name": "Montaje tabiques de pladur en planta 1",
                        "quantity": 1,
                        "price_unit": 80,
                        "tax_ids": [(6, 0, [])],
                    },
                )
            ],
        )
        draft.invoice_line_ids.filtered(lambda l: not l.display_type).write(
            {"name": "Montaje tabiques de pladur en planta 1"}
        )
        draft._suggest_chapters()
        section = self.order_b.order_line.filtered(lambda l: l.display_type == "line_section")
        content = draft.invoice_line_ids.filtered(lambda l: l.display_type == "product")
        self.assertTrue(section, self.order_b.order_line.mapped("name"))
        self.assertTrue(content, draft.invoice_line_ids.mapped("name"))
        self.assertEqual(
            content.construction_section_id,
            section,
            "%s vs %s" % (content.mapped("name"), section.mapped("name")),
        )

    def test_chapter_when_obra_picked_later(self):
        draft = self._bill(
            state="draft",
            lines=[
                (
                    0,
                    0,
                    {
                        "name": "Tabique autoportante de pladur 15+15 sobre estructura",
                        "product_id": self.product.id,
                        "quantity": 1,
                        "price_unit": 80,
                        "tax_ids": [(6, 0, [])],
                    },
                )
            ],
        )
        self.assertFalse(draft.project_id)
        content = draft.invoice_line_ids.filtered(lambda l: l.display_type == "product")
        self.assertFalse(content.construction_section_id)
        draft.project_id = self.project_b
        self.assertEqual(
            content.construction_section_id,
            self.order_b.order_line.filtered(lambda l: l.display_type == "line_section"),
        )

    def test_chapter_matches_uo_under_section(self):
        order, project = self._make_obra("P2600993", "[C04] Tabiqueria y pladur")
        self.env["sale.order.line"].create(
            {
                "order_id": order.id,
                "name": "[UO0401] Tabique de pladur 15+15 sobre estructura- Tabique autoportante",
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "price_unit": 22.8,
                "tax_id": [(6, 0, [])],
            }
        )
        draft = self._bill(
            state="draft",
            lines=[
                (
                    0,
                    0,
                    {
                        "name": "Tabique autoportante de pladur 15+15 sobre estructura, montantes cada 40 cm",
                        "product_id": self.product.id,
                        "quantity": 42,
                        "price_unit": 18.5,
                        "tax_ids": [(6, 0, [])],
                    },
                )
            ],
        )
        draft.project_id = project
        section = order.order_line.filtered(lambda l: l.display_type == "line_section")
        content = draft.invoice_line_ids.filtered(lambda l: l.display_type == "product")
        self.assertEqual(content.construction_section_id, section)

    def test_post_without_obra_blocked(self):
        draft = self._bill(state="draft")
        self.assertFalse(draft.project_id)
        self.assertNotEqual(draft.ocr_obra_state, "skipped")
        with self.assertRaises(UserError):
            draft.action_post()

    def test_post_not_job_skips_margin(self):
        self.order_a.invalidate_recordset(["amount_job_cost"])
        draft = self._bill(state="draft")
        draft.ocr_obra_not_job = True
        draft.action_post()
        self.assertEqual(draft.state, "posted")
        self.assertFalse(draft.project_id)
        self.order_a.invalidate_recordset(["amount_job_cost"])
        self.assertAlmostEqual(self.order_a.amount_job_cost, 0.0)

    def test_post_with_obra_ok(self):
        draft = self._bill(self.project_a, state="draft")
        draft.action_post()
        self.assertEqual(draft.state, "posted")
        self.order_a.invalidate_recordset(["amount_job_cost"])
        self.assertAlmostEqual(self.order_a.amount_job_cost, 50.0)

    def test_chapter_tie_stays_empty(self):
        order, project = self._make_obra("P2600994", "[C04] Tabiqueria y pladur")
        self.env["sale.order.line"].create(
            {
                "order_id": order.id,
                "display_type": "line_section",
                "name": "[C05] Techos de pladur",
            }
        )
        draft = self._bill(
            project,
            state="draft",
            lines=[
                (
                    0,
                    0,
                    {
                        "name": "Trabajo de pladur en planta",
                        "quantity": 1,
                        "price_unit": 80,
                        "tax_ids": [(6, 0, [])],
                    },
                )
            ],
        )
        content = draft.invoice_line_ids.filtered(lambda l: l.display_type == "product")
        content.write({"name": "Trabajo de pladur en planta"})
        draft._suggest_chapters()
        self.assertFalse(content.construction_section_id)

    def test_chapter_cost_hole(self):
        bill = self._bill(
            self.project_b,
            state="draft",
            lines=[
                (
                    0,
                    0,
                    {
                        "name": "Sin capitulo asignado",
                        "product_id": self.product.id,
                        "quantity": 1,
                        "price_unit": 40,
                        "tax_ids": [(6, 0, [])],
                    },
                )
            ],
        )
        bill.invoice_line_ids.filtered(lambda l: l.display_type == "product").write(
            {"name": "Sin capitulo asignado", "construction_section_id": False}
        )
        bill.action_post()
        self.order_b.invalidate_recordset(
            ["amount_job_cost", "amount_cost_in_chapter", "amount_cost_no_chapter"]
        )
        self.assertAlmostEqual(self.order_b.amount_job_cost, 40.0)
        self.assertAlmostEqual(self.order_b.amount_cost_in_chapter, 0.0)
        self.assertAlmostEqual(self.order_b.amount_cost_no_chapter, 40.0)

    def test_chapter_cost_assigned(self):
        bill = self._bill(
            self.project_b,
            state="draft",
            lines=[
                (
                    0,
                    0,
                    {
                        "name": "Tabique pladur",
                        "product_id": self.product.id,
                        "quantity": 1,
                        "price_unit": 40,
                        "tax_ids": [(6, 0, [])],
                    },
                )
            ],
        )
        section = self.order_b.order_line.filtered(lambda l: l.display_type == "line_section")
        bill.invoice_line_ids.filtered(lambda l: l.display_type == "product").write(
            {"construction_section_id": section.id}
        )
        bill.action_post()
        self.order_b.invalidate_recordset(
            [
                "amount_job_cost",
                "amount_cost_in_chapter",
                "amount_cost_no_chapter",
                "chapter_cost_text",
            ]
        )
        self.assertAlmostEqual(self.order_b.amount_cost_in_chapter, 40.0)
        self.assertAlmostEqual(self.order_b.amount_cost_no_chapter, 0.0)
        self.assertTrue(self.order_b.chapter_cost_text)
