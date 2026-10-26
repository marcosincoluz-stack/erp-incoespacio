from odoo.tests.common import TransactionCase


class TestUserGroupsView(TransactionCase):
    def test_it_and_support_rights_are_dropdowns(self):
        classified = self.env["res.groups"].get_groups_by_application()
        kinds = {app: kind for app, kind, _gs, _cat in classified}
        for xmlid in ("module_category_it", "module_category_support"):
            category = self.env.ref("incoespacio_security." + xmlid)
            self.assertEqual(kinds[category], "selection")
