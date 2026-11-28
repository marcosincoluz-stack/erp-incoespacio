from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger


def _collect_test_rows(self):
    rows = []
    for item in self.env.context.get("assistant_rows") or []:
        record = self.env[item["model"]].browse(item["id"])
        responsible = self.env["res.users"].browse(item.get("user_id") or 0)
        row = (record, responsible, item.get("message") or record.display_name)
        if item.get("since"):
            row += (fields.Date.to_date(item["since"]),)
        rows.append(row)
    return rows


def _collect_test_boom(self):
    raise RuntimeError("boom")


def _collect_test_sql(self):
    self.env.cr.execute("SELECT * FROM tabla_que_no_existe")
    return []


class AssistantCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # IncoBot está apagado si no se enciende (así arranca al instalar).
        cls.env["ir.config_parameter"].sudo().set_param(
            "incoespacio_assistant.enabled", "True"
        )
        cls.env = cls.env(context=dict(cls.env.context, assistant_today="2026-11-25"))
        model = type(cls.env["assistant.alert.type"])
        cls._model_cls = model
        model._collect_test_rows = _collect_test_rows
        model._collect_test_boom = _collect_test_boom
        model._collect_test_sql = _collect_test_sql
        cls.bot = cls.env.ref("incoespacio_assistant.partner_incobot_assistant")
        cls.ana = cls._user("Ana", "ana.assistant")
        cls.pedro = cls._user("Pedro", "pedro.assistant")
        cls.luis = cls._user("Luis", "luis.assistant")

    @classmethod
    def tearDownClass(cls):
        for name in ("_collect_test_rows", "_collect_test_boom", "_collect_test_sql"):
            if hasattr(cls._model_cls, name):
                delattr(cls._model_cls, name)
        super().tearDownClass()

    @classmethod
    def _user(cls, name, login):
        return (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": name,
                    "login": login,
                    "email": "%s@example.com" % login,
                    "groups_id": [(6, 0, [cls.env.ref("base.group_user").id])],
                }
            )
        )

    def _type(self, code, collector="_collect_test_rows", **extra):
        vals = {
            "name": extra.pop("name", code),
            "code": code,
            "collector": collector,
        }
        vals.update(extra)
        return self.env["assistant.alert.type"].create(vals)

    def _role(self, atype, users):
        role = self.env["res.users.role"].create(
            {
                "name": "Rol %s" % atype.code,
                "implied_ids": [(4, self.env.ref("base.group_user").id)],
            }
        )
        for user in users:
            self.env["res.users.role.line"].create(
                {"role_id": role.id, "user_id": user.id}
            )
        atype.role_ids = [(4, role.id)]
        return role

    def _partner(self, name):
        return self.env["res.partner"].create({"name": name})

    def _row(self, record, user=None, message=None, since=None):
        return {
            "model": record._name,
            "id": record.id,
            "user_id": user.id if user else False,
            "message": message or record.display_name,
            "since": since,
        }

    def _run(self, rows, today=None):
        ctx = {"assistant_rows": rows}
        if today:
            ctx["assistant_today"] = today
        return self.env["assistant.alert"].with_context(**ctx)._cron_run()

    def _alerts(self, user=None):
        domain = [("user_id", "=", user.id)] if user else []
        return self.env["assistant.alert"].search(domain)

    def _chats(self, user):
        return (
            self.env["discuss.channel"]
            .search(
                [
                    ("channel_type", "=", "chat"),
                    ("channel_member_ids.partner_id", "=", self.bot.id),
                    ("channel_member_ids.partner_id", "=", user.partner_id.id),
                ]
            )
            .filtered(
                lambda channel: (
                    set(channel.channel_member_ids.partner_id.ids)
                    == {self.bot.id, user.partner_id.id}
                )
            )
        )

    def _bodies(self, user):
        return self._chats(user).message_ids.filtered(
            lambda message: message.author_id == self.bot
        )


