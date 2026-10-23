import base64

from odoo.tests.common import TransactionCase, tagged

_HEADER = b"~V|SOFT|FIEBDC-3/2020|Test||ANSI|\n"
_BASE = _HEADER + (
    b"~C|C01#||Albanileria|0||0|\n"
    b"~D|C01#|37.5\\1\\1\\TAB01\\1\\1\\MAT01\\1\\1\\MO01\\1\\1\\AUX%\\1\\1\\|\n"
    b"~C|37.5|m2|DESMONTAJE CARPINTERIAS|12.50||0|\n"
    b"~T|37.5|Texto largo de desmontaje|\n"
    b"~C|TAB01|m2|Tabique de ladrillo|25.00||EU|\n"
    b"~C|MAT01|ud|Ladrillo hueco|0.15||3|\n"
    b"~C|MO01|h|Oficial|18.00||1|\n"
    b"~C|AUX%|%|Medios auxiliares|1||0|\n"
)
_BUDGET = _HEADER + (
    b"~C|C01#||Cap|0||0|\n"
    b"~D|C01#|37.5\\1\\1\\ZZZ\\1\\1\\|\n"
    b"~C|37.5|m2|DESMONTAJE|99.00||0|\n"
    b"~T|37.5|Texto del presupuesto|\n"
    b"~C|ZZZ|ud|No esta|5.00||0|\n"
)


class TestPriceDbSuggest(TransactionCase):
    def _import(self, raw):
        wizard = self.env["bc3.price.import.wizard"].create(
            {"bc3_file": base64.b64encode(raw), "bc3_file_name": "base.bc3"}
        )
        return wizard.action_import()

    def test_sale_line_fills_from_product(self):
        self._import(_BASE)
        product = self.env["product.product"].search(
            [("default_code", "=", "37.5")], limit=1
        )
        partner = self.env["res.partner"].create({"name": "Cliente obra"})
        order = self.env["sale.order"].create({"partner_id": partner.id})
        line = self.env["sale.order.line"].create(
            {"order_id": order.id, "product_id": product.id}
        )
        self.assertEqual(line.bc3_code, "37.5")
        self.assertEqual(line.bc3_text, "Texto largo de desmontaje")
        self.assertAlmostEqual(line.price_unit, 12.5)
        self.assertEqual(line.product_uom, product.uom_id)
        self.assertEqual(line.name, product.name)
        self.assertNotIn("[", line.name)
        self.assertNotIn("Texto largo", line.name)

    def test_linked_code_snaps_back(self):
        self._import(_BASE)
        product = self.env["product.product"].search(
            [("default_code", "=", "37.5")], limit=1
        )
        partner = self.env["res.partner"].create({"name": "Cliente obra"})
        order = self.env["sale.order"].create({"partner_id": partner.id})
        line = self.env["sale.order.line"].create(
            {"order_id": order.id, "product_id": product.id}
        )
        line.write({"bc3_code": ""})
        self.assertEqual(line.bc3_code, "37.5")
        line.write({"bc3_code": "OTRO"})
        self.assertEqual(line.bc3_code, "37.5")
        loose = self.env["sale.order.line"].create(
            {
                "order_id": order.id,
                "product_id": self.env.ref(
                    "bc3_importer.product_product_product_units"
                ).id,
                "bc3_code": "ZZZ",
            }
        )
        loose.write({"bc3_code": "LIBRE"})
        self.assertEqual(loose.bc3_code, "LIBRE")

    def test_budget_keeps_bc3_title_unlinked(self):
        self._import(_BASE)
        catalog = self.env["product.product"].search(
            [("default_code", "=", "37.5")], limit=1
        )
        partner = self.env["res.partner"].create({"name": "Cliente obra"})
        wizard = self.env["bc3.import.wizard"].create(
            {
                "bc3_file": base64.b64encode(_BUDGET),
                "bc3_file_name": "obra.bc3",
                "partner_id": partner.id,
                "version_id": self.env.ref("bc3_importer.bc3_version_2020_v2").id,
            }
        )
        wizard.do_action()
        lines = wizard.sale_id.order_line.filtered(lambda line: not line.display_type)
        hit = lines.filtered(lambda line: line.bc3_code == "37.5")
        miss = lines.filtered(lambda line: line.bc3_code == "ZZZ")
        self.assertNotEqual(hit.product_id, catalog)
        self.assertEqual(hit.product_id.name, "Sin vincular (m²)")
        self.assertAlmostEqual(hit.price_unit, 99.0)
        self.assertIn("DESMONTAJE", hit.name)
        self.assertEqual(hit.product_uom, hit.product_id.uom_id)
        self.assertEqual(miss.product_id.name, "Sin vincular (ud)")
        square = self.env.ref("bc3_importer.product_product_product_square_meter")
        self.assertEqual(square.with_context(lang="es_ES").name, "Sin vincular (m²)")
        copy = self.env.ref("bc3_importer.product_product_product_template_square_meter")
        self.assertFalse(copy.sale_ok)
        self.assertEqual(copy.with_context(lang="es_ES").name, "Sin vincular (m²)")
        self.env.add_to_compute(miss._fields["bc3_code"], miss)
        miss.flush_recordset(["bc3_code"])
        self.assertEqual(miss.bc3_code, "ZZZ")


@tagged("post_install", "-at_install")
class TestPriceDbSuggestCertification(TransactionCase):
    def test_certification_copies_linked_line(self):
        TestPriceDbSuggest._import(self, _BASE)
        partner = self.env["res.partner"].create({"name": "Cliente obra"})
        wizard = self.env["bc3.import.wizard"].create(
            {
                "bc3_file": base64.b64encode(_BUDGET),
                "bc3_file_name": "obra.bc3",
                "partner_id": partner.id,
                "version_id": self.env.ref("bc3_importer.bc3_version_2020_v2").id,
            }
        )
        wizard.do_action()
        order = wizard.sale_id
        action = order.action_create_certification()
        cert = self.env["construction.certification"].browse(action["res_id"])
        hit = cert.line_ids.filtered(lambda line: line.code == "37.5")
        miss = cert.line_ids.filtered(lambda line: line.code == "ZZZ")
        self.assertTrue(hit)
        self.assertAlmostEqual(hit.price_unit, 99.0)
        self.assertEqual(hit.product_uom_id, hit.sale_order_line_id.product_uom)
        self.assertEqual(hit.bc3_text, "Texto del presupuesto")
        self.assertEqual(miss.product_uom_id, miss.sale_order_line_id.product_uom)
