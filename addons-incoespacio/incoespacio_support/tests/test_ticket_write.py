from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase


class TestTicketWrite(TransactionCase):
    def test_user_cannot_write_state(self):
        user = self.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "Usuario tickets",
                "login": "ticket_user_s1",
                "email": "ticket_user_s1@example.com",
                "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        ticket_type = self.env.ref("incoespacio_support.ticket_type_question")
        own = (
            self.env["incoespacio_support.ticket"]
            .with_user(user)
            .create(
                {
                    "title": "Mio",
                    "type_id": ticket_type.id,
                    "user_id": user.id,
                }
            )
        )
        with self.assertRaises(UserError):
            own.with_user(user).write({"state": "working"})

        other = self.env["incoespacio_support.ticket"].create(
            {
                "title": "Ajeno",
                "type_id": ticket_type.id,
            }
        )
        try:
            other.with_user(user).write({"state": "working"})
        except (AccessError, UserError):
            return
        self.fail("expected AccessError or UserError on foreign ticket")

    def test_transition_chatter_renders_html(self):
        ticket = self.env["incoespacio_support.ticket"].create(
            {
                "title": "Prueba",
                "type_id": self.env.ref("incoespacio_support.ticket_type_question").id,
            }
        )
        ticket.button_working()
        bodies = "".join(ticket.message_ids.mapped("body"))
        self.assertIn("<b>", bodies)
        self.assertNotIn("&lt;b&gt;", bodies)

    def test_fix_seed_mojibake(self):
        cat = self.env.ref("incoespacio_support.ticket_cat_it")
        erp = self.env.ref("incoespacio_support.ticket_cat_erp")
        err = self.env.ref("incoespacio_support.ticket_type_error")
        cat.name = "Inform?tica / Conectividad"
        erp.name = "ERP & Facturaci?n"
        err.name = "Error cr?tico"
        self.env["incoespacio_support.ticket"]._fix_seed_mojibake()
        self.assertEqual(cat.name, "Informática / Conectividad")
        self.assertEqual(erp.name, "ERP & Facturación")
        self.assertEqual(err.name, "Error crítico")

    def test_fix_escaped_chatter(self):
        ticket = self.env["incoespacio_support.ticket"].create(
            {
                "title": "Prueba",
                "type_id": self.env.ref("incoespacio_support.ticket_type_question").id,
            }
        )
        msg = ticket.message_post(body="n")
        self.env.cr.execute(
            "UPDATE mail_message SET body = %s WHERE id = %s",
            ("<p>El ticket &lt;b&gt;X&lt;/b&gt;</p>", msg.id),
        )
        msg.invalidate_recordset()
        self.env["incoespacio_support.ticket"]._fix_seed_mojibake()
        self.assertIn("<b>", msg.body)
        self.assertNotIn("&lt;b&gt;", msg.body)
