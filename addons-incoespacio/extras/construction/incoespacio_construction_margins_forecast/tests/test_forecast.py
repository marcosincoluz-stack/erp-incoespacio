from odoo import fields
from odoo.tests.common import TransactionCase


class TestMarginsForecast(TransactionCase):
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
            {"name": "Cliente forecast", "is_company": True}
        )
        cls.vendor = cls.env["res.partner"].create(
            {"name": "Proveedor forecast", "is_company": True}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Partida forecast",
                "type": "service",
                "invoice_policy": "order",
                "purchase_ok": True,
                "purchase_method": "purchase",
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

    def _po(self, amount):
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "project_id": self.order.project_id.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "name": self.product.name,
                            "product_qty": 1,
                            "price_unit": amount,
                            "date_planned": fields.Datetime.now(),
                            "construction_line_id": self.line.id,
                        },
                    )
                ],
            }
        )
        po.button_confirm()
        return po

    def _invoice_cert(self, qty_origin):
        action = self.order.action_create_certification()
        cert = self.env["construction.certification"].browse(action["res_id"])
        line = cert.line_ids.filtered(lambda l: not l.display_type)
        line.qty_origin = qty_origin
        cert.action_confirm()
        cert.action_create_invoice()
        return cert

    def _post_bill(self, price):
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
                            "construction_line_id": self.line.id,
                        },
                    )
                ],
            }
        )
        bill.action_post()
        return bill

    def test_committed_moves_to_invoiced(self):
        po = self._po(300)
        self.line.invalidate_recordset()
        self.order.invalidate_recordset()
        self.assertAlmostEqual(self.line.amount_po_cost, 300.0)
        self.assertAlmostEqual(self.line.amount_cost_incurred, 300.0)
        self.assertAlmostEqual(self.order.amount_po_partida, 300.0)

        action = po.action_create_invoice()
        bill = self.env["account.move"].browse(action["res_id"])
        bill.invoice_date = fields.Date.context_today(bill)
        bill.action_post()
        self.line.invalidate_recordset()
        self.order.invalidate_recordset()
        self.assertAlmostEqual(self.line.amount_po_cost, 0.0)
        self.assertAlmostEqual(self.line.amount_vendor_cost, 300.0)
        self.assertAlmostEqual(self.line.amount_cost_incurred, 300.0)

    def test_forecast_with_certification(self):
        self._invoice_cert(4)
        self._post_bill(400)
        self.line.invalidate_recordset()
        self.order.invalidate_recordset()
        self.assertAlmostEqual(self.line.price_unit_forecast, 100.0)
        self.assertAlmostEqual(self.line.amount_cost_forecast, 1000.0)
        self.assertAlmostEqual(self.line.amount_margin_forecast, 0.0)
        self.assertAlmostEqual(self.order.amount_cost_forecast, 1000.0)
        self.assertAlmostEqual(self.order.margin_percent_forecast, 0.0)

    def test_forecast_without_certification(self):
        self.line.invalidate_recordset()
        self.order.invalidate_recordset()
        self.assertAlmostEqual(self.line.price_planned, 80.0)
        self.assertAlmostEqual(self.line.amount_cost_forecast, 800.0)
        self.assertAlmostEqual(self.line.amount_margin_forecast, 200.0)
        self.assertAlmostEqual(self.order.amount_cost_forecast, 800.0)
        self.assertAlmostEqual(self.order.margin_percent_forecast, 20.0)
