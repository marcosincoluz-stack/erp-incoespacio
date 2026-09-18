from odoo.tests.common import TransactionCase


class TestConstructionMargins(TransactionCase):
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
            {"name": "Cliente Márgenes", "is_company": True}
        )
        cls.vendor = cls.env["res.partner"].create(
            {"name": "Proveedor Márgenes", "is_company": True}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Partida margen",
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
                "planned_percent": 20.0,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": cls.product.id,
                            "product_uom_qty": 10,
                            "price_unit": 100,
                            "tax_id": [(6, 0, [])],
                        },
                    )
                ],
            }
        )
        cls.line = cls.order.order_line.filtered(lambda l: not l.display_type)
        cls.order.action_confirm()

    def _post_bill(self, price, partida=None):
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.vendor.id,
                "invoice_date": self.order.date_order,
                "project_id": self.order.project_id.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Coste partida",
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": price,
                            "tax_ids": [(6, 0, [])],
                            "construction_line_id": partida.id if partida else False,
                        },
                    )
                ],
            }
        )
        bill.action_post()
        return bill

    def _invoice_cert(self, qty_origin):
        action = self.order.action_create_certification()
        cert = self.env["construction.certification"].browse(action["res_id"])
        line = cert.line_ids.filtered(lambda l: not l.display_type)
        line.qty_origin = qty_origin
        cert.action_confirm()
        cert.action_create_invoice()
        return cert

    def test_line_and_order_margins(self):
        self.assertAlmostEqual(self.line.qty_planned, 10.0)
        self.assertAlmostEqual(self.line.price_planned, 80.0)
        self.assertAlmostEqual(self.line.amount_planned, 800.0)
        self._invoice_cert(4)
        self._post_bill(300, partida=self.line)
        self.line.invalidate_recordset()
        self.order.invalidate_recordset()
        self.assertAlmostEqual(self.line.amount_vendor_cost, 300.0)
        self.assertAlmostEqual(self.line.qty_cert_origin, 4.0)
        self.assertAlmostEqual(self.line.progress_percent, 40.0)
        self.assertAlmostEqual(self.line.amount_cert_origin, 400.0)
        self.assertAlmostEqual(self.line.amount_planned_done, 320.0)
        self.assertAlmostEqual(self.line.amount_cost_deviation, -20.0)
        self.assertAlmostEqual(self.line.amount_margin, 100.0)
        self.assertAlmostEqual(self.line.margin_percent, 25.0)
        self.assertAlmostEqual(self.line.price_unit_real, 75.0)
        self.assertEqual(len(self.line.vendor_cost_line_ids), 1)
        self.assertAlmostEqual(self.line.vendor_cost_line_ids.price_subtotal, 300.0)
        self.assertAlmostEqual(self.order.amount_untaxed, 1000.0)
        self.assertAlmostEqual(self.order.amount_certified_origin, 400.0)
        self.assertAlmostEqual(self.order.amount_cost_partida, 300.0)
        self.assertAlmostEqual(self.order.amount_margin_planned, 200.0)
        self.assertAlmostEqual(self.order.margin_percent_planned, 20.0)
        self.assertAlmostEqual(self.order.progress_percent, 40.0)
        self.assertAlmostEqual(self.order.amount_planned_done, 320.0)
        self.assertAlmostEqual(self.order.amount_cost_deviation, -20.0)
        self.assertAlmostEqual(self.order.amount_margin_real, 100.0)
        self.assertAlmostEqual(self.order.margin_percent_real, 25.0)
        self.assertAlmostEqual(self.order.amount_cost_unassigned, 0.0)

    def test_unassigned_cost(self):
        self._post_bill(600, partida=self.line)
        self._post_bill(100)
        self.line.invalidate_recordset()
        self.order.invalidate_recordset()
        self.assertAlmostEqual(self.order.amount_cost_partida, 600.0)
        self.assertAlmostEqual(self.order.amount_job_cost, 700.0)
        self.assertAlmostEqual(self.order.amount_cost_unassigned, 100.0)
        self.assertAlmostEqual(self.order.amount_cost_deviation, 0.0)
        self.assertEqual(len(self.line.vendor_cost_line_ids), 1)
        self.assertAlmostEqual(self.line.vendor_cost_line_ids.price_subtotal, 600.0)
