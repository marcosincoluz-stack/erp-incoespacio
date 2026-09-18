from odoo import fields
from odoo.tests.common import TransactionCase


class TestOcrObraPurchase(TransactionCase):
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
            {"name": "Cliente PO partida", "is_company": True}
        )
        cls.partner = cls.env["res.partner"].create(
            {"name": "Proveedor PO partida", "is_company": True}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Partida PO",
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
                "order_line": [
                    (0, 0, {"display_type": "line_section", "name": "[C04] Tabiqueria"}),
                    (
                        0,
                        0,
                        {
                            "name": "[UO0401] Tabique de pladur",
                            "product_id": cls.product.id,
                            "product_uom_qty": 10,
                            "price_unit": 22.8,
                            "tax_id": [(6, 0, [])],
                        },
                    ),
                ],
            }
        )
        cls.order.action_confirm()
        cls.uo1 = cls.order.order_line.filtered(lambda l: not l.display_type)

    def test_po_line_copies_partida_to_bill(self):
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.partner.id,
                "project_id": self.order.project_id.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "name": self.product.name,
                            "product_qty": 1,
                            "price_unit": 40,
                            "date_planned": fields.Datetime.now(),
                            "construction_line_id": self.uo1.id,
                        },
                    )
                ],
            }
        )
        self.assertEqual(po.order_line.construction_line_id, self.uo1)
        po.button_confirm()
        action = po.action_create_invoice()
        bill = self.env["account.move"].browse(action["res_id"])
        line = bill.invoice_line_ids.filtered(lambda l: l.display_type == "product")
        self.assertEqual(line.construction_line_id, self.uo1)
        self.assertEqual(bill.project_id, self.order.project_id)
