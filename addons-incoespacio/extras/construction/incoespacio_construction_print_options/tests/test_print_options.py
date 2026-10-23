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
        return (
            self.env["ir.actions.report"]
            ._render_qweb_html("sale.report_saleorder", self.order.ids, data=data)[0]
            .decode()
        )

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
        self.assertEqual([chapter["decimal"] for chapter in chapters], ["1", "2"])

        plain = self._html()
        self.assertIn("Resumen de presupuesto", plain)
        self.assertIn("Albañilería", plain)
        self.assertIn("DATOS DEL CLIENTE", plain)

    def test_decimal_codes_number_chapter_subchapter_and_partida(self):
        chapter = self._section(1, "C01", "Uno")
        sub = self._section(2, "C01A", "Sub", level=1)
        partida = self._partida(3, 1, 10)
        partida.write({"bc3_level": 2, "bc3_code": "UO1", "name": "[UO1] Ladrillo"})
        other = self._section(4, "C02", "Dos")
        direct = self._partida(5, 1, 5)
        direct.bc3_level = 1
        codes = self.order._decimal_codes()
        self.assertEqual(
            [codes[line.id] for line in (chapter, sub, partida, other, direct)],
            ["1", "1.1", "1.1.1", "2", "2.1"],
        )
        html = self._html()
        self.assertIn("[1.1.1] Ladrillo", html)
        self.assertNotIn("[UO1]", html)
        self.assertNotIn("[C01]", html)

    def test_custom_dialog_selects_the_first_and_last_chapter(self):
        first = self._section(1, "C01", "Uno")
        self._section(2, "C01.1", "Sub", level=1)
        self._partida(3, 1, 10)
        last = self._section(4, "C02", "Dos")
        self.order.action_print_custom()
        self.assertEqual(self.order.print_chapter_first_id, first)
        self.assertEqual(self.order.print_chapter_last_id, last)
        self.order.print_chapter_first_id = last
        self.order.action_print_custom()
        self.assertEqual(self.order.print_chapter_first_id, last)

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
        self.assertEqual(
            lines.filtered("display_type").mapped("bc3_code"), ["C01", "C02"]
        )
        self.order.print_hide_null_chapters = True
        lines = self.order._get_custom_report_lines()
        self.assertEqual(lines.filtered("display_type").mapped("bc3_code"), ["C02"])

    def test_certification_pdf_summarizes_the_period_and_signs_presto(self):
        cert = self.env["construction.certification"].create(
            {
                "order_id": self.order.id,
                "number": 1,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "display_type": "line_section",
                            "name": "[C01] Albañilería",
                            "bc3_level": 0,
                            "sequence": 1,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "name": "Tabique",
                            "price_unit": 100,
                            "qty_budget": 2,
                            "qty_origin": 2,
                            "sequence": 2,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "display_type": "line_section",
                            "name": "[C01.1] Interior",
                            "bc3_level": 1,
                            "sequence": 3,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "name": "Ladrillo",
                            "price_unit": 50,
                            "qty_budget": 1,
                            "qty_origin": 1,
                            "sequence": 4,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "display_type": "line_section",
                            "name": "[C02] Pintura",
                            "bc3_level": 0,
                            "sequence": 5,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "name": "Pintar",
                            "price_unit": 10,
                            "qty_budget": 3,
                            "qty_origin": 3,
                            "sequence": 6,
                        },
                    ),
                ],
            }
        )
        chapters = cert._get_chapter_summary()
        self.assertEqual([chapter["decimal"] for chapter in chapters], ["1", "2"])
        self.assertEqual(
            [chapter["name"] for chapter in chapters], ["Albañilería", "Pintura"]
        )
        self.assertAlmostEqual(chapters[0]["amount"], 250.0)
        self.assertAlmostEqual(chapters[1]["amount"], 30.0)
        self.assertEqual(
            cert._cert_amount_words(),
            cert.currency_id.with_context(lang=self.env.lang).amount_to_text(
                cert.amount_period_total
            ),
        )

        html = (
            self.env["ir.actions.report"]
            ._render_qweb_html(
                "incoespacio_construction_certification.report_certification_document",
                cert.ids,
            )[0]
            .decode()
        )
        self.assertIn("Resumen de capítulos", html)
        self.assertIn("page-break-before: always", html)
        self.assertIn("font-size: 9.5px", html)
        self.assertIn("TOTAL PERIODO", html)
        self.assertIn("TOTAL A PERCIBIR", html)
        self.assertIn("Asciende la presente certificación", html)
        self.assertIn("El promotor", html)
        self.assertIn("La dirección facultativa", html)
        self.assertNotIn("LA CONSTRUCTORA", html)

        custom = (
            self.env["ir.actions.report"]
            ._render_qweb_html(
                "incoespacio_construction_certification.report_certification_document",
                cert.ids,
                data={"custom": True},
            )[0]
            .decode()
        )
        self.assertNotIn("Resumen de capítulos", custom)

    def _cert_html(self, cert, custom=False):
        data = {"custom": True} if custom else None
        return (
            self.env["ir.actions.report"]
            ._render_qweb_html(
                "incoespacio_construction_certification.report_certification_document",
                cert.ids,
                data=data,
            )[0]
            .decode()
        )

    def test_custom_pdf_groups_partial_measures_by_certification(self):
        partida = self._partida(1, 10, 100)

        def _cert(number, rows, origin):
            return self.env["construction.certification"].create(
                {
                    "order_id": self.order.id,
                    "number": number,
                    "line_ids": [
                        (
                            0,
                            0,
                            {
                                "sale_order_line_id": partida.id,
                                "name": "Tabique",
                                "price_unit": 100,
                                "qty_budget": 10,
                                "qty_origin": origin,
                                "bc3_cert_measures": rows,
                                "sequence": 1,
                            },
                        )
                    ],
                }
            )

        _cert(1, [{"comment": "Zona A", "units": 2, "partial": 2}], 2)
        second = _cert(2, [{"comment": "Zona B", "units": 2, "partial": 2}], 4)
        groups = second.line_ids._print_measure_groups()
        self.assertEqual([group["cert"] for group in groups], [1, 2])
        self.assertFalse(groups[0]["current"])
        self.assertTrue(groups[1]["current"])
        self.assertAlmostEqual(groups[0]["total"], 2.0)
        self.assertAlmostEqual(groups[1]["total"], 2.0)

        second.print_measures = True
        html = self._cert_html(second, custom=True)
        self.assertIn("Certificación 1", html)
        self.assertIn("Certificación 2 · este periodo", html)
        self.assertIn("Total certificación 1", html)

        second.print_measures = False
        plain = self._cert_html(second, custom=True)
        self.assertNotIn("este periodo", plain)