class TestAssistant(AssistantCase):
    def test_recipients_role_responsible_and_archive(self):
        partner = self._partner("Factura")
        atype = self._type("union", notify_responsible=True)
        self._role(atype, self.ana | self.pedro)
        self._run([self._row(partner, self.pedro)])
        self.assertEqual(self._alerts(self.ana).res_id, partner.id)
        self.assertEqual(len(self._alerts(self.pedro)), 1)
        self.assertFalse(self._alerts(self.luis))

        self.pedro.active = False
        self._run([self._row(partner, self.pedro)])
        self.assertFalse(
            self._alerts(self.pedro).filtered(lambda alert: alert.state != "resolved")
        )
        self.assertEqual(self._alerts(self.ana).state, "open")

    def test_without_role_or_responsible_creates_nothing(self):
        partner = self._partner("Sola")
        self._type("vacio", notify_responsible=False)
        self._run([self._row(partner, self.ana)])
        self.assertFalse(self._alerts())

    def test_user_without_access_is_skipped(self):
        secret = (
            self.env["discuss.channel"]
            .with_user(self.ana)
            .channel_get([self.pedro.partner_id.id])
        )
        atype = self._type("secreto", notify_responsible=False)
        self._role(atype, self.ana | self.luis)
        self._run([self._row(secret, message="Canal secreto")])
        self.assertTrue(self._alerts(self.ana))
        self.assertFalse(self._alerts(self.luis))

    def test_lifecycle_dedup_resolve_reopen_snooze(self):
        partner = self._partner("Ciclo")
        atype = self._type("ciclo", notify_responsible=False)
        self._role(atype, self.ana)
        row = [self._row(partner)]
        self._run(row)
        alert = self._alerts(self.ana)
        self.assertEqual(len(alert), 1)
        self.assertEqual(alert.state, "open")
        self.assertIn("🆕", self._bodies(self.ana).body)
        self._run(row)
        self.assertEqual(len(self._alerts(self.ana)), 1)
        self._run([])
        self.assertEqual(alert.state, "resolved")
        # Sin novedades no se vuelve a escribir.
        self.assertEqual(len(self._bodies(self.ana)), 1)
        self._run(row)
        self.assertEqual(alert.state, "open")
        alert.with_user(self.ana).action_snooze_week()
        self.assertEqual(alert.state, "snoozed")
        sent = len(self._bodies(self.ana))
        self._run(row)
        self.assertEqual(alert.state, "snoozed")
        self.assertEqual(len(self._bodies(self.ana)), sent)
        alert.snooze_until = "2026-11-25"
        self._run(row)
        self.assertEqual(alert.state, "open")
        self.assertEqual(len(self._bodies(self.ana)), sent + 1)

    def test_chat_is_reused_and_silence_skips_the_message(self):
        partner = self._partner("Chat")
        atype = self._type("chat", notify_responsible=False)
        atype.hint = "Haz esto"
        self._role(atype, self.ana)
        self._run([self._row(partner, message="FAC-1 · Proveedor · 10 €")])
        channel = self._chats(self.ana)
        self.assertEqual(len(channel), 1)
        members = set(channel.channel_member_ids.partner_id.ids)
        self.assertEqual(members, {self.bot.id, self.ana.partner_id.id})
        root = self.env.ref("base.user_root").partner_id
        self.assertNotIn(root.id, members)
        body = self._bodies(self.ana).body
        self.assertIn("no responde mensajes", body)
        # El chat abre la ficha con data-oe-model/id; el href solo no basta.
        self.assertIn('data-oe-model="res.partner"', body)
        self.assertIn('data-oe-id="%s"' % partner.id, body)
        # La chapa solo envuelve el número; el resto va como texto.
        self.assertIn('class="o_incobot_link"', body)
        self.assertIn(">FAC-1</a> · Proveedor · 10 €", body)
        self.assertIn("→ Haz esto", body)
        self._run([self._row(partner)], today="2026-11-30")
        self.assertEqual(self._chats(self.ana), channel)
        self.assertEqual(len(self._bodies(self.ana)), 2)
        self._run([], today="2026-11-30")
        self.assertEqual(len(self._bodies(self.ana)), 2)
        self.ana.assistant_muted_type_ids = atype
        self._run([self._row(partner)], today="2026-11-30")
        self.assertEqual(len(self._bodies(self.ana)), 2)
        self.assertEqual(self._alerts(self.ana).state, "new")

    def test_cap_age_and_collector_failure(self):
        atype = self._type("tope", notify_responsible=False, name="Tope")
        self._role(atype, self.ana)
        partners = self.env["res.partner"].browse()
        # browse() on empty then union
        rows = []
        for index in range(12):
            partner = self._partner("Pieza %s" % index)
            partners |= partner
            rows.append(self._row(partner))
        self._run(rows)
        body = self._bodies(self.ana)[:1].body
        self.assertIn("y 2 más", body)
        self.assertIn("12", body)
        self._alerts(self.ana).write(
            {"first_seen": "2026-11-19", "pending_since": "2026-11-19"}
        )
        self._run(rows, today="2026-11-30")
        latest = self._bodies(self.ana).sorted("id")[-1].body
        self.assertIn("pendiente desde hace 11 días", latest)
        self.assertNotIn("🆕", latest)
        boom = self._type("boom", collector="_collect_test_boom", name="Boom")
        kept = self.env["assistant.alert"].create(
            {
                "type_id": boom.id,
                "user_id": self.ana.id,
                "res_model": "res.partner",
                "res_id": partners[0].id,
                "message": "no tocar",
                "state": "open",
                "first_seen": "2026-11-25",
                "last_seen": "2026-11-25",
            }
        )
        self._run(rows)
        self.assertEqual(kept.state, "open")

    def test_user_can_only_snooze_own_alerts(self):
        partner = self._partner("Mio")
        atype = self._type("mio", notify_responsible=False)
        self._role(atype, self.ana | self.pedro)
        self._run([self._row(partner)])
        own = self._alerts(self.ana)
        other = self._alerts(self.pedro)
        self.assertEqual(
            len(self.env["assistant.alert"].with_user(self.ana).search([])), 1
        )
        with self.assertRaises(AccessError):
            own.with_user(self.ana).write({"message": "no"})
        with self.assertRaises(AccessError):
            own.with_user(self.ana).unlink()
        with self.assertRaises(AccessError):
            own.with_user(self.ana).write({"state": "resolved"})
        with self.assertRaises(AccessError):
            self.env["assistant.alert"].with_user(self.ana).create(
                {
                    "type_id": atype.id,
                    "user_id": self.ana.id,
                    "res_model": "res.partner",
                    "res_id": partner.id,
                    "message": "no",
                    "first_seen": "2026-11-25",
                    "last_seen": "2026-11-25",
                }
            )
        own.with_user(self.ana).action_snooze_day()
        self.assertEqual(own.state, "snoozed")
        self.assertFalse(
            self.env["assistant.alert"]
            .with_user(self.ana)
            .search([("id", "=", other.id)])
        )

    def test_sql_error_in_collector_does_not_abort_the_run(self):
        partner = self._partner("Superviviente")
        bad = self._type("sql", collector="_collect_test_sql", name="SQL")
        self._role(bad, self.ana)
        good = self._type("bueno", notify_responsible=False, sequence=99)
        self._role(good, self.ana)
        with mute_logger(
            "odoo.sql_db", "odoo.addons.incoespacio_assistant.models.alert"
        ):
            self._run([self._row(partner)])
        self.assertEqual(self._alerts(self.ana).type_id, good)
        self.assertEqual(len(self._bodies(self.ana)), 1)

    def test_collector_must_use_the_prefix(self):
        atype = self._type("peligro", collector="unlink")
        self._role(atype, self.ana)
        with mute_logger("odoo.addons.incoespacio_assistant.models.alert"):
            self._run([])
        self.assertTrue(atype.exists())

    def test_oldest_first_from_pending_since(self):
        atype = self._type("antiguedad", notify_responsible=False, name="Antigüedad")
        self._role(atype, self.ana)
        dates = {"Ocho": "2026-11-17", "Cinco": "2026-11-20", "Diez": "2026-11-15"}
        rows = [
            self._row(self._partner(name), message=name, since=since)
            for name, since in dates.items()
        ]
        self._run(rows)
        body = self._bodies(self.ana).body
        self.assertLess(body.index("Diez"), body.index("Ocho"))
        self.assertLess(body.index("Ocho"), body.index("Cinco"))
        self.assertIn("pendiente desde hace 10 días", body)
        self.assertIn("pendiente desde hace 5 días", body)
        alert = self._alerts(self.ana).filtered(lambda a: a.message == "Diez")
        self.assertEqual(str(alert.pending_since), "2026-11-15")

    def test_three_piece_collector_and_one_day(self):
        atype = self._type("tres", notify_responsible=False)
        self._role(atype, self.ana)
        partner = self._partner("Tres piezas")
        self._run([self._row(partner)])
        alert = self._alerts(self.ana)
        self.assertEqual(alert.pending_since, alert.first_seen)
        alert.pending_since = "2026-11-29"
        self._run([self._row(partner)], today="2026-11-30")
        latest = self._bodies(self.ana).sorted("id")[-1].body
        self.assertIn("pendiente desde hace 1 día", latest)
        self.assertNotIn("1 días", latest)

    def test_only_writes_with_news_and_full_recap_on_monday(self):
        atype = self._type("novedad", notify_responsible=False)
        self._role(atype, self.ana)
        first, second = self._partner("Primera"), self._partner("Segunda")
        self._run([self._row(first)], today="2026-11-25")
        self.assertEqual(len(self._bodies(self.ana)), 1)
        self.assertIn("(1 nuevo)", self._bodies(self.ana).body)
        self._run([self._row(first)], today="2026-11-26")
        self.assertEqual(len(self._bodies(self.ana)), 1)
        self._run([self._row(first), self._row(second)], today="2026-11-27")
        self.assertEqual(len(self._bodies(self.ana)), 2)
        latest = self._bodies(self.ana).sorted("id")[-1].body
        self.assertIn("Primera", latest)
        self.assertIn("Segunda", latest)
        self._run([self._row(first), self._row(second)], today="2026-11-30")
        self.assertEqual(len(self._bodies(self.ana)), 3)
        latest = self._bodies(self.ana).sorted("id")[-1].body
        self.assertIn("Repaso de los lunes", latest)

    def test_snooze_return_counts_as_news(self):
        atype = self._type("vuelve", notify_responsible=False)
        self._role(atype, self.ana)
        partner = self._partner("Pospuesta")
        self._run([self._row(partner)], today="2026-11-25")
        alert = self._alerts(self.ana)
        alert.with_user(self.ana).action_snooze_day()
        self._run([self._row(partner)], today="2026-11-26")
        # Vuelve como nuevo, se envía y queda abierto.
        self.assertEqual(alert.state, "open")
        self.assertEqual(len(self._bodies(self.ana)), 2)

    def test_opening_my_alerts_resolves_what_was_fixed(self):
        atype = self._type("vivo")
        self._role(atype, self.ana | self.luis)
        fixed, pending = self._partner("Arreglada"), self._partner("Pendiente")
        self._run([self._row(fixed), self._row(pending)])
        # Ana arregla una durante el día: la regla ya solo ve la otra.
        alerts = self.env["assistant.alert"].with_context(
            assistant_rows=[self._row(pending)]
        )
        action = alerts.with_user(self.ana).action_open_my_alerts()
        self.assertEqual(action["res_model"], "assistant.alert")
        states = {
            (alert.user_id, alert.res_id): alert.state for alert in self._alerts()
        }
        for user in (self.ana, self.luis):
            # Resuelta para todos los que la tenían, no solo para Ana.
            self.assertEqual(states[(user, fixed.id)], "resolved")
            self.assertIn(states[(user, pending.id)], ("new", "open"))

    def test_broken_rule_does_not_resolve_on_open(self):
        atype = self._type("roto", collector="_collect_test_rows")
        self._role(atype, self.ana)
        partner = self._partner("Rota")
        self._run([self._row(partner)])
        atype.collector = "_collect_test_boom"
        with mute_logger("odoo.addons.incoespacio_assistant.models.alert"):
            self.env["assistant.alert"].with_user(self.ana).action_open_my_alerts()
        self.assertIn(self._alerts(self.ana).state, ("new", "open"))


class TestSwitch(AssistantCase):
    def test_switched_off_sends_nothing(self):
        atype = self._type("apagado")
        self._role(atype, self.ana)
        self.env["ir.config_parameter"].sudo().set_param(
            "incoespacio_assistant.enabled", False
        )
        self._run([self._row(self._partner("Apagado"))])
        self.assertFalse(self._alerts(self.ana))
        self.assertFalse(self._bodies(self.ana))
