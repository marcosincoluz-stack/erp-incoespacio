from odoo import fields
from odoo.tests.common import TransactionCase


class TestMarginsForecast(TransactionCase):
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
        cls.customer = cls.env["res.partner"].create(
            {"name": "Cliente forecast", "is_company": True}
        )
        cls.vendor = cls.env["res.partner"].create(
            {"name": "Proveedor forecast", "is_company": True}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Partida forecast",
                "type": "service",
                "invoice_policy": "order",
                "purchase_ok": True,
                "purchase_method": "purchase",
                "list_price": 100,
                "taxes_id": [(5, 0, 0)],
                "supplier_taxes_id": [(5, 0, 0)],
                "property_account_income_id": income.id if income else False,
                "property_account_expense_id": expense.id if expense else False,
            }
        )
        cls.order = cls.env["sale.order"].create(
            {
                "partner_id": cls.customer.id,
                "bc3": True,
                "planned_percent": 20.0,
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
        cls.line = cls.order.order_line.filtered(lambda l: not l.display_type)
        cls.order.action_confirm()

    def _po(self, amount):
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "project_id": self.order.project_id.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "name": self.product.name,
                            "product_qty": 1,
                            "price_unit": amount,
                            "date_planned": fields.Datetime.now(),
                            "construction_line_id": self.line.id,
                        },
                    )
                ],
            }
        )
        po.button_confirm()
        return po

    def _invoice_cert(self, qty_origin):
        action = self.order.action_create_certification()
        cert = self.env["construction.certification"].browse(action["res_id"])
        line = cert.line_ids.filtered(lambda l: not l.display_type)
        line.qty_origin = qty_origin
        cert.action_confirm()
        cert.action_create_invoice()
        return cert

    def _post_bill(self, price, partida=True):
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.vendor.id,
                "invoice_date": self.order.date_order,
                "project_id": self.order.project_id.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Coste partida",
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": price,
                            "tax_ids": [(6, 0, [])],
                            "construction_line_id": self.line.id if partida else False,
                        },
                    )
                ],
            }
        )
        bill.action_post()
        return bill

    def test_committed_moves_to_invoiced(self):
        po = self._po(300)
        self.line.invalidate_recordset()
        self.order.invalidate_recordset()
        self.assertAlmostEqual(self.line.amount_po_cost, 300.0)
        self.assertAlmostEqual(self.line.amount_cost_incurred, 300.0)
        self.assertAlmostEqual(self.order.amount_po_partida, 300.0)

        action = po.action_create_invoice()
        bill = self.env["account.move"].browse(action["res_id"])
        bill.invoice_date = fields.Date.context_today(bill)
        bill.action_post()
        self.line.invalidate_recordset()
        self.order.invalidate_recordset()
        self.assertAlmostEqual(self.line.amount_po_cost, 0.0)
        self.assertAlmostEqual(self.line.amount_vendor_cost, 300.0)
        self.assertAlmostEqual(self.line.amount_cost_incurred, 300.0)

    def test_forecast_with_certification(self):
        self._invoice_cert(4)
        self._post_bill(400)
        self.line.invalidate_recordset()
        self.order.invalidate_recordset()
        self.assertAlmostEqual(self.line.price_unit_forecast, 100.0)
        self.assertAlmostEqual(self.line.amount_cost_forecast, 1000.0)
        self.assertAlmostEqual(self.line.amount_margin_forecast, 0.0)
        self.assertAlmostEqual(self.order.amount_cost_forecast, 1000.0)
        self.assertAlmostEqual(self.order.margin_percent_forecast, 0.0)

    def test_forecast_without_certification(self):
        self.line.invalidate_recordset()
        self.order.invalidate_recordset()
        self.assertAlmostEqual(self.line.price_planned, 80.0)
        self.assertAlmostEqual(self.line.amount_cost_forecast, 800.0)
        self.assertAlmostEqual(self.line.amount_margin_forecast, 200.0)
        self.assertAlmostEqual(self.order.amount_cost_forecast, 800.0)
        self.assertAlmostEqual(self.order.margin_percent_forecast, 20.0)

    def test_order_for_the_whole_partida_is_not_counted_twice(self):
        # Certificado el 20 % (2 de 10), facturado al ritmo del objetivo (80 €/ud)
        # y pedido el material de lo que falta por 700 €: antes se extrapolaba
        # todo lo incurrido (860 / 2 × 8) y salían 4.300 € de previsión.
        self._invoice_cert(2)
        self._post_bill(160)
        self._po(700)
        self.line.invalidate_recordset()
        self.order.invalidate_recordset()
        # Lo que falta al ritmo real (8 × 80 = 640) es menos que lo pedido: manda
        # el pedido. Previsión = 160 facturado + 700 comprometido.
        self.assertAlmostEqual(self.line.amount_cost_forecast, 860.0)
        self.assertAlmostEqual(self.line.amount_margin_forecast, 140.0)

    def test_order_above_the_pace_raises_the_forecast(self):
        self._invoice_cert(2)
        self._post_bill(160)
        self._po(1000)
        self.line.invalidate_recordset()
        # El pedido supera lo que falta al ritmo real: la previsión sube con él.
        self.assertAlmostEqual(self.line.amount_cost_forecast, 1160.0)

    def test_unassigned_cost_counts_in_the_order_forecast(self):
        self._post_bill(150, partida=False)
        self.line.invalidate_recordset()
        self.order.invalidate_recordset()
        # 800 de la partida al objetivo + 150 sin imputar.
        self.assertAlmostEqual(self.order.amount_cost_forecast, 950.0)
        self.assertAlmostEqual(self.order.amount_margin_forecast, 50.0)

    def _second_partida_with_cost_but_no_progress(self):
        second = self.env["sale.order.line"].create(
            {
                "order_id": self.order.id,
                "product_id": self.product.id,
                "product_uom_qty": 5,
                "price_unit": 100,
                "tax_id": [(6, 0, [])],
            }
        )
        action = self.order.action_create_certification()
        cert = self.env["construction.certification"].browse(action["res_id"])
        cert.line_ids.filtered(
            lambda l: l.sale_order_line_id == self.line
        ).qty_origin = 4
        cert.action_confirm()
        cert.action_create_invoice()
        self._post_bill(400)
        bill = self._post_bill(150)
        bill.button_draft()
        bill.invoice_line_ids.construction_line_id = second
        bill.action_post()
        (self.line | second).invalidate_recordset()
        self.order.invalidate_recordset()
        return second

    def test_cost_without_progress_is_ahead_not_deviation(self):
        second = self._second_partida_with_cost_but_no_progress()
        # La certificada: objetivo ejecutado 4 × 80 = 320 y coste 400.
        self.assertAlmostEqual(self.line.amount_cost_deviation, -80.0)
        self.assertAlmostEqual(self.line.amount_cost_ahead, 0.0)
        # La que no tiene avance: su coste es adelantado, no desviación.
        self.assertAlmostEqual(second.amount_cost_deviation, 0.0)
        self.assertAlmostEqual(second.amount_cost_ahead, 150.0)
        self.assertAlmostEqual(self.order.amount_cost_ahead, 150.0)

    def test_order_deviation_is_the_sum_of_its_partidas(self):
        self._second_partida_with_cost_but_no_progress()
        # Antes la cabecera restaba también los 150 (−230) y no cuadraba con
        # la tabla (−80).
        self.assertAlmostEqual(self.order.amount_cost_deviation, -80.0)

    def test_real_margin_counts_the_unassigned_cost(self):
        self._invoice_cert(4)
        self._post_bill(300)
        self._post_bill(100, partida=False)
        self.line.invalidate_recordset()
        self.order.invalidate_recordset()
        # Certificado 400; coste 300 en la partida + 100 sin imputar.
        self.assertAlmostEqual(self.order.amount_cost_unassigned, 100.0)
        self.assertAlmostEqual(self.order.amount_margin_real, 0.0)
        self.assertAlmostEqual(self.order.margin_percent_real, 0.0)
        # El margen de la pestaña y el de la obra (el que usa IncoBot) coinciden.
        self.assertAlmostEqual(
            self.order.amount_margin_real, self.order.amount_job_margin
        )

    def test_no_objective_means_no_deviation(self):
        self.order.planned_percent = 0.0
        self._invoice_cert(4)
        self._post_bill(300)
        self.line.invalidate_recordset()
        self.order.invalidate_recordset()
        # Antes: objetivo ejecutado 0 − coste 300 = −300, como si fuera sobrecoste.
        self.assertFalse(self.line.price_planned)
        self.assertAlmostEqual(self.line.amount_cost_deviation, 0.0)
        self.assertAlmostEqual(self.order.amount_cost_deviation, 0.0)
        # El margen real sí vale: certificado 400 − coste 300.
        self.assertAlmostEqual(self.line.amount_margin, 100.0)
