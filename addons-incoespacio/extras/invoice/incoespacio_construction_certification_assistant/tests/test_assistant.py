from datetime import timedelta

from odoo import fields
from odoo.tests.common import TransactionCase


class TestCertificationAssistant(TransactionCase):
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
            {"name": "Proveedor assistant", "is_company": True}
        )
        cls.customer = cls.env["res.partner"].create(
            {"name": "Cliente assistant", "is_company": True}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Partida assistant",
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

    def _bill(self, qty, price, move_type="in_invoice", partida=None, date=None, name=None, uom=None):
        sol = self.sol if partida is None else (partida or self.sol)
        project = sol.order_id.project_id if partida is not False else self.order.project_id
        line_vals = {
            "name": name or "Coste obra",
            "quantity": qty,
            "price_unit": price,
            "tax_ids": [(6, 0, [])],
            "construction_line_id": sol.id if partida is not False else False,
        }
        if uom:
            line_vals["product_uom_id"] = uom.id
        bill = self.env["account.move"].create(
            {
                "move_type": move_type,
                "partner_id": self.partner.id,
                "invoice_date": date or (sol.order_id.date_order if partida is not False else self.order.date_order),
                "project_id": project.id,
                "invoice_line_ids": [(0, 0, line_vals)],
            }
        )
        bill.action_post()
        return bill

    def _cert(self, order=None):
        action = (order or self.order).action_create_certification()
        return self.env["construction.certification"].browse(action["res_id"])

    def _clines(self, cert):
        return cert.line_ids.filtered(lambda l: not l.display_type)

    def test_pending_cost_needs_measure_refund(self):
        cert = self._cert()
        bill = self._bill(5, 8)
        self._invalidate(cert)
        line = self._clines(cert)
        self.assertAlmostEqual(line.pending_cost_amount, 40.0)
        self.assertAlmostEqual(line.pending_cost_qty, 5.0)
        self.assertTrue(line.needs_measure)
        self.assertIn(bill.name, line.pending_bill_names)
        self.assertEqual(cert.assistant_line_count, 1)

        line.qty_period = 1
        self._invalidate(cert)
        self.assertFalse(line.needs_measure)

        line.qty_period = 0
        self._bill(1, 10, move_type="in_refund")
        self._invalidate(cert)
        self.assertAlmostEqual(line.pending_cost_amount, 30.0)
        self.assertAlmostEqual(line.pending_cost_qty, 4.0)

    def test_apply_suggested_cap_and_all(self):
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
        self._bill(30, 2, partida=self.sol)
        self._bill(3, 8, partida=other)
        self._invalidate(cert)
        paint = cert.line_ids.filtered(lambda l: l.sale_order_line_id == self.sol)
        alba = cert.line_ids.filtered(lambda l: l.sale_order_line_id == other)
        self.assertAlmostEqual(paint.qty_suggested, 10.0)
        paint.action_apply_suggested()
        self.assertAlmostEqual(paint.qty_period, 10.0)
        self._invalidate(cert)
        self.assertFalse(paint.needs_measure)

        alba.action_apply_suggested()
        self.assertAlmostEqual(alba.qty_period, 3.0)

    def test_suggest_by_cost_qty_and_fallback(self):
        self.order.planned_percent = 20
        cert = self._cert()
        self.assertEqual(cert.suggest_by, "cost")
        self._bill(1, 160)
        self._invalidate(cert)
        line = self._clines(cert)
        self.assertAlmostEqual(self.sol.price_planned, 80.0)
        self.assertAlmostEqual(line.qty_suggested, 2.0)
        self.assertAlmostEqual(cert.assistant_pending_cost, 160.0)
        self.assertAlmostEqual(cert.assistant_suggested_amount, 200.0)

        cert.suggest_by = "qty"
        self._invalidate(cert)
        self.assertAlmostEqual(line.qty_suggested, 1.0)

        order = self.env["sale.order"].create(
            {
                "partner_id": self.customer.id,
                "bc3": True,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "name": "Pintura sin margen",
                            "product_uom_qty": 10,
                            "price_unit": 100,
                            "tax_id": [(6, 0, [])],
                        },
                    )
                ],
            }
        )
        order.action_confirm()
        sol = order.order_line.filtered(lambda l: not l.display_type)
        cert2 = self._cert(order)
        self.assertEqual(cert2.suggest_by, "qty")
        self._bill(5, 8, partida=sol)
        self._invalidate(cert2)
        self.assertAlmostEqual(self._clines(cert2).qty_suggested, 5.0)

    def test_reviewed_and_assign_partida(self):
        cert = self._cert()
        bill = self._bill(2, 10, partida=False)
        self._invalidate(cert)
        self.assertEqual(cert.pending_bill_count, 1)
        self.assertTrue(cert.pending_review_line_ids)
        line = self._clines(cert)
        self.assertFalse(line.pending_cost_amount)

        aml = cert.pending_review_line_ids
        aml.write({"construction_line_id": self.sol.id})
        self._invalidate(cert)
        self.assertAlmostEqual(line.pending_cost_amount, 20.0)
        self.assertFalse(cert.pending_review_line_ids)

        bill.with_context(certification_id=cert.id).action_cert_reviewed()
        self._invalidate(cert)
        self.assertEqual(bill.certification_id, cert)
        self.assertEqual(cert.pending_bill_count, 0)

        cert.action_draft()
        self._invalidate(cert)
        self.assertFalse(bill.certification_id)
        self.assertEqual(cert.pending_bill_count, 1)

    def test_confirm_chatter_measured_with_bill(self):
        cert = self._cert()
        self._bill(2, 10)
        self._invalidate(cert)
        line = self._clines(cert)
        line.action_apply_suggested()
        cert.action_confirm()
        bodies = " ".join(cert.message_ids.mapped("body"))
        self.assertIn("Partidas medidas con factura", bodies)

    def test_over_sale_and_create_modification(self):
        self.order.planned_percent = 20
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
        line = cert.line_ids.filtered(lambda l: l.sale_order_line_id == cheap)
        self.assertEqual(line.cost_alert, "over_sale")
        self.assertTrue(cert.pending_review_line_ids)

        line.action_create_modification()
        mod = self.order.order_line.filtered("is_modification")
        self.assertEqual(len(mod), 1)
        self.assertAlmostEqual(mod.price_unit, 1020.0 / 0.8)
        cert_mod = cert.line_ids.filtered("is_modification")
        self.assertAlmostEqual(cert_mod.qty_origin, 1.0)
        self._invalidate(cert)
        self.assertFalse(line.cost_alert)
        self.assertAlmostEqual(cert_mod.pending_cost_amount, 1020.0)
        self.assertTrue(cert.message_ids.filtered(lambda m: "Modificado" in (m.body or "")))

    def test_certified_alert_and_suggested_partida(self):
        self.env["sale.order.line"].create(
            {
                "order_id": self.order.id,
                "sequence": 5,
                "display_type": "line_section",
                "name": "[C01] Alicatados",
            }
        )
        bath = self.env["sale.order.line"].create(
            {
                "order_id": self.order.id,
                "sequence": 6,
                "product_id": self.product.id,
                "name": "[D01] Alicatado de baño",
                "product_uom_qty": 2,
                "price_unit": 50,
                "tax_id": [(6, 0, [])],
            }
        )
        kitchen = self.env["sale.order.line"].create(
            {
                "order_id": self.order.id,
                "sequence": 7,
                "product_id": self.product.id,
                "name": "[D02] Alicatado de cocina",
                "product_uom_qty": 4,
                "price_unit": 40,
                "tax_id": [(6, 0, [])],
            }
        )
        cert1 = self._cert()
        cline = cert1.line_ids.filtered(lambda l: l.sale_order_line_id == bath)
        cline.qty_origin = cline.qty_budget
        cert1.action_confirm()
        cert1.action_create_invoice()

        bill = self._bill(1, 80, partida=bath, name="Alicatado ceramico")
        cert2 = self._cert()
        self._invalidate(cert2)
        line = cert2.line_ids.filtered(lambda l: l.sale_order_line_id == bath)
        self.assertEqual(line.cost_alert, "certified")
        aml = bill.invoice_line_ids.filtered(lambda l: l.display_type == "product")
        self.assertEqual(aml.construction_line_suggested_id, kitchen)
        self.assertEqual(
            aml.with_context(certification_id=cert2.id).review_reason,
            "Partida ya certificada",
        )
        aml.action_use_suggested_partida()
        self.assertEqual(aml.construction_line_id, kitchen)

    def test_split_posted_bill_keeps_name(self):
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
        bill = self._bill(1, 100, partida=self.sol)
        name = bill.name
        aml = bill.invoice_line_ids.filtered(lambda l: l.display_type == "product")
        wiz = self.env["ocr.obra.split.wizard"].create(
            {
                "line_id": aml.id,
                "split_line_ids": [
                    (0, 0, {"construction_line_id": self.sol.id, "amount": 60}),
                    (0, 0, {"construction_line_id": other.id, "amount": 40}),
                ],
            }
        )
        wiz.action_apply()
        self.assertEqual(bill.state, "posted")
        self.assertEqual(bill.name, name)
        lines = bill.invoice_line_ids.filtered(lambda l: l.display_type == "product")
        self.assertEqual(len(lines), 2)
        self.assertEqual(
            set(lines.mapped("construction_line_id").ids), {self.sol.id, other.id}
        )
        self._invalidate(cert)
        paint = cert.line_ids.filtered(lambda l: l.sale_order_line_id == self.sol)
        alba = cert.line_ids.filtered(lambda l: l.sale_order_line_id == other)
        self.assertAlmostEqual(paint.pending_cost_amount, 60.0)
        self.assertAlmostEqual(alba.pending_cost_amount, 40.0)

    def test_pending_bill_previous_period(self):
        day = fields.Date.today()
        cert1 = self._cert()
        cert1.date = day
        self._clines(cert1).qty_period = 1
        cert1.action_confirm()
        cert1.action_create_invoice()

        late = self._bill(1, 10, date=day - timedelta(days=5))
        cert2 = self._cert()
        cert2.date = day + timedelta(days=30)
        self._invalidate(cert2)
        self.assertIn(late, cert2.pending_bill_late_ids)
        self.assertNotIn(late, cert2.pending_bill_period_ids)
        self.assertEqual(cert2.pending_bill_late_count, 1)
        self.assertEqual(cert2.previous_cert_date, day)

    def _invalidate(self, cert):
        cert.invalidate_recordset(
            [
                "pending_bill_ids",
                "pending_bill_count",
                "pending_review_line_ids",
                "pending_bill_period_ids",
                "pending_bill_late_ids",
                "pending_bill_late_count",
                "previous_cert_date",
                "assistant_line_count",
                "assistant_pending_cost",
                "assistant_suggested_amount",
                "assistant_suggested_percent",
            ]
        )
        cert.line_ids.invalidate_recordset(
            [
                "pending_cost_amount",
                "pending_cost_qty",
                "pending_bill_names",
                "needs_measure",
                "qty_suggested",
                "qty_period",
                "cost_alert",
                "uom_mismatch",
                "suggest_basis",
            ]
        )

    def _area_order(self, qty=10, price=100):
        categ = self.env["uom.category"].create({"name": "Área assistant"})
        m2 = self.env["uom.uom"].create(
            {"name": "m² a", "category_id": categ.id, "uom_type": "reference"}
        )
        product = self.env["product.product"].create(
            {
                "name": "Partida m2",
                "type": "service",
                "invoice_policy": "order",
                "list_price": price,
                "uom_id": m2.id,
                "uom_po_id": m2.id,
                "taxes_id": [(5, 0, 0)],
                "supplier_taxes_id": [(5, 0, 0)],
            }
        )
        order = self.env["sale.order"].create(
            {
                "partner_id": self.customer.id,
                "bc3": True,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "name": "Pintura m2",
                            "product_uom_qty": qty,
                            "product_uom": m2.id,
                            "price_unit": price,
                            "tax_id": [(6, 0, [])],
                        },
                    )
                ],
            }
        )
        order.action_confirm()
        sol = order.order_line.filtered(lambda l: not l.display_type)
        return order, sol, m2

    def test_uom_mismatch_falls_to_sale(self):
        order, sol, _m2 = self._area_order()
        cert = self._cert(order)
        unit = self.env.ref("uom.product_uom_unit")
        self._bill(30, 10, partida=sol, uom=unit)
        self._invalidate(cert)
        line = self._clines(cert)
        self.assertTrue(line.uom_mismatch)
        self.assertEqual(line.suggest_basis, "sale")
        self.assertAlmostEqual(line.qty_suggested, 3.0)
        self.assertAlmostEqual(line.pending_cost_qty, 0.0)

    def test_uom_conversion_cm2_to_m2(self):
        order, sol, m2 = self._area_order()
        cm2 = self.env["uom.uom"].create(
            {
                "name": "cm² a",
                "category_id": m2.category_id.id,
                "uom_type": "smaller",
                "factor": 10000,
            }
        )
        cert = self._cert(order)
        self._bill(20000, 0.01, partida=sol, uom=cm2)
        self._invalidate(cert)
        line = self._clines(cert)
        expected = cm2._compute_quantity(20000, m2)
        self.assertFalse(line.uom_mismatch)
        self.assertEqual(line.suggest_basis, "qty")
        self.assertAlmostEqual(line.pending_cost_qty, expected)
        self.assertAlmostEqual(line.qty_suggested, expected)

    def test_suggest_basis_sale_without_planned(self):
        self.order.planned_percent = 0
        cert = self._cert()
        cert.suggest_by = "cost"
        self._bill(1, 300)
        self._invalidate(cert)
        line = self._clines(cert)
        self.assertEqual(line.suggest_basis, "sale")
        self.assertAlmostEqual(line.qty_suggested, 3.0)
