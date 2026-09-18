from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestOcrObraPartida(TransactionCase):
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
        cls.customer = cls.env["res.partner"].create(
            {"name": "Cliente Obra Partida", "is_company": True}
        )
        cls.partner = cls.env["res.partner"].create(
            {"name": "Proveedor Pladur", "is_company": True}
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
        cls.order = cls.env["sale.order"].create(
            {
                "partner_id": cls.customer.id,
                "bc3": True,
                "order_line": [
                    (0, 0, {"display_type": "line_section", "name": "[C01] Albañilería"}),
                    (
                        0,
                        0,
                        {
                            "name": "[D07DA101] Fábrica ladrillo 1/2 pie",
                            "product_id": cls.product.id,
                            "product_uom_qty": 2,
                            "price_unit": 27.0,
                            "tax_id": [(6, 0, [])],
                        },
                    ),
                    (0, 0, {"display_type": "line_section", "name": "[C04] Tabiqueria y pladur"}),
                    (
                        0,
                        0,
                        {
                            "name": "[UO0401] Tabique de pladur 15+15 sobre estructura",
                            "product_id": cls.product.id,
                            "product_uom_qty": 10,
                            "price_unit": 22.8,
                            "tax_id": [(6, 0, [])],
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "name": "[UO0402] Trasdosado de pladur",
                            "product_id": cls.product.id,
                            "product_uom_qty": 5,
                            "price_unit": 18.0,
                            "tax_id": [(6, 0, [])],
                        },
                    ),
                ],
            }
        )
        cls.order.action_confirm()
        cls.albanileria = cls.order.order_line.filtered(lambda l: "C01" in (l.name or "") and l.display_type == "line_section")
        cls.section = cls.order.order_line.filtered(lambda l: "C04" in (l.name or "") and l.display_type == "line_section")
        cls.ladrillo = cls.order.order_line.filtered(lambda l: "D07DA101" in (l.name or ""))
        cls.uo1 = cls.order.order_line.filtered(lambda l: "UO0401" in (l.name or ""))
        cls.uo2 = cls.order.order_line.filtered(lambda l: "UO0402" in (l.name or ""))

    def _draft_bill(self, name="Tabique autoportante de pladur 15+15 sobre estructura", price=100):
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "invoice_date": self.order.date_order,
                "project_id": self.order.project_id.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": name,
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": price,
                            "tax_ids": [(6, 0, [])],
                        },
                    )
                ],
            }
        )
        return bill, bill.invoice_line_ids.filtered(lambda l: l.display_type == "product")

    def test_partida_fills_chapter(self):
        bill, line = self._draft_bill()
        line.construction_line_id = self.uo1
        self.assertEqual(line.construction_section_id, self.section)

    def test_suggest_picks_partida(self):
        bill, line = self._draft_bill()
        bill._suggest_chapters()
        self.assertEqual(line.construction_line_id, self.uo1)
        self.assertEqual(line.construction_section_id, self.section)

    def test_split_two_partidas(self):
        bill, line = self._draft_bill(price=100)
        wiz = self.env["ocr.obra.split.wizard"].create(
            {
                "line_id": line.id,
                "split_line_ids": [
                    (0, 0, {"construction_line_id": self.uo1.id, "amount": 40}),
                    (0, 0, {"construction_line_id": self.uo2.id, "amount": 60}),
                ],
            }
        )
        wiz.action_apply()
        products = bill.invoice_line_ids.filtered(lambda l: l.display_type == "product")
        self.assertEqual(len(products), 2)
        by_uo = {p.construction_line_id: p.price_subtotal for p in products}
        self.assertAlmostEqual(by_uo[self.uo1], 40)
        self.assertAlmostEqual(by_uo[self.uo2], 60)
        self.assertEqual(products.mapped("construction_section_id"), self.section)

    def test_split_must_sum(self):
        bill, line = self._draft_bill(price=100)
        wiz = self.env["ocr.obra.split.wizard"].create(
            {
                "line_id": line.id,
                "split_line_ids": [
                    (0, 0, {"construction_line_id": self.uo1.id, "amount": 40}),
                    (0, 0, {"construction_line_id": self.uo2.id, "amount": 50}),
                ],
            }
        )
        self.assertAlmostEqual(wiz.amount_remaining, 10)
        with self.assertRaises(UserError):
            wiz.action_apply()

    def test_short_label_drops_long_text(self):
        self.uo1.name = (
            "[D13ACH001] TENDIDO YESO CONTROLADO+ ENLUCIDO MECAFINO P. VERTICALES = 3 m A- m². "
            "Tendido de yeso manual de fraguado controlado sobre paramentos verticales y un montón de texto técnico"
        )
        self.uo1.bc3_code = "D13ACH001"
        label = self.uo1.with_context(short_construction_line=True)._short_construction_label()
        self.assertIn("D13ACH001", label)
        self.assertIn("TENDIDO YESO", label)
        self.assertNotIn("paramentos", label)
        self.assertNotIn(self.order.name, self.uo1.with_context(short_construction_line=True).display_name)

    def test_partida_domain_follows_chapter(self):
        self.assertEqual(self.uo1.bc3_section_id, self.section)
        self.assertEqual(self.ladrillo.bc3_section_id, self.albanileria)
        under_c04 = self.env["sale.order.line"].search(
            [
                ("order_id", "=", self.order.id),
                ("display_type", "=", False),
                ("bc3_section_id", "=?", self.section.id),
            ]
        )
        self.assertIn(self.uo1, under_c04)
        self.assertNotIn(self.ladrillo, under_c04)

    def test_partida_tie_stays_empty(self):
        bill, line = self._draft_bill(name="Trabajo de pladur")
        line.write(
            {
                "name": "Trabajo de pladur",
                "construction_line_id": False,
                "construction_section_id": False,
            }
        )
        bill._suggest_chapters()
        self.assertFalse(line.construction_line_id)

    def test_onchange_project_on_new_bill(self):
        bill = self.env["account.move"].new(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "invoice_date": self.order.date_order,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Tabique autoportante de pladur 15+15 sobre estructura",
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": 100,
                            "tax_ids": [(6, 0, [])],
                        },
                    )
                ],
            }
        )
        bill.project_id = self.order.project_id
        bill._onchange_project_id_chapters()
        line = bill.invoice_line_ids.filtered(lambda l: l.display_type == "product")
        self.assertEqual(line.construction_line_id, self.uo1)

    def test_sticky_partida_from_vendor(self):
        first, fline = self._draft_bill()
        fline.construction_line_id = self.uo1
        first.action_post()
        draft, dline = self._draft_bill(name="Factura periodo marzo")
        dline.write(
            {
                "name": "Factura periodo marzo",
                "construction_line_id": False,
                "construction_section_id": False,
            }
        )
        draft._suggest_chapters()
        self.assertEqual(dline.construction_line_id, self.uo1)
        self.assertEqual(dline.construction_section_id, self.section)

    def test_vendor_cost_on_line(self):
        bill, line = self._draft_bill(price=40)
        line.construction_line_id = self.uo1
        bill.action_post()
        self.uo1.invalidate_recordset(["amount_vendor_cost"])
        self.uo2.invalidate_recordset(["amount_vendor_cost"])
        self.assertAlmostEqual(self.uo1.amount_vendor_cost, 40.0)
        self.assertAlmostEqual(self.uo2.amount_vendor_cost, 0.0)

    def test_split_default_remaining_is_subtotal(self):
        bill, line = self._draft_bill(price=100)
        vals = (
            self.env["ocr.obra.split.wizard"]
            .with_context(default_line_id=line.id)
            .default_get(["line_id", "split_line_ids"])
        )
        wiz = self.env["ocr.obra.split.wizard"].new(vals)
        self.assertAlmostEqual(wiz.split_line_ids.amount, 0.0)
        self.assertAlmostEqual(wiz.amount_remaining, 100.0)

    def test_split_onchange_fills_empty_line(self):
        bill, line = self._draft_bill(price=100)
        wiz = self.env["ocr.obra.split.wizard"].new(
            {
                "line_id": line.id,
                "split_line_ids": [
                    (0, 0, {"construction_line_id": self.uo1.id, "amount": 40}),
                    (0, 0, {"construction_line_id": self.uo2.id, "amount": 0}),
                ],
            }
        )
        wiz._onchange_fill_remaining()
        filled = wiz.split_line_ids.filtered(lambda l: l.construction_line_id == self.uo2)
        self.assertAlmostEqual(filled.amount, 60)

    def test_gastos_sin_partida_filter(self):
        domain = [
            ("move_type", "in", ("in_invoice", "in_refund")),
            ("state", "=", "posted"),
            ("project_id", "!=", False),
            ("has_unassigned_partida", "=", True),
        ]
        with_uo, line = self._draft_bill(price=40)
        line.construction_line_id = self.uo1
        with_uo.action_post()
        without_uo, _ = self._draft_bill(price=50)
        without_uo.action_post()
        skipped = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "invoice_date": self.order.date_order,
                "ocr_obra_state": "skipped",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Luz oficina",
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": 20,
                            "tax_ids": [(6, 0, [])],
                        },
                    )
                ],
            }
        )
        skipped.action_post()
        found = self.env["account.move"].search(domain)
        self.assertIn(without_uo, found)
        self.assertNotIn(with_uo, found)
        self.assertNotIn(skipped, found)
        action = self.order.action_view_gastos_sin_partida()
        scoped = self.env["account.move"].search(action["domain"])
        self.assertIn(without_uo, scoped)
        self.assertNotIn(with_uo, scoped)
        self.assertNotIn(skipped, scoped)

    def test_assign_posted_updates_uo_cost(self):
        bill, line = self._draft_bill(price=40)
        bill.action_post()
        self.order.invalidate_recordset(["amount_job_cost"])
        unassigned_before = self.order.amount_job_cost - sum(
            self.order.order_line.mapped("amount_vendor_cost")
        )
        self.assertAlmostEqual(unassigned_before, 40.0)
        copies = []
        orig_copy = type(line).copy

        def _spy_copy(self, default=None):
            copies.append(1)
            return orig_copy(self, default)

        type(line).copy = _spy_copy
        try:
            wiz = self.env["ocr.obra.assign.wizard"].create(
                {
                    "move_id": bill.id,
                    "line_ids": [
                        (
                            0,
                            0,
                            {
                                "move_line_id": line.id,
                                "construction_line_id": self.uo1.id,
                            },
                        )
                    ],
                }
            )
            wiz.action_apply()
        finally:
            type(line).copy = orig_copy
        self.assertFalse(copies)
        self.assertEqual(line.construction_line_id, self.uo1)
        self.assertEqual(
            len(bill.invoice_line_ids.filtered(lambda l: l.display_type == "product")),
            1,
        )
        self.uo1.invalidate_recordset(["amount_vendor_cost"])
        self.order.invalidate_recordset(["amount_job_cost"])
        self.assertAlmostEqual(self.uo1.amount_vendor_cost, 40.0)
        unassigned = self.order.amount_job_cost - sum(
            self.order.order_line.mapped("amount_vendor_cost")
        )
        self.assertAlmostEqual(unassigned, 0.0)
        if "amount_cost_unassigned" in self.order._fields:
            self.order.invalidate_recordset(["amount_cost_unassigned"])
            self.assertAlmostEqual(self.order.amount_cost_unassigned, 0.0)

    def test_bc3_section_compute_on_new_lines(self):
        order = self.env["sale.order"].new(
            {
                "partner_id": self.customer.id,
                "bc3": True,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "display_type": "line_section",
                            "name": "[C99] Capítulo nuevo",
                            "sequence": 1,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "name": "Partida nueva",
                            "product_uom_qty": 1,
                            "price_unit": 10,
                            "sequence": 2,
                        },
                    ),
                ],
            }
        )
        order.order_line._compute_bc3_section_id()
        partida = order.order_line.filtered(lambda l: not l.display_type)
        cap = order.order_line.filtered(lambda l: l.display_type == "line_section")
        self.assertEqual(partida.bc3_section_id, cap)
