from odoo.tests.common import TransactionCase


class TestCertificationLineLens(TransactionCase):
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
            {"name": "Proveedor lens", "is_company": True}
        )
        cls.customer = cls.env["res.partner"].create(
            {"name": "Cliente lens", "is_company": True}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Partida lens",
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
                "planned_percent": 20,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": cls.product.id,
                            "name": "Pintura",
                            "product_uom_qty": 10,
                            "price_unit": 100,
                            "tax_id": [(6, 0, [])],
                        },
                    )
                ],
            }
        )
        cls.order.action_confirm()
        cls.sol = cls.order.order_line.filtered(lambda l: not l.display_type)

    def _bill(self, qty, price, partida=None):
        sol = partida or self.sol
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "invoice_date": sol.order_id.date_order,
                "project_id": sol.order_id.project_id.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Coste obra",
                            "quantity": qty,
                            "price_unit": price,
                            "tax_ids": [(6, 0, [])],
                            "construction_line_id": sol.id,
                        },
                    )
                ],
            }
        )
        bill.action_post()
        return bill

    def _cert(self):
        action = self.order.action_create_certification()
        return self.env["construction.certification"].browse(action["res_id"])

    def _cline(self, cert, sol=None):
        sol = sol or self.sol
        return cert.line_ids.filtered(lambda l: l.sale_order_line_id == sol)

    def _invalidate(self, cert):
        cert.invalidate_recordset(["pending_bill_ids", "pending_bill_count"])
        cert.line_ids.invalidate_recordset(
            [
                "pending_cost_amount",
                "pending_cost_qty",
                "qty_suggested",
                "suggest_basis",
                "cost_alert",
                "qty_period",
            ]
        )

    def _lens(self, line):
        return self.env["certification.line.lens"].with_context(
            default_line_id=line.id
        ).create({})

    def test_lens_values_and_accept(self):
        cert = self._cert()
        self._bill(1, 160)
        self._invalidate(cert)
        line = self._cline(cert)
        wiz = self._lens(line)
        self.assertAlmostEqual(wiz.price_planned, 80.0)
        self.assertAlmostEqual(wiz.cost_vs_planned_percent, 20.0)
        self.assertAlmostEqual(wiz.qty_period, 2.0)
        self.assertAlmostEqual(wiz.margin_new, 40.0)
        wiz.qty_period = 3
        self.assertAlmostEqual(wiz.amount_period_new, 300.0)
        wiz.action_accept()
        self.assertAlmostEqual(line.qty_period, 3.0)

    def test_use_suggested_and_fill_remaining(self):
        cert = self._cert()
        self._bill(1, 160)
        self._invalidate(cert)
        wiz = self._lens(self._cline(cert))
        wiz.qty_period = 0
        wiz.action_use_suggested()
        self.assertAlmostEqual(wiz.qty_period, 2.0)
        wiz.action_fill_remaining()
        self.assertAlmostEqual(wiz.qty_period, 10.0)

    def test_create_modification_from_lens(self):
        cheap = self.env["sale.order.line"].create(
            {
                "order_id": self.order.id,
                "product_id": self.product.id,
                "name": "Emergencia",
                "product_uom_qty": 1,
                "price_unit": 59,
                "tax_id": [(6, 0, [])],
            }
        )
        cert = self._cert()
        self._bill(1, 1020, partida=cheap)
        self._invalidate(cert)
        line = self._cline(cert, cheap)
        self.assertEqual(line.cost_alert, "over_sale")
        wiz = self._lens(line)
        self.assertEqual(wiz.cost_alert, "over_sale")
        wiz.action_create_modification()
        self._invalidate(cert)
        self.assertFalse(line.cost_alert)
        self.assertTrue(self.order.order_line.filtered("is_modification"))

    def test_reassign_bill_line_moves_cost(self):
        other = self.env["sale.order.line"].create(
            {
                "order_id": self.order.id,
                "product_id": self.product.id,
                "name": "Albañilería",
                "product_uom_qty": 10,
                "price_unit": 50,
                "tax_id": [(6, 0, [])],
            }
        )
        cert = self._cert()
        self._bill(1, 100)
        self._invalidate(cert)
        paint = self._cline(cert)
        alba = self._cline(cert, other)
        wiz = self._lens(paint)
        self.assertEqual(len(wiz.bill_line_ids), 1)
        wiz.bill_line_ids.construction_line_id = other
        wiz.action_accept()
        self._invalidate(cert)
        self.assertAlmostEqual(paint.pending_cost_amount, 0.0)
        self.assertAlmostEqual(alba.pending_cost_amount, 100.0)

    def _lens_case(self, qty, price, bill_qty, bill_price, planned=20, suggest_by=None):
        order = self.env["sale.order"].create(
            {
                "partner_id": self.customer.id,
                "bc3": True,
                "planned_percent": planned,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "name": "Alicatado",
                            "product_uom_qty": qty,
                            "price_unit": price,
                            "tax_id": [(6, 0, [])],
                        },
                    )
                ],
            }
        )
        order.action_confirm()
        sol = order.order_line.filtered(lambda l: not l.display_type)
        action = order.action_create_certification()
        cert = self.env["construction.certification"].browse(action["res_id"])
        if suggest_by:
            cert.suggest_by = suggest_by
        self._bill(bill_qty, bill_price, partida=sol)
        self._invalidate(cert)
        return self._lens(self._cline(cert, sol))

    def test_verdict_levels(self):
        danger = self._lens_case(21.22, 8.30, 21, 10)
        self.assertEqual(danger.verdict_level, "danger")
        self.assertIn("210", danger.verdict)
        self.assertIn("176", danger.verdict)

        warn = self._lens_case(21.22, 8.30, 21, 7)
        self.assertEqual(warn.verdict_level, "warning")
        self.assertIn("objetivo", warn.verdict)

        ok = self._lens_case(21.22, 8.30, 21, 5)
        self.assertEqual(ok.verdict_level, "success")
        self.assertIn("dentro de objetivo", ok.verdict)
        self.assertIn("P.U. objetivo", ok.verdict)

    def test_verdict_sale_basis_without_planned(self):
        wiz = self._lens_case(10, 100, 1, 300, planned=0, suggest_by="cost")
        self.assertEqual(wiz.suggest_basis, "sale")
        self.assertIn("P.U. venta", wiz.verdict)

    def test_verdict_updates_with_qty_period(self):
        wiz = self._lens_case(21.22, 8.30, 21, 7)
        self.assertEqual(wiz.verdict_level, "warning")
        before = wiz.verdict
        wiz.qty_period = 1
        self.assertNotEqual(wiz.verdict, before)
        self.assertIn("-138", wiz.verdict)
