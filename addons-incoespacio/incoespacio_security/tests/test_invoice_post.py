from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestInvoicePost(TransactionCase):
    def test_post_requires_validator(self):
        partner = self.env["res.partner"].create({"name": "Prov validador"})
        user = self.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "Contable sin validar",
                "login": "novalidator_s1",
                "email": "novalidator_s1@example.com",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("account.group_account_invoice").id,
                        ],
                    )
                ],
            }
        )
        move = (
            self.env["account.move"]
            .with_user(user)
            .create(
                {
                    "move_type": "in_invoice",
                    "partner_id": partner.id,
                    "invoice_date": "2026-01-15",
                    "invoice_line_ids": [
                        (
                            0,
                            0,
                            {
                                "name": "Linea",
                                "quantity": 1,
                                "price_unit": 10,
                                "tax_ids": [(6, 0, [])],
                            },
                        )
                    ],
                }
            )
        )
        with self.assertRaises(UserError):
            move.action_post()
