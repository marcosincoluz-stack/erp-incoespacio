from odoo.tests.common import TransactionCase


class TestObrasList(TransactionCase):
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
        cls.vendor = cls.env["res.partner"].create({"name": "Proveedor lista"})
        product = cls.env["product.product"].create(
            {
                "name": "Partida lista",
                "type": "service",
                "invoice_policy": "order",
                "taxes_id": [(5, 0, 0)],
                "supplier_taxes_id": [(5, 0, 0)],
                "property_account_income_id": income.id if income else False,
                "property_account_expense_id": expense.id if expense else False,
            }
        )
        cls.order = cls.env["sale.order"].create(
            {
                "partner_id": cls.env["res.partner"].create({"name": "Cliente lista"}).id,
                "bc3": True,
                "planned_percent": 20.0,
                "order_line": [
                    (0, 0, {"product_id": product.id, "product_uom_qty": 10, "price_unit": 100, "tax_id": [(6, 0, [])]})
                ],
            }
        )
        cls.order.action_confirm()

    def _post_bill(self, price):
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.vendor.id,
                "invoice_date": self.order.date_order,
                "project_id": self.order.project_id.id,
                "invoice_line_ids": [(0, 0, {"name": "Coste", "quantity": 1, "price_unit": price, "tax_ids": [(6, 0, [])]})],
            }
        )
        bill.action_post()

    def test_margin_percent_job(self):
        self.assertAlmostEqual(self.order.margin_percent_job, 0.0)
        action = self.order.action_create_certification()
        cert = self.env["construction.certification"].browse(action["res_id"])
        cert.line_ids.filtered(lambda l: not l.display_type).qty_origin = 4
        cert.action_confirm()
        cert.action_create_invoice()
        self._post_bill(300)
        self.order.invalidate_recordset()
        self.assertAlmostEqual(self.order.amount_certified_origin, 400.0)
        self.assertAlmostEqual(self.order.amount_job_margin, 100.0)
        self.assertAlmostEqual(self.order.margin_percent_job, 25.0)

    def test_columns_in_quotes_and_orders(self):
        Order = self.env["sale.order"].with_user(self.env.ref("base.user_admin"))
        for xmlid in ("sale.view_order_tree", "sale.view_quotation_tree"):
            arch = Order.get_view(self.env.ref(xmlid).id, "tree")["arch"]
            self.assertIn("margin_percent_job", arch)
            self.assertNotIn('name="company_id" optional', arch)
