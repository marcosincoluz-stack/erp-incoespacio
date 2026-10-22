import base64
import time

from odoo.exceptions import UserError
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


class TestPriceDb(TransactionCase):
    def _import(self, raw):
        wizard = self.env["bc3.price.import.wizard"].create(
            {"bc3_file": base64.b64encode(raw), "bc3_file_name": "base.bc3"}
        )
        return wizard.action_import()

    def _products(self, codes=None):
        domain = [
            ("categ_id", "=", self.env.ref("incoespacio_bc3_price_db.price_db_category").id)
        ]
        if codes is not None:
            domain.append(("default_code", "in", list(codes)))
        return self.env["product.template"].search(domain)

    def test_import_partidas_and_skip_resources(self):
        before_resources = len(self._products(["MAT01", "MO01"]))
        self._import(_BASE)
        products = self._products(["37.5", "TAB01"])
        self.assertEqual(set(products.mapped("default_code")), {"37.5", "TAB01"})
        self.assertEqual(len(self._products(["MAT01", "MO01"])), before_resources)
        row = products.filtered(lambda p: p.default_code == "37.5")
        self.assertEqual(row.name, "DESMONTAJE CARPINTERIAS")
        self.assertAlmostEqual(row.list_price, 12.5)
        self.assertEqual(row.description_sale, "Texto largo de desmontaje")
        self.assertEqual(
            row.uom_id, self.env.ref("bc3_importer.product_uom_square_meter")
        )
        self.assertEqual(row.uom_po_id, row.uom_id)
        self.assertEqual(row.detailed_type, "service")
        self.assertTrue(row.sale_ok)
        self.assertFalse(row.purchase_ok)

    def test_import_continues_across_requests(self):
        raw = _HEADER + (
            b"~C|C01#||Cap|0||0|\n"
            b"~C|ZZBATCH1|m2|Uno batch|1.00||0|\n"
            b"~C|ZZBATCH2|ud|Dos batch|2.00||0|\n"
        )
        wizard = self.env["bc3.price.import.wizard"].create(
            {"bc3_file": base64.b64encode(raw), "bc3_file_name": "base.bc3"}
        )
        codes = ["ZZBATCH1", "ZZBATCH2"]
        first = wizard.with_context(bc3_price_chunk=1).action_import()
        self.assertEqual(first["tag"], "bc3_price_import_continue")
        self.assertEqual(len(self._products(codes)), 1)
        second = wizard.with_context(bc3_price_chunk=1).action_import()
        self.assertEqual(second["type"], "ir.actions.act_window")
        self.assertEqual(set(self._products(codes).mapped("default_code")), set(codes))
        self.assertFalse(wizard.batch_rows)

    def test_reimport_updates_without_duplicating(self):
        self._import(_BASE)
        updated = _BASE.replace(b"|12.50|", b"|15.00|").replace(
            b"DESMONTAJE CARPINTERIAS", b"DESMONTAJE ACTUALIZADO"
        )
        self._import(updated)
        products = self._products(["37.5", "TAB01"])
        self.assertEqual(len(products), 2)
        row = products.filtered(lambda p: p.default_code == "37.5")
        self.assertAlmostEqual(row.list_price, 15.0)
        self.assertEqual(row.name, "DESMONTAJE ACTUALIZADO")

    def test_empty_file_errors(self):
        with self.assertRaises(UserError):
            self._import(_HEADER + b"~C|MAT01|ud|Ladrillo|0.15||3|\n")

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

    def test_suggest_only_price_db(self):
        self._import(_BASE)
        other = self.env["product.product"].create(
            {"name": "Tabique ajeno", "default_code": "ZZ-NO", "sale_ok": True}
        )
        Product = self.env["product.product"].with_context(price_db_only=True)
        by_title = Product.name_search("tabique")
        self.assertTrue(by_title)
        self.assertNotIn(other.id, [row[0] for row in by_title])
        self.assertNotIn(other.id, [row[0] for row in Product.name_search("ZZ-NO")])
        by_code = Product.name_search("37.5")
        self.assertEqual(len(by_code), 1)
        self.assertIn("37.5", by_code[0][1])
        self.assertIn("DESMONTAJE", by_code[0][1])
        categ = self.env.ref("incoespacio_bc3_price_db.price_db_category")
        self.assertIn(("categ_id", "=", categ.id), self.env["product.product"].price_db_domain())
        created_id, _label = self.env["product.product"].with_context(
            default_categ_id=categ.id,
            default_detailed_type="service",
            default_sale_ok=True,
            default_purchase_ok=False,
        ).name_create("Tabique nuevo ZZ")
        created = self.env["product.product"].browse(created_id)
        self.assertEqual(created.categ_id, categ)
        self.assertTrue(created.sale_ok)
        self.assertFalse(created.purchase_ok)

    def test_many_partidas_search(self):
        lines = [b"~C|C01#||Cap|0||0|"]
        children = []
        for index in range(200):
            code = "T%04d" % index
            children.append(code + "\\1\\1")
            name = "Tabique hueco" if index == 7 else "Partida %s" % index
            lines.append(("~C|%s|m2|%s|10.00||0|" % (code, name)).encode())
        lines.append(("~D|C01#|%s\\|" % "\\".join(children)).encode())
        started = time.time()
        self._import(_HEADER + b"\n".join(lines) + b"\n")
        elapsed = time.time() - started
        codes = ["T%04d" % index for index in range(200)]
        products = self._products(codes)
        self.assertEqual(len(products), 200)
        self.assertEqual(
            len(products.filtered(lambda product: "tabique" in product.name.lower())),
            1,
        )
        self.assertLess(elapsed, 45, "import of 200 partidas took %ss" % elapsed)

@tagged("post_install", "-at_install")
class TestPriceDbCertification(TransactionCase):
    def test_certification_copies_linked_line(self):
        TestPriceDb._import(self, _BASE)
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
