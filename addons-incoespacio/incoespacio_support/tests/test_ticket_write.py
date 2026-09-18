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
