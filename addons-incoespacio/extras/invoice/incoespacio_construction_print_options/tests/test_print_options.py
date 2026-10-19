from odoo.tests.common import TransactionCase


class TestPrintOptions(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Obra resumen"})
        cls.product = cls.env["product.product"].create(
            {"name": "Partida", "type": "service", "taxes_id": [(5, 0, 0)]}
        )
        cls.order = cls.env["sale.order"].create(
            {"partner_id": cls.partner.id, "bc3": True}
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

    def _partida(self, seq, qty, price):
        return self.env["sale.order.line"].create(
            {
                "order_id": self.order.id,
                "product_id": self.product.id,
                "name": "Partida %s" % seq,
                "product_uom_qty": qty,
                "price_unit": price,
                "tax_id": [(6, 0, [])],
                "sequence": seq,
            }
        )

    def _html(self, custom=False):
        data = {"custom": True} if custom else None
        return self.env["ir.actions.report"]._render_qweb_html(
            "sale.report_saleorder", self.order.ids, data=data
        )[0].decode()

    def test_chapter_summary_rolls_subchapters_into_parent(self):
        self.assertFalse(self.order._get_chapter_summary())
        self._section(1, "C01", "Albañilería")
        self._partida(2, 2, 100)
        self._section(3, "C01.1", "Tabiques", level=1)
        self._partida(4, 1, 50)
        self._section(5, "C02", "Pintura")
        self._partida(6, 3, 100)

        chapters = self.order._get_chapter_summary()
        self.assertEqual([chapter["code"] for chapter in chapters], ["C01", "C02"])
        self.assertEqual(chapters[0]["name"], "Albañilería")
        self.assertAlmostEqual(chapters[0]["amount"], 250.0)
        self.assertAlmostEqual(chapters[1]["amount"], 300.0)
        self.assertAlmostEqual(sum(chapter["pct"] for chapter in chapters), 100.0)

        plain = self._html()
        self.assertIn("Resumen de presupuesto", plain)
        self.assertIn("Albañilería", plain)
        self.assertIn("DATOS DEL CLIENTE", plain)

    def test_custom_flag_uses_active_ids_when_the_url_drops_docids(self):
        report = self.env["report.sale.report_saleorder"]
        custom = report.with_context(active_ids=self.order.ids)._get_report_values(
            None, data={"custom": True}
        )
        self.assertEqual(custom["docs"], self.order)
        self.assertTrue(custom["custom"])
        plain = report._get_report_values(self.order.ids, data={})
        self.assertEqual(plain["docs"], self.order)
        self.assertFalse(plain["custom"])
        self.assertNotIn("Resumen de presupuesto", self._html())

    def test_range_keeps_chapters_between_and_drops_the_preamble(self):
        self._partida(1, 1, 5)
        first = self._section(2, "C01", "Uno")
        self._partida(3, 1, 10)
        last = self._section(4, "C02", "Dos")
        self._partida(5, 1, 20)
        self._section(6, "C03", "Tres")
        self._partida(7, 1, 30)
        self.order.print_chapter_first_id = first
        self.order.print_chapter_last_id = last

        lines = self.order._get_custom_report_lines()
        self.assertEqual(
            lines.filtered("display_type").mapped("bc3_code"), ["C01", "C02"]
        )
        self.assertNotIn(5.0, lines.mapped("price_unit"))
        summary = self.order._get_chapter_summary(lines)
        self.assertEqual([chapter["code"] for chapter in summary], ["C01", "C02"])
        self.assertAlmostEqual(sum(chapter["pct"] for chapter in summary), 100.0)

    def test_null_partidas_drop_the_subchapter_they_empty(self):
        self._section(1, "C01", "Uno")
        kept = self._partida(2, 1, 10)
        self._section(3, "C01.1", "Sub", level=1)
        self._partida(4, 1, 0)
        self._partida(5, 0, 20)
        self.order.print_hide_null_price = True
        self.order.print_hide_null_qty = True

        lines = self.order._get_custom_report_lines()
        self.assertEqual(lines.filtered(lambda line: not line.display_type), kept)
        self.assertFalse(lines.filtered(lambda line: line.bc3_code == "C01.1"))

    def test_null_chapter_disappears_only_when_asked(self):
        self._section(1, "C01", "Nulo")
        self._partida(2, 1, 0)
        self._section(3, "C02", "Vivo")
        self._partida(4, 1, 50)

        lines = self.order._get_custom_report_lines()
        self.assertEqual(lines.filtered("display_type").mapped("bc3_code"), ["C01", "C02"])
        self.order.print_hide_null_chapters = True
        lines = self.order._get_custom_report_lines()
        self.assertEqual(lines.filtered("display_type").mapped("bc3_code"), ["C02"])
