from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestConstruction(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        income = cls.env["account.account"].search(
            [("account_type", "=", "income"), ("company_id", "=", company.id)],
            limit=1,
        )
        expense = cls.env["account.account"].search(
            [("account_type", "=", "expense"), ("company_id", "=", company.id)],
            limit=1,
        )
        cls.partner = cls.env["res.partner"].create(
            {"name": "Obra Test", "is_company": True}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Partida test",
                "type": "service",
                "invoice_policy": "order",
                "list_price": 100,
                "taxes_id": [(5, 0, 0)],
                "supplier_taxes_id": [(5, 0, 0)],
                "purchase_ok": True,
                "purchase_method": "purchase",
                "property_account_income_id": income.id if income else False,
                "property_account_expense_id": expense.id if expense else False,
            }
        )
        cls.order = cls.env["sale.order"].create(
            {
                "partner_id": cls.partner.id,
                "bc3": True,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": cls.product.id,
                            "product_uom_qty": 10,
                            "price_unit": 100,
                            "tax_id": [(6, 0, [])],
                        },
                    )
                ],
            }
        )

    def test_new_certification_retention_defaults_zero(self):
        self.order.action_confirm()
        action = self.order.action_create_certification()
        cert = self.env["construction.certification"].browse(action["res_id"])
        self.assertEqual(cert.retention_rate, 0.0)
        self.assertFalse(cert.lines_editable)
        cert.action_toggle_lines_editable()
        self.assertTrue(cert.lines_editable)

    def test_retention_return_and_percent(self):
        self.order.action_confirm()
        action = self.order.action_create_certification()
        cert = self.env["construction.certification"].browse(action["res_id"])
        cert.retention_rate = 5.0
        line = cert.line_ids.filtered(lambda l: not l.display_type)
        line.qty_origin = 3
        self.assertAlmostEqual(line.percentage_origin, 30.0)
        cert.action_confirm()
        cert.action_create_invoice()
        self.assertAlmostEqual(self.order.amount_retention_to_return, 15.0)

        action = self.order.action_return_retention()
        move = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(move.move_type, "out_invoice")
        self.assertAlmostEqual(move.amount_untaxed, 15.0)
        self.assertFalse(move.invoice_line_ids.tax_ids)
        self.assertTrue(move.invoice_line_ids.account_id.code.startswith("4308"))
        self.assertIn("Devolución retención", move.ref)

        with self.assertRaises(UserError):
            self.order.action_return_retention()

    def test_confirm_creates_project_once(self):
        self.order.action_confirm()
        project = self.order.project_id
        self.assertTrue(project)
        self.order._ensure_project()
        self.assertEqual(self.order.project_id, project)

    def test_project_open_goes_to_order(self):
        self.order.action_confirm()
        action = self.order.project_id.with_context(
            open_construction_order=1
        ).get_formview_action()
        self.assertEqual(action["res_model"], "sale.order")
        self.assertEqual(action["res_id"], self.order.id)
        plain = self.order.project_id.get_formview_action()
        self.assertEqual(plain["res_model"], "project.project")

    def test_vendor_bill_cost(self):
        self.order.action_confirm()
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "invoice_date": self.order.date_order,
                "project_id": self.order.project_id.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Coste obra",
                            "quantity": 1,
                            "price_unit": 40,
                            "tax_ids": [(6, 0, [])],
                        },
                    )
                ],
            }
        )
        self.assertEqual(bill.construction_order_id, self.order)
        bill.action_post()
        self.order.invalidate_recordset(
            ["amount_job_cost", "amount_job_margin", "amount_certified_origin"]
        )
        self.assertAlmostEqual(self.order.amount_job_cost, 40.0)

    def test_modification_copied_to_cert(self):
        self.order.action_confirm()
        self.order.action_add_modification()
        mod = self.order.order_line.filtered("is_modification")
        self.assertTrue(mod)
        mod.price_unit = 20
        action = self.order.action_create_certification()
        cert = self.env["construction.certification"].browse(action["res_id"])
        cert_mod = cert.line_ids.filtered("is_modification")
        self.assertTrue(cert_mod)
        self.assertTrue(cert_mod.code == "MOD" or cert_mod.name.startswith("["))

    def test_cert_project_follows_order(self):
        self.order.action_confirm()
        action = self.order.action_create_certification()
        cert = self.env["construction.certification"].browse(action["res_id"])
        self.assertEqual(cert.project_id, self.order.project_id)

    def test_cert_keeps_subchapter_level(self):
        self.order.write(
            {
                "order_line": [
                    (0, 0, {"display_type": "line_section", "name": "C01", "bc3_level": 0}),
                    (0, 0, {"display_type": "line_section", "name": "C01A", "bc3_level": 1}),
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "name": "Bajo subcapítulo",
                            "product_uom_qty": 1,
                            "price_unit": 10,
                            "bc3_level": 2,
                            "tax_id": [(6, 0, [])],
                        },
                    ),
                ]
            }
        )
        self.order.action_confirm()
        action = self.order.action_create_certification()
        cert = self.env["construction.certification"].browse(action["res_id"])
        sub = cert.line_ids.filtered(lambda l: l.name == "C01A")
        partida = cert.line_ids.filtered(lambda l: l.name == "Bajo subcapítulo")
        self.assertEqual(sub.bc3_level, 1)
        self.assertEqual(partida.bc3_level, 2)

    def test_report_hides_zero_origin_lines(self):
        self.order.write(
            {
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "display_type": "line_section",
                            "name": "Capítulo vacío",
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "name": "Sin certificar",
                            "product_uom_qty": 8,
                            "price_unit": 50,
                            "tax_id": [(6, 0, [])],
                        },
                    ),
                ],
            }
        )
        self.order.action_confirm()
        action = self.order.action_create_certification()
        cert = self.env["construction.certification"].browse(action["res_id"])
        content = cert.line_ids.filtered(lambda l: not l.display_type)
        content[0].qty_origin = 3
        shown = cert._get_report_lines()
        self.assertIn(content[0], shown)
        self.assertNotIn(content[1], shown)
        self.assertFalse(shown.filtered(lambda l: l.name == "Capítulo vacío"))

    def test_report_name_strips_code_and_truncates(self):
        self.order.action_confirm()
        action = self.order.action_create_certification()
        cert = self.env["construction.certification"].browse(action["res_id"])
        line = cert.line_ids.filtered(lambda l: not l.display_type)[:1]
        line.code = "D01EA020"
        line.name = (
            "[D01EA020] Demolicion de tabique de ladrillo hueco doble por medios "
            "manuales, incluido revestimiento de yeso, mortero, escombros a pie "
            "de carga y demas auxiliares de obra que constan en el pliego."
        )
        short = line._get_report_name()
        self.assertFalse(short.startswith("[D01EA020]"))
        self.assertLessEqual(len(short), 110)
        self.assertTrue(short.endswith("..."))

    def test_certified_over_cost_positive_margin(self):
        self.order.action_confirm()
        action = self.order.action_create_certification()
        cert = self.env["construction.certification"].browse(action["res_id"])
        line = cert.line_ids.filtered(lambda l: not l.display_type)
        line.qty_origin = 5
        cert.action_confirm()
        cert.action_create_invoice()
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "invoice_date": self.order.date_order,
                "project_id": self.order.project_id.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Coste obra",
                            "quantity": 1,
                            "price_unit": 40,
                            "tax_ids": [(6, 0, [])],
                        },
                    )
                ],
            }
        )
        bill.action_post()
        self.order.invalidate_recordset(
            ["amount_job_cost", "amount_job_margin", "amount_certified_origin"]
        )
        self.assertAlmostEqual(self.order.amount_job_cost, 40.0)
        self.assertGreater(self.order.amount_certified_origin, 40.0)
        self.assertGreater(self.order.amount_job_margin, 0.0)

    def test_po_committed_then_invoiced(self):
        self.order.action_confirm()
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.partner.id,
                "project_id": self.order.project_id.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "name": self.product.name,
                            "product_qty": 2,
                            "price_unit": 50,
                            "date_planned": fields.Datetime.now(),
                        },
                    )
                ],
            }
        )
        po.button_confirm()
        self.order.invalidate_recordset(["amount_job_po", "amount_job_cost"])
        self.assertAlmostEqual(self.order.amount_job_po, 100.0)
        self.assertAlmostEqual(self.order.amount_job_cost, 0.0)
        action = po.action_create_invoice()
        bill = self.env["account.move"].browse(action["res_id"])
        bill.invoice_date = fields.Date.context_today(bill)
        bill.action_post()
        self.order.invalidate_recordset(["amount_job_po", "amount_job_cost"])
        self.assertAlmostEqual(self.order.amount_job_po, 0.0)
        self.assertAlmostEqual(self.order.amount_job_cost, 100.0)

    def test_confirm_and_invoice(self):
        self.order.action_confirm()
        action = self.order.action_create_certification()
        cert = self.env["construction.certification"].browse(action["res_id"])
        line = cert.line_ids.filtered(lambda l: not l.display_type)
        line.qty_origin = 2
        cert.action_confirm_and_invoice()
        self.assertEqual(cert.state, "invoiced")
        self.assertTrue(cert.invoice_id)

    def test_confirm_and_invoice_no_period_stays_confirmed(self):
        # El botón confirma y luego factura. Si no hay periodo, UserError de la
        # factura: la cert queda Aprobada (no vuelve a borrador).
        self.order.action_confirm()
        action = self.order.action_create_certification()
        cert = self.env["construction.certification"].browse(action["res_id"])
        cert.action_confirm()
        self.assertEqual(cert.state, "confirmed")
        with self.assertRaises(UserError):
            cert.action_create_invoice()
        self.assertEqual(cert.state, "confirmed")
        self.assertFalse(cert.invoice_id)
        cert.action_draft()
        with self.assertRaises(UserError):
            cert.action_confirm_and_invoice()

    def test_second_confirmed_so_same_project(self):
        self.order.action_confirm()
        project = self.order.project_id
        other = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "bc3": True,
                "project_id": project.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 1,
                            "price_unit": 10,
                            "tax_id": [(6, 0, [])],
                        },
                    )
                ],
            }
        )
        with self.assertRaises(UserError):
            other.action_confirm()
        self.assertEqual(self.order.state, "sale")
        self.assertEqual(self.order.project_id, project)
        self.assertNotEqual(other.state, "sale")
