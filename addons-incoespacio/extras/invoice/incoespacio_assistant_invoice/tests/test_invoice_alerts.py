from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from odoo import fields
from odoo.tests.common import TransactionCase

_MADRID = ZoneInfo("Europe/Madrid")


class TestInvoiceAlerts(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # IncoBot está apagado si no se enciende (así arranca al instalar).
        cls.env["ir.config_parameter"].sudo().set_param(
            "incoespacio_assistant.enabled", "True"
        )
        company = cls.env.company
        expense = cls.env["account.account"].search(
            [("account_type", "=", "expense"), ("company_id", "=", company.id)],
            limit=1,
        )
        cls.partner = cls.env["res.partner"].create(
            {"name": "Ferretería López", "is_company": True}
        )
        income = cls.env["account.account"].search(
            [("account_type", "=", "income"), ("company_id", "=", company.id)],
            limit=1,
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Material",
                "type": "service",
                "purchase_ok": True,
                "supplier_taxes_id": [(5, 0, 0)],
                "taxes_id": [(5, 0, 0)],
                "property_account_income_id": income.id if income else False,
                "property_account_expense_id": expense.id if expense else False,
            }
        )
        cls.drafts = cls.env.ref(
            "incoespacio_assistant_invoice.alert_type_bill_draft_no_obra"
        )
        cls.partidas = cls.env.ref(
            "incoespacio_assistant_invoice.alert_type_bill_no_partida"
        )
        cls.empty = cls.env.ref(
            "incoespacio_assistant_invoice.alert_type_bill_draft_empty"
        )
        cls.ocr = cls.env.ref(
            "incoespacio_assistant_invoice.alert_type_bill_ocr_failed"
        )
        cls.overdue = cls.env.ref(
            "incoespacio_assistant_invoice.alert_type_invoice_overdue"
        )
        cls.billing = cls.env.ref("account.group_account_invoice")
        cls.jefe = cls._user("Jefe", "jefe.alertas", cls.billing)
        cls.admin = cls._user("Admin facturas", "admin.alertas", cls.billing)
        cls.plain = cls._user("Sin contabilidad", "plain.alertas", False)
        cls.project = cls.env["project.project"].create(
            {"name": "Calle Mayor 12", "user_id": cls.jefe.id}
        )

    @classmethod
    def _user(cls, name, login, group):
        groups = [cls.env.ref("base.group_user").id]
        if group:
            groups.append(group.id)
        return (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": name,
                    "login": login,
                    "email": "%s@example.com" % login,
                    "groups_id": [(6, 0, groups)],
                }
            )
        )

    def _bill(self, **extra):
        vals = {
            "move_type": "in_invoice",
            "partner_id": self.partner.id,
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [
                (
                    0,
                    0,
                    {
                        "name": "Material",
                        "product_id": self.product.id,
                        "quantity": 1,
                        "price_unit": 1240,
                        "tax_ids": [(6, 0, [])],
                    },
                )
            ],
        }
        vals.update(extra)
        return self.env["account.move"].create(vals)

    def _backdate(self, move, days):
        created = datetime.now(_MADRID).replace(
            hour=12, minute=0, second=0, microsecond=0
        ) - timedelta(days=days)
        utc = created.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
        self.env.cr.execute(
            "UPDATE account_move SET create_date = %s WHERE id = %s",
            (fields.Datetime.to_string(utc), move.id),
        )
        move.invalidate_recordset(["create_date"])

    def _ids(self, atype):
        return {row[0].id for row in atype._collect()}

    def test_draft_without_obra_respects_margin_and_flag(self):
        old = self._bill()
        self._backdate(old, 4)
        young = self._bill()
        self._backdate(young, 3)
        excluded = self._bill(construction_not_job=True)
        self._backdate(excluded, 10)
        with_obra = self._bill(project_id=self.project.id)
        self._backdate(with_obra, 10)
        refund = self._bill(move_type="in_refund")
        self._backdate(refund, 5)
        fresh = self._bill()
        self._backdate(fresh, 4)
        found = self._ids(self.drafts)
        self.assertIn(old.id, found)
        self.assertIn(refund.id, found)
        self.assertNotIn(young.id, found)
        self.assertNotIn(excluded.id, found)
        self.assertNotIn(with_obra.id, found)
        rows = {row[0].id: row for row in self.drafts._collect()}
        today = self.env["assistant.alert"]._madrid_today()
        # La antigüedad va como fecha (cuarta pieza), no dentro del texto.
        self.assertEqual((today - rows[old.id][3]).days, 4)
        self.assertEqual((today - rows[refund.id][3]).days, 5)
        self.assertEqual((today - rows[fresh.id][3]).days, 4)
        for row in rows.values():
            self.assertNotIn("pendiente", row[2])

    def test_draft_responsible_is_suggested_manager_if_he_can_read(self):
        bill = self._bill(ocr_obra_suggested_id=self.project.id)
        self._backdate(bill, 6)
        role = self.env["res.users.role"].create(
            {
                "name": "Administración facturas",
                "implied_ids": [
                    (4, self.billing.id),
                    (4, self.env.ref("base.group_user").id),
                ],
            }
        )
        self.env["res.users.role.line"].create(
            {"role_id": role.id, "user_id": self.admin.id}
        )
        self.drafts.role_ids = role
        self.env["assistant.alert"]._cron_run()
        alerts = self.env["assistant.alert"].search(
            [("type_id", "=", self.drafts.id), ("res_id", "=", bill.id)]
        )
        self.assertEqual(set(alerts.user_id.ids), {self.jefe.id, self.admin.id})
        self.assertFalse(alerts.filtered(lambda alert: alert.user_id == self.plain))
        blocked = self._bill(ocr_obra_suggested_id=self.project.id)
        self.project.user_id = self.plain
        self._backdate(blocked, 6)
        self.env["assistant.alert"]._cron_run()
        plain_alerts = self.env["assistant.alert"].search(
            [
                ("type_id", "=", self.drafts.id),
                ("res_id", "=", blocked.id),
                ("user_id", "=", self.plain.id),
            ]
        )
        self.assertFalse(plain_alerts)

    def test_posted_without_partida_and_ocr_error(self):
        posted = self._bill(project_id=self.project.id)
        posted.action_post()
        self.assertIn(posted.id, self._ids(self.partidas))
        self.partidas.since_date = fields.Date.today() + timedelta(days=1)
        self.assertNotIn(posted.id, self._ids(self.partidas))
        self.partidas.since_date = False
        self.assertIn(posted.id, self._ids(self.partidas))
        draft = self._bill(project_id=self.project.id)
        self.assertNotIn(draft.id, self._ids(self.partidas))
        line = posted.invoice_line_ids.filtered(
            lambda item: item.display_type == "product"
        )
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    (0, 0, {"product_id": self.product.id, "product_uom_qty": 1})
                ],
            }
        )
        line.construction_line_id = order.order_line
        self.assertNotIn(posted.id, self._ids(self.partidas))
        failed = self._bill(ocr_status="error", ocr_error_message="no se leyó")
        done = self._bill(ocr_status="done")
        customer = self._bill(move_type="out_invoice", ocr_status="error")
        fixed = self._bill(
            project_id=self.project.id, ocr_status="error", ocr_error_message="x"
        )
        fixed.action_post()
        found = self._ids(self.ocr)
        self.assertIn(failed.id, found)
        self.assertNotIn(done.id, found)
        self.assertNotIn(customer.id, found)
        self.assertNotIn(fixed.id, found)
        message = {row[0].id: row[2] for row in self.ocr._collect()}[failed.id]
        self.assertIn("no se leyó", message)

    def _empty_bill(self, **extra):
        vals = {"move_type": "in_invoice"}
        vals.update(extra)
        return self.env["account.move"].create(vals)

    def test_empty_drafts_have_their_own_alert(self):
        empty = self._empty_bill()
        self._backdate(empty, 3)
        young = self._empty_bill()
        self._backdate(young, 1)
        failed = self._empty_bill(ocr_status="error", ocr_error_message="ilegible")
        self._backdate(failed, 5)
        queued = self._empty_bill(ocr_status="pending")
        self._backdate(queued, 5)
        zero_with_partner = self._bill()
        zero_with_partner.invoice_line_ids.price_unit = 0
        self._backdate(zero_with_partner, 5)
        refund = self._empty_bill(move_type="in_refund")
        self._backdate(refund, 3)
        found = self._ids(self.empty)
        self.assertIn(empty.id, found)
        self.assertIn(refund.id, found)
        self.assertNotIn(young.id, found)
        self.assertNotIn(failed.id, found)
        self.assertNotIn(queued.id, found)
        self.assertNotIn(zero_with_partner.id, found)
        # Un borrador vacío no sale también como «sin obra».
        no_obra = self._ids(self.drafts)
        self.assertNotIn(empty.id, no_obra)
        self.assertIn(zero_with_partner.id, no_obra)
        row = {row[0].id: row for row in self.empty._collect()}[empty.id]
        self.assertIn("creado por", row[2])
        self.assertIn(self.env.user.name, row[2])
        today = self.env["assistant.alert"]._madrid_today()
        self.assertEqual((today - row[3]).days, 3)

    def _sale(self, days_ago, **extra):
        day = self.env["assistant.alert"]._madrid_today() - timedelta(days=days_ago)
        move = self._bill(
            move_type="out_invoice",
            invoice_date=day,
            invoice_date_due=day,
            invoice_payment_term_id=False,
            **extra,
        )
        return move

    def test_overdue_customer_invoices(self):
        overdue = self._sale(10)
        overdue.action_post()
        not_due = self._sale(0)
        not_due.action_post()
        draft = self._sale(10)
        paid = self._sale(20)
        paid.action_post()
        self.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=paid.ids
        ).create({}).action_create_payments()
        found = self._ids(self.overdue)
        self.assertIn(overdue.id, found)
        self.assertNotIn(not_due.id, found)
        self.assertNotIn(draft.id, found)
        self.assertNotIn(paid.id, found)
        row = {row[0].id: row for row in self.overdue._collect()}[overdue.id]
        self.assertIn("sin cobrar", row[2])
        self.assertEqual(row[3], overdue.invoice_date_due)

    # ------------------------------------------------------------------ #
    # Tachar al guardar (incoespacio_assistant_done)
    # ------------------------------------------------------------------ #
    def _admin_role(self, atype):
        role = self.env["res.users.role"].create(
            {
                "name": "Administración %s" % atype.code,
                "implied_ids": [
                    (4, self.billing.id),
                    (4, self.env.ref("base.group_user").id),
                ],
            }
        )
        self.env["res.users.role.line"].create(
            {"role_id": role.id, "user_id": self.admin.id}
        )
        atype.role_ids = role

    def _open_alerts(self, atype, move):
        return self.env["assistant.alert"].search(
            [("type_id", "=", atype.id), ("res_id", "=", move.id)]
        )

    def _save(self):
        # Lo que hace el commit: guardar lo pendiente y correr los ganchos.
        self.env.cr.flush()

    def _chat_body(self, user):
        bot = self.env.ref("incoespacio_assistant.partner_incobot_assistant")
        channel = self.env["discuss.channel"].with_user(user).channel_get([bot.id])
        return channel.message_ids.filtered(lambda m: m.author_id == bot)[:1].body

    def test_saving_the_obra_strikes_the_alert_with_the_name(self):
        bill = self._bill(ocr_obra_suggested_id=self.project.id)
        self._backdate(bill, 6)
        self._admin_role(self.drafts)
        self.env["assistant.alert"]._cron_run()
        alerts = self._open_alerts(self.drafts, bill)
        self.assertEqual(set(alerts.user_id.ids), {self.jefe.id, self.admin.id})
        bill.with_user(self.admin).write({"project_id": self.project.id})
        self._save()
        self.assertEqual(set(alerts.mapped("state")), {"resolved"})
        self.assertEqual(alerts.resolved_by_id, self.admin)
        # Lo tenían dos: los dos mensajes dicen quién lo hizo.
        for user in (self.jefe, self.admin):
            self.assertIn("✓ Hecho por Admin facturas", self._chat_body(user))

    def test_partida_on_a_line_strikes_without_touching_the_bill(self):
        posted = self._bill(project_id=self.project.id)
        posted.action_post()
        self._admin_role(self.partidas)
        self.env["assistant.alert"]._cron_run()
        alerts = self._open_alerts(self.partidas, posted)
        self.assertEqual(set(alerts.user_id.ids), {self.jefe.id, self.admin.id})
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    (0, 0, {"product_id": self.product.id, "product_uom_qty": 1})
                ],
            }
        )
        line = posted.invoice_line_ids.filtered(lambda l: l.display_type == "product")
        line.with_user(self.admin).construction_line_id = order.order_line
        self._save()
        self.assertEqual(set(alerts.mapped("state")), {"resolved"})
        self.assertEqual(alerts.resolved_by_id, self.admin)
        self.assertIn("✓ Hecho por Admin facturas", self._chat_body(self.jefe))

    def test_saving_a_bill_without_alerts_runs_no_rule(self):
        bill = self._bill()
        Type = type(self.env["assistant.alert.type"])
        with patch.object(Type, "_collect", autospec=True) as collect:
            bill.write({"ref": "Otra referencia"})
            self._save()
        collect.assert_not_called()

    def test_a_failing_check_never_blocks_the_save(self):
        bill = self._bill(ocr_obra_suggested_id=self.project.id)
        self._backdate(bill, 6)
        self.env["assistant.alert"]._cron_run()
        alert = self._open_alerts(self.drafts, bill)
        Alert = type(self.env["assistant.alert"])
        with patch.object(Alert, "_still_matching", side_effect=RuntimeError("x")):
            bill.write({"project_id": self.project.id})
            self._save()
        self.assertEqual(bill.project_id, self.project)
        self.assertIn(alert.state, ("new", "open"))

    def test_switched_off_saving_strikes_nothing(self):
        bill = self._bill(ocr_obra_suggested_id=self.project.id)
        self._backdate(bill, 6)
        self.env["assistant.alert"]._cron_run()
        alert = self._open_alerts(self.drafts, bill)
        self.env["ir.config_parameter"].sudo().set_param(
            "incoespacio_assistant.enabled", False
        )
        bill.write({"project_id": self.project.id})
        self._save()
        self.assertIn(alert.state, ("new", "open"))
