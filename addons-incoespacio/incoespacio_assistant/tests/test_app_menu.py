from odoo.tests import tagged
from odoo.tests.common import TransactionCase


# Después de instalar todo: así se miran también los menús de la IA.
@tagged("post_install", "-at_install")
class TestIncoBotApp(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.plain = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Usuaria normal",
                    "login": "usuaria.app.incobot",
                    "groups_id": [(6, 0, [cls.env.ref("base.group_user").id])],
                }
            )
        )
        ref = "incoespacio_assistant.%s"
        cls.root = cls.env.ref(ref % "menu_incobot_root")
        cls.mine = cls.env.ref(ref % "menu_my_alerts")
        cls.config = cls.env.ref(ref % "menu_incobot_config")
        cls.admin_only = cls.config | cls.env.ref(ref % "menu_alert_types")
        cls.admin_only |= cls.env.ref(ref % "menu_incobot_settings")

    def _visible(self, user):
        return self.env["ir.ui.menu"].with_user(user)._visible_menu_ids()

    def test_everyone_sees_the_app_with_their_alerts(self):
        visible = self._visible(self.plain)
        self.assertIn(self.root.id, visible)
        self.assertIn(self.mine.id, visible)
        for menu in self.admin_only:
            self.assertNotIn(menu.id, visible)
        self.assertTrue(self.root.web_icon.startswith("incoespacio_assistant,"))

    def test_admins_see_the_configuration(self):
        visible = self._visible(self.env.ref("base.user_admin"))
        for menu in self.root | self.mine | self.admin_only:
            self.assertIn(menu.id, visible)

    def test_nothing_of_ours_left_in_the_settings_menu(self):
        settings = self.env.ref("base.menu_administration")
        ours = self.env["ir.model.data"].search(
            [("module", "like", "incoespacio_assistant%"), ("model", "=", "ir.ui.menu")]
        )
        menus = self.env["ir.ui.menu"].browse(ours.mapped("res_id"))
        self.assertFalse(menus.filtered(lambda m: m.parent_id == settings))
        self.assertEqual(
            self.config.child_id.filtered("action")[-1:].action.context,
            "{'module': 'incoespacio_assistant', 'bin_size': False}",
        )
