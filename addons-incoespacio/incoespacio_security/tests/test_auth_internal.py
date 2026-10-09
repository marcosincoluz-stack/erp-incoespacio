from odoo.addons.auth_signup.models.res_users import SignupError
from odoo.tests.common import TransactionCase


class TestAuthInternal(TransactionCase):
    def test_open_signup_is_rejected_and_create_sends_no_link(self):
        self.assertEqual(self.env["res.users"]._get_signup_invitation_scope(), "b2b")
        with self.assertRaises(SignupError):
            self.env["res.users"].signup(
                {"login": "publico@example.com", "name": "Publico", "password": "secret"}
            )
        user = self.env["res.users"].create(
            {
                "name": "Interno auth",
                "login": "interno_auth_test",
                "email": "interno_auth_test@example.com",
            }
        )
        self.assertFalse(user.partner_id.signup_token)
