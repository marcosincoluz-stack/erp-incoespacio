import base64
import os
from datetime import timedelta

from odoo.addons.incoespacio_construction_certification_pending_bills import (
    post_init_hook,
)
from odoo.tests.common import TransactionCase


class TestPendingBills(TransactionCase):
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
            {"name": "Proveedor cert", "is_company": True}
        )
        cls.customer = cls.env["res.partner"].create(
            {"name": "Cliente cert", "is_company": True}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Partida pending",
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
                            "product_uom_qty": 10,
                            "price_unit": 100,
                            "tax_id": [(6, 0, [])],
                        },
                    )
                ],
            }
        )
        cls.order.action_confirm()

    def _bill(self, amount, invoice_date, move_type="in_invoice", project=None):
        bill = self.env["account.move"].create(
            {
                "move_type": move_type,
                "partner_id": self.partner.id,
                "invoice_date": invoice_date,
                "project_id": (project or self.order.project_id).id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Coste obra",
                            "quantity": 1,
                            "price_unit": amount,
                            "tax_ids": [(6, 0, [])],
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

    def test_pending_confirm_draft_date_refund_hook(self):
        cert = self._cert()
        bill = self._bill(40, cert.date)
        cert.invalidate_recordset(
            ["pending_bill_ids", "pending_bill_count", "pending_bill_amount"]
        )
        self.assertEqual(cert.pending_bill_count, 1)
        self.assertAlmostEqual(cert.pending_bill_amount, 40.0)

        later = self._bill(25, cert.date + timedelta(days=10))
        refund = self._bill(10, cert.date, move_type="in_refund")
        cert.invalidate_recordset(
            ["pending_bill_ids", "pending_bill_count", "pending_bill_amount"]
        )
        self.assertEqual(cert.pending_bill_count, 2)
        self.assertAlmostEqual(cert.pending_bill_amount, 30.0)
        self.assertNotIn(later, cert.pending_bill_ids)

        cert.action_confirm()
        self.assertEqual(bill.certification_id, cert)
        self.assertEqual(refund.certification_id, cert)
        self.assertFalse(later.certification_id)
        cert.invalidate_recordset(
            ["pending_bill_ids", "pending_bill_count", "pending_bill_amount"]
        )
        self.assertEqual(cert.pending_bill_count, 0)
        action = cert.action_view_pending_bills()
        self.assertEqual(action["res_model"], "account.move")
        self.assertEqual(action["domain"], cert._pending_bill_domain())

        other = self.env["project.project"].create({"name": "Otra obra"})
        bill.project_id = other
        self.assertFalse(bill.certification_id)

        cert.action_draft()
        self.assertFalse(refund.certification_id)
        cert.invalidate_recordset(["pending_bill_count", "pending_bill_ids"])
        self.assertEqual(cert.pending_bill_count, 1)

        cert.action_confirm()
        cert.action_cancel()
        self.assertFalse(refund.certification_id)

        billed = self._cert()
        billed.line_ids.filtered(lambda l: not l.display_type).qty_origin = 1
        billed.action_confirm()
        billed.action_create_invoice()
        same_day = self._bill(15, billed.date)
        historical = self._bill(20, billed.date - timedelta(days=1))
        self.assertFalse(same_day.certification_id)
        self.assertFalse(historical.certification_id)
        post_init_hook(self.env)
        same_day.invalidate_recordset(["certification_id"])
        historical.invalidate_recordset(["certification_id"])
        self.assertFalse(same_day.certification_id)
        self.assertEqual(historical.certification_id, billed)

    def test_demo_subcapitulos_bc3(self):
        path = os.path.join(os.path.dirname(__file__), "DEMO_subcapitulos.bc3")
        with open(path, "rb") as demo:
            raw = demo.read()
        wiz = self.env["bc3.import.wizard"].create(
            {
                "bc3_file": base64.b64encode(raw),
                "bc3_file_name": "DEMO_subcapitulos.bc3",
                "version_id": self.env.ref("bc3_importer.bc3_version_2020_v2").id,
                "partner_id": self.customer.id,
                "create_products": False,
            }
        )
        wiz.do_action()
        order = wiz.sale_id
        order.action_confirm()
        self.assertTrue(order.project_id)
        bill = self._bill(100, order.date_order, project=order.project_id)
        action = order.action_create_certification()
        cert = self.env["construction.certification"].browse(action["res_id"])
        cert.invalidate_recordset(
            ["pending_bill_ids", "pending_bill_count", "pending_bill_amount"]
        )
        self.assertEqual(cert.pending_bill_count, 1)
        self.assertAlmostEqual(cert.pending_bill_amount, 100.0)
        self.assertIn(bill, cert.pending_bill_ids)
