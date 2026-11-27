from odoo.addons.incoespacio_assistant.tests.test_assistant import AssistantCase


class TestSummary(AssistantCase):
    def _director(self, name, login):
        user = self._user(name, login)
        role = self.env["res.users.role"].create(
            {
                "name": "Dirección %s" % login,
                "implied_ids": [(4, self.env.ref("base.group_user").id)],
            }
        )
        self.env["res.users.role.line"].create({"role_id": role.id, "user_id": user.id})
        self.env["ir.config_parameter"].sudo().set_param(
            "incoespacio_assistant.summary_role_ids", str(role.id)
        )
        return user

    def _resolved(self, atype, first_seen, resolved_date, message="cerrado"):
        return self.env["assistant.alert"].create(
            {
                "type_id": atype.id,
                "user_id": self.ana.id,
                "res_model": "res.partner",
                "res_id": self._partner(message).id,
                "message": message,
                "state": "resolved",
                "first_seen": first_seen,
                "last_seen": resolved_date,
                "resolved_date": resolved_date,
            }
        )

    def _text(self, user):
        return " ".join(" ".join(self._bodies(user).mapped("body")).split())

    def test_summary_counts_matters_not_people(self):
        partner = self._partner("Asunto")
        atype = self._type("resumen", notify_responsible=True, name="Huecos")
        role = self._role(atype, self.ana | self.pedro)
        direction = self._director("Dirección", "direccion.assistant")
        # Lo resuelto esta semana cuenta; lo del lunes pasado ya salió entonces.
        self._resolved(atype, "2026-11-20", "2026-11-27", "esta semana")
        self._resolved(atype, "2026-11-16", "2026-11-23", "lunes pasado")
        self._run([self._row(partner, self.pedro, "Hueco único")], today="2026-11-30")
        body = self._text(direction)
        visible = self.env["assistant.alert"].with_user(direction).search([])
        self.assertGreaterEqual(len(visible), 2)
        self.assertIn("Resumen del 30/11/2026", body)
        self.assertIn("Huecos", body)
        self.assertIn(">1<", body)
        self.assertNotIn(">2<", body)
        self.assertNotIn("Ana:", body)
        self.assertIn("Resueltos desde el último resumen: 1", body)
        self.assertIn(role.name, self._alerts(self.ana).type_id.role_ids.name)

    def test_monday_counts_what_was_fixed_over_the_weekend(self):
        atype = self._type("finde", name="Finde")
        self._role(atype, self.ana)
        partner = self._partner("Arreglado el sábado")
        self._run([self._row(partner)], today="2026-11-20")
        direction = self._director("Lunes finde", "finde.assistant")
        self._run([], today="2026-11-23")
        self.assertIn("Resueltos desde el último resumen: 1", self._text(direction))

    def test_monday_week_and_weekend_skip(self):
        atype = self._type("semana", name="Semanal")
        self._resolved(atype, "2026-11-16", "2026-11-20", "de la semana")
        self._resolved(atype, "2026-11-10", "2026-11-16", "del lunes pasado")
        direction = self._director("Lunes", "lunes.assistant")
        self._run([], today="2026-11-23")
        body = self._text(direction)
        self.assertIn("Semana", body)
        self.assertIn("lunes pasado", body)
        self.assertIn("1 resueltos, media 4", body)
        before = len(self._alerts())
        self._run([self._row(self._partner("Sabado"))], today="2026-11-28")
        self.assertEqual(len(self._alerts()), before)

    def test_regular_user_sees_only_own_alerts(self):
        atype = self._type("propios", notify_responsible=False)
        self._role(atype, self.ana | self.pedro)
        self._run([self._row(self._partner("Propio"))])
        self._director("Dirección propia", "propia.assistant")
        mine = self.env["assistant.alert"].with_user(self.ana).search([])
        self.assertEqual(mine.user_id, self.ana)

    def test_stuck_uses_pending_since_not_the_text(self):
        atype = self._type("atasco", name="Atascos")
        self._role(atype, self.ana)
        direction = self._director("Dirección atasco", "atasco.assistant")
        old = self._partner("Vieja")
        new = self._partner("Reciente")
        self._run(
            [
                self._row(old, message="Factura vieja", since="2026-11-05"),
                self._row(new, message="hace 99 días en el texto", since="2026-11-24"),
            ],
            today="2026-11-30",
        )
        body = self._text(direction)
        self.assertLess(body.index("Factura vieja"), body.index("hace 99 días"))
        self.assertIn('data-oe-id="%s"' % old.id, body)
        self.assertIn("Atascos, 25 días. Le toca a:", body)
        self.assertIn("<td>1</td>", body.replace(" ", ""))

    def test_summary_only_on_mondays(self):
        atype = self._type("lunes", name="Solo lunes")
        self._role(atype, self.ana)
        direction = self._director("Dirección lunes", "sololunes.assistant")
        partner = self._partner("Abierto")
        for day in ("2026-11-24", "2026-11-25", "2026-11-26", "2026-11-27"):
            self._run([self._row(partner)], today=day)
        self.assertFalse(self._bodies(direction))
        self._run([self._row(partner)], today="2026-11-30")
        self.assertEqual(len(self._bodies(direction)), 1)

    def test_all_alerts_menu_only_for_admins(self):
        menu = self.env.ref("incoespacio_assistant_summary.menu_all_alerts")
        Menu = self.env["ir.ui.menu"]
        self.assertEqual(
            menu.parent_id, self.env.ref("incoespacio_assistant.menu_incobot_root")
        )
        self.assertNotIn(menu.id, Menu.with_user(self.ana)._visible_menu_ids())
        admin = self.env.ref("base.user_admin")
        self.assertIn(menu.id, Menu.with_user(admin)._visible_menu_ids())
