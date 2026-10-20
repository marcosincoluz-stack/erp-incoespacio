from odoo.tests.common import TransactionCase


class TestPrintLayout(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Cliente obra"})
        cls.product = cls.env["product.product"].create(
            {"name": "Partida", "type": "service", "taxes_id": [(5, 0, 0)]}
        )
        cls.order = cls.env["sale.order"].create({"partner_id": cls.partner.id})
        cls.tax = cls.env["account.tax"].create(
            {
                "name": "IVA 21 layout",
                "amount": 21.0,
                "amount_type": "percent",
                "type_tax_use": "sale",
            }
        )

    def _section(self, seq, code, name, level=0):
        return self.env["sale.order.line"].create(
            {
                "order_id": self.order.id,
                "display_type": "line_section",
                "name": "[%s] %s" % (code, name),
                "bc3_code": code,
                "bc3_level": level,
                "sequence": seq,
            }
        )

    def _partida(self, seq, name, qty, price):
        return self.env["sale.order.line"].create(
            {
                "order_id": self.order.id,
                "product_id": self.product.id,
                "name": name,
                "product_uom_qty": qty,
                "price_unit": price,
                "tax_id": [(6, 0, [])],
                "sequence": seq,
            }
        )

    def _html(self, report="incoespacio_construction_print_layout.report_saleorder_custom"):
        return self.env["ir.actions.report"]._render_qweb_html(
            report, self.order.ids
        )[0].decode()

    def test_custom_table_keeps_code_measures_and_drops_the_pipe(self):
        self._section(1, "00", "DEMOLICION")
        line = self._partida(2, "[00.01] DEMOLICION DE FABRICA", 4.5, 10)
        line.bc3_code = "00.01"
        line.bc3_text = "Texto con barra|\r\n"
        line.product_uom = self.env["uom.uom"].create(
            {
                "name": "Unidades",
                "category_id": self.env.ref("uom.product_uom_categ_unit").id,
                "uom_type": "smaller",
                "factor": 1.0,
            }
        )
        line.bc3_measures = [
            {
                "comment": "Zona norte",
                "units": 1,
                "length": 4.5,
                "width": 0,
                "height": None,
                "partial": 4.5,
            }
        ]
        bare = self._partida(3, "Hecha a mano", 1, 5)
        bare.bc3_measures = [
            {"comment": "", "units": 1, "length": None, "width": None, "height": None, "partial": 1}
        ]
        self.assertFalse(bare._report_measure_rows())
        self.assertEqual(line._print_uom(), "ud")

        self.order.write(
            {
                "print_full_text": True,
                "print_measures": True,
                "print_prices": True,
                "print_code": "project",
            }
        )
        html = self._html()
        self.assertIn("inco-budget-table", html)
        self.assertIn("00.01", html)
        self.assertNotIn("[00.01]", html)
        self.assertIn("DEMOLICION DE FABRICA", html)
        self.assertIn("Zona norte", html)
        self.assertIn("inco-measure-total", html)
        self.assertIn("inco-amount", html)
        self.assertTrue("4.500" in html or "4,500" in html)
        self.assertNotIn("0.000", html)
        self.assertNotIn("0,000", html)
        self.assertIn("Texto con barra", html)
        self.assertNotIn("Texto con barra|", html)
        self.assertIn("PRESUPUESTO Y MEDICIONES", html)
        self.assertNotIn("PEDIDO DE VENTA", html)

        self.order.write({"print_prices": False, "print_summary": False})
        measures = self._html()
        self.assertIn("MEDICIONES", measures)
        self.assertNotIn("PEDIDO DE VENTA", measures)

        self.order.write({"print_only_chapters": True, "print_prices": True, "print_summary": True})
        summary = self._html()
        self.assertIn("RESUMEN DE PRESUPUESTO", summary)
        self.assertIn("100 %", summary)
        self.assertNotIn("DEMOLICION DE FABRICA", summary)
        self.assertNotIn("inco-budget-table", summary)
        self.order.print_summary_pct = False
        hidden = self._html()
        self.assertIn("RESUMEN DE PRESUPUESTO", hidden)
        self.assertNotIn("100 %", hidden)

    def test_chapters_share_one_table_unless_page_break(self):
        self._section(1, "C01", "Uno")
        self._partida(2, "Partida uno", 1, 10)
        self._section(3, "C02", "Dos")
        self._partida(4, "Partida dos", 1, 20)
        html = self._html()
        self.assertEqual(html.count("inco-budget-table"), 1)
        self.assertEqual(html.count("<colgroup>"), 1)
        self.assertIn("Total <span>1</span>", html)
        self.order.print_page_break = True
        broken = self._html()
        self.assertEqual(broken.count("inco-budget-table"), 2)
        self.assertEqual(broken.count("<colgroup>"), 2)

    def test_print_totals_add_general_expenses_and_profit(self):
        self._section(1, "C01", "Obra")
        line = self._partida(2, "Partida", 1, 100)
        line.tax_id = [(6, 0, self.tax.ids)]
        self.order.write({"print_gg_pct": 13, "print_bi_pct": 6})
        totals = self.order._get_print_totals(self.order._get_chapter_summary())
        self.assertAlmostEqual(totals["material"], 100.0)
        self.assertAlmostEqual(totals["gg"], 13.0)
        self.assertAlmostEqual(totals["bi"], 6.0)
        self.assertAlmostEqual(totals["contract"], 119.0)
        self.assertAlmostEqual(totals["tax"], 24.99)
        self.assertAlmostEqual(totals["total"], 143.99)

    def test_normal_pdf_keeps_the_client_card_without_the_code_column(self):
        self._section(1, "C01", "Albañilería")
        self._partida(2, "Tabique", 1, 10)
        self.order.print_summary_pct = False
        self.order.bc3 = True
        self.order.print_code = "project"
        html = self._html("sale.report_saleorder")
        self.assertIn("DATOS DEL CLIENTE", html)
        self.assertIn("Elemento", html)
        self.assertNotIn("inco-budget-table", html)
        self.assertIn("Resumen de presupuesto", html)
        self.assertIn("100 %", html)
        self.assertIn("[1] Albañilería", html)
        self.assertNotIn("[C01]", html)
        custom = self._html()
        self.assertIn("C01", custom)
        self.order.print_code = "decimal"
        decimal = self._html()
        self.assertIn(">1.1<", decimal)
        self.assertNotIn("C01", decimal)
