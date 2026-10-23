from odoo.tests.common import TransactionCase


class TestObraPath(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        income = cls.env["account.account"].search(
            [("account_type", "=", "income"), ("company_id", "=", company.id)],
            limit=1,
        )
        cls.partner = cls.env["res.partner"].create(
            {"name": "Obra Nav", "is_company": True}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Partida nav",
                "type": "service",
                "invoice_policy": "order",
                "list_price": 100,
                "taxes_id": [(5, 0, 0)],
                "property_account_income_id": income.id if income else False,
            }
        )
        cls.order = cls.env["sale.order"].create(
            {
                "partner_id": cls.partner.id,
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

    def test_invoice_links_certification(self):
        self.order.action_confirm()
        action = self.order.action_create_certification()
        cert = self.env["construction.certification"].browse(action["res_id"])
        cert.line_ids.filtered(lambda line: not line.display_type)[:1].qty_origin = 3
        cert.action_confirm()
        cert.action_create_invoice()
        self.assertEqual(cert.invoice_id.invoice_certification_id, cert)
