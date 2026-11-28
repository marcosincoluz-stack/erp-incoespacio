from datetime import datetime, timedelta

from odoo import fields
from odoo.tests.common import TransactionCase


class TestConstructionAlerts(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # IncoBot está apagado si no se enciende (así arranca al instalar).
        cls.env["ir.config_parameter"].sudo().set_param(
            "incoespacio_assistant.enabled", "True"
        )
        income = cls.env["account.account"].search(
            [
                ("account_type", "=", "income"),
                ("company_id", "=", cls.env.company.id),
            ],
            limit=1,
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Partida",
                "type": "service",
                "taxes_id": [(5, 0, 0)],
                "property_account_income_id": income.id if income else False,
            }
        )
        cls.client = cls.env["res.partner"].create({"name": "Promotora Sur"})
        cls.jefe = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Jefe obras",
                    "login": "jefe.obras.alertas",
                    "groups_id": [
                        (
                            6,
                            0,
                            [
                                cls.env.ref(
                                    "sales_team.group_sale_salesman_all_leads"
                                ).id
                            ],
                        )
                    ],
                }
            )
        )
        ref = "incoespacio_assistant_construction.alert_type_%s"
        cls.to_invoice = cls.env.ref(ref % "cert_to_invoice")
        cls.drafts = cls.env.ref(ref % "cert_draft")
        cls.idle = cls.env.ref(ref % "obra_no_cert")
        cls.today = fields.Date.to_date("2026-11-26")

    def _collect(self, atype):
        rows = atype.with_context(assistant_today=self.today)._collect()
        return {row[0].id: row for row in rows}

    def _obra(self, name, days_ago=0):
        order = self.env["sale.order"].create(
            {
                "partner_id": self.client.id,
                "bc3": True,
                "order_line": [
                    (0, 0, {"product_id": self.product.id, "price_unit": 1000})
                ],
            }
        )
        order.action_confirm()
        order.project_id.write({"name": name, "user_id": self.jefe.id})
        moment = datetime.combine(self.today, datetime.min.time()) + timedelta(
            hours=12, days=-days_ago
        )
        order.date_order = moment
        return order

    def _cert(self, order, days_ago, state="draft"):
        cert = self.env["construction.certification"].create(
            {"order_id": order.id, "date": self.today - timedelta(days=days_ago)}
        )
        if state != "draft":
            cert.state = state
        return cert

    def _backdate(self, cert, days):
        moment = datetime.combine(self.today, datetime.min.time()) + timedelta(
            hours=12, days=-days
        )
        self.env.cr.execute(
            "UPDATE construction_certification SET create_date = %s WHERE id = %s",
            (fields.Datetime.to_string(moment), cert.id),
        )
        cert.invalidate_recordset(["create_date"])

    def test_approved_without_invoice_after_margin(self):
        obra = self._obra("Colegio")
        old = self._cert(obra, 4, "confirmed")
        young = self._cert(obra, 2, "confirmed")
        invoiced = self._cert(obra, 10, "invoiced")
        found = self._collect(self.to_invoice)
        self.assertIn(old.id, found)
        self.assertNotIn(young.id, found)
        self.assertNotIn(invoiced.id, found)
        self.assertEqual(found[old.id][1], self.jefe)
        self.assertIn("Colegio", found[old.id][2])
        self.assertEqual(found[old.id][3], old.date)

    def test_drafts_older_than_a_week(self):
        obra = self._obra("Nave")
        old = self._cert(obra, 0)
        self._backdate(old, 8)
        young = self._cert(obra, 0)
        self._backdate(young, 3)
        found = self._collect(self.drafts)
        self.assertIn(old.id, found)
        self.assertNotIn(young.id, found)
        self.assertEqual((self.today - found[old.id][3]).days, 8)

    def test_idle_obras(self):
        never = self._obra("Sin certificar", days_ago=40)
        recent = self._obra("Al día", days_ago=40)
        self._cert(recent, 5, "invoiced")
        stale = self._obra("Parada", days_ago=90)
        self._cert(stale, 35, "invoiced")
        self._cert(stale, 2, "cancel")
        archived = self._obra("Archivada", days_ago=90)
        archived.project_id.active = False
        young = self._obra("Recién empezada", days_ago=10)
        found = self._collect(self.idle)
        self.assertIn(never.id, found)
        self.assertIn(stale.id, found)
        self.assertNotIn(recent.id, found)
        self.assertNotIn(archived.id, found)
        self.assertNotIn(young.id, found)
        self.assertIn("sin certificaciones", found[never.id][2])
        self.assertIn("última certificación", found[stale.id][2])
        self.assertEqual((self.today - found[stale.id][3]).days, 35)
        self.assertEqual(found[never.id][1], self.jefe)

    # ------------------------------------------------------------------ #
    # Tachar al guardar (incoespacio_assistant_done)
    # ------------------------------------------------------------------ #
    def _run(self):
        self.env["assistant.alert"].with_context(assistant_today=self.today)._cron_run()

    def _alerts(self, atype, record):
        return self.env["assistant.alert"].search(
            [("type_id", "=", atype.id), ("res_id", "=", record.id)]
        )

    def _save(self):
        # Lo que hace el commit: guardar lo pendiente y correr los ganchos.
        self.env.cr.flush()

    def _chat_body(self):
        bot = self.env.ref("incoespacio_assistant.partner_incobot_assistant")
        channel = self.env["discuss.channel"].with_user(self.jefe).channel_get([bot.id])
        return channel.message_ids.filtered(lambda m: m.author_id == bot)[:1].body

    def _admin_role(self, atype):
        # Este tipo no va al jefe de obra, sino al rol de Administración.
        role = self.env["res.users.role"].create(
            {
                "name": "Administración",
                # Los roles fijan los grupos: se mantienen los suyos.
                "implied_ids": [(6, 0, self.jefe.groups_id.ids)],
            }
        )
        self.env["res.users.role.line"].create(
            {"role_id": role.id, "user_id": self.jefe.id}
        )
        atype.role_ids = role

    def test_invoicing_a_cert_strikes_its_alert(self):
        cert = self._cert(self._obra("Colegio"), 4, "confirmed")
        self._admin_role(self.to_invoice)
        self._run()
        alert = self._alerts(self.to_invoice, cert)
        self.assertEqual(alert.user_id, self.jefe)
        cert.with_user(self.jefe).state = "invoiced"
        self._save()
        self.assertEqual(alert.state, "resolved")
        self.assertEqual(alert.resolved_by_id, self.jefe)
        self.assertIn("✓ Hecho", self._chat_body())

    def test_a_new_cert_strikes_the_idle_obra(self):
        obra = self._obra("Sin certificar", days_ago=40)
        self._run()
        alert = self._alerts(self.idle, obra)
        self.assertIn(alert.state, ("new", "open"))
        self.env["construction.certification"].with_user(self.jefe).create(
            {"order_id": obra.id}
        )
        self._save()
        self.assertEqual(alert.state, "resolved")
        self.assertEqual(alert.resolved_by_id, self.jefe)

    def test_deleting_a_draft_strikes_its_alert(self):
        cert = self._cert(self._obra("Nave"), 0)
        self._backdate(cert, 8)
        self._run()
        alert = self._alerts(self.drafts, cert)
        self.assertIn(alert.state, ("new", "open"))
        cert.with_user(self.jefe).unlink()
        self._save()
        self.assertEqual(alert.state, "resolved")
        self.assertIn("✓ Hecho", self._chat_body())

    def test_cancelling_the_obra_strikes_its_alert(self):
        obra = self._obra("Parada", days_ago=40)
        self._run()
        alert = self._alerts(self.idle, obra)
        obra.with_user(self.jefe).write({"state": "cancel"})
        self._save()
        self.assertEqual(alert.state, "resolved")

    def test_saving_an_obra_that_still_needs_it_keeps_the_alert(self):
        obra = self._obra("Sigue parada", days_ago=40)
        self._run()
        alert = self._alerts(self.idle, obra)
        obra.with_user(self.jefe).write({"note": "Llamar al cliente"})
        self._save()
        self.assertIn(alert.state, ("new", "open"))
