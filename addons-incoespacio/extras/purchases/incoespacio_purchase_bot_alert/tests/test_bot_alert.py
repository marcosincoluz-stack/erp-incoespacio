from odoo.tests.common import TransactionCase


class TestPurchaseBotAlert(TransactionCase):
    def test_bot_create_notifies_and_schedules(self):
        group = self.env.ref(
            "incoespacio_purchase_bot_alert.purchase_bot_alert_group_user"
        )
        user = self.env["res.users"].create(
            {
                "name": "Compras aviso",
                "login": "compras_aviso_test",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("purchase.group_purchase_user").id,
                            group.id,
                        ],
                    )
                ],
            }
        )
        bot = self.env.ref("base.user_root")
        partner = self.env["res.partner"].create({"name": "Proveedor bot"})
        order = (
            self.env["purchase.order"]
            .with_user(bot)
            .create({"partner_id": partner.id})
        )
        self.assertIn("IncoBot", order.message_ids[:1].body)
        activity = self.env["mail.activity"].search(
            [
                ("res_model", "=", "purchase.order"),
                ("res_id", "=", order.id),
                ("user_id", "=", user.id),
            ]
        )
        self.assertTrue(activity)

    def test_human_create_stays_quiet(self):
        partner = self.env["res.partner"].create({"name": "Proveedor humano"})
        order = self.env["purchase.order"].create({"partner_id": partner.id})
        self.assertNotIn("IncoBot", order.message_ids[:1].body or "")
        self.assertFalse(order.activity_ids)
