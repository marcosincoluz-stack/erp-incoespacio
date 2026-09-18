import base64
import os

from odoo.tests.common import TransactionCase

_DIR = os.path.dirname(__file__)


class TestBC3ImportWizard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with open(os.path.join(_DIR, "bc3_file_test.bc3"), "rb") as file:
            bc3_content = file.read()
        cls.partner = cls.env["res.partner"].create({"name": "BC3 Test Partner"})
        cls.wizard = cls.env["bc3.import.wizard"].create(
            {
                "bc3_file": base64.b64encode(bc3_content),
                "bc3_file_name": "test.bc3",
                "version_id": cls.env.ref("bc3_importer.bc3_version_2020_v2").id,
                "partner_id": cls.partner.id,
                "create_products": False,
            }
        )

    def test_do_action(self):
        result = self.wizard.do_action()
        order = self.wizard.sale_id
        self.assertEqual(result["res_model"], "sale.order")
        self.assertEqual(result["res_id"], order.id)
        self.assertTrue(order.bc3)
        self.assertEqual(order.partner_id, self.partner)
        sections = order.order_line.filtered(lambda l: l.display_type == "line_section")
        products = order.order_line.filtered(lambda l: not l.display_type)
        self.assertTrue(sections)
        self.assertEqual(sections[0].bc3_code, "CAP01")
        self.assertTrue(products)
        hormigon = products.filtered(lambda l: l.bc3_code == "A03B0010")
        self.assertTrue(hormigon)
        self.assertAlmostEqual(hormigon[0].price_unit, 38.34)

    def test_presto_nul_drawings_are_skipped(self):
        raw = (
            b"~V|SOFT S.A.|FIEBDC-3/2002|Presto 8.8||ANSI|\n"
            b"~C|CAP01#||Capitulo hormigon|0||CA|\n"
            b"~C|A03B0010|m3|Hormigon aligerado de cemento y picon.|38.34|011222|3|\n"
            b"~D|CAP01#|A03B0010\\1\\1\\|\n"
            b"~T|A03B0010|texto real de partida|\n"
            b"\x00\xff~C|FAKE01#||No debe importar|0||CA|"
            + b"\x00" * 8000
            + b"~G|IE-01|"
            + b"\x00" * 4000
        )
        regs = list(self.wizard._iter_bc3_registers(self.wizard._decode_bc3(raw)))
        self.assertEqual(sum(1 for r in regs if r[0] == "C"), 2)
        self.assertFalse(any("FAKE01" in r for r in regs))
        texts = [r for r in regs if r[0] == "T"]
        self.assertEqual(len(texts), 1)
        self.assertIn("texto real de partida", texts[0])
        self.assertLess(len(texts[0]), 80)

        wizard = self.env["bc3.import.wizard"].create(
            {
                "bc3_file": base64.b64encode(raw),
                "bc3_file_name": "presto.bc3",
                "version_id": self.env.ref("bc3_importer.bc3_version_2020_v2").id,
                "partner_id": self.partner.id,
                "create_products": False,
            }
        )
        wizard.do_action()
        codes = wizard.sale_id.order_line.mapped("bc3_code")
        self.assertIn("A03B0010", codes)
        self.assertNotIn("FAKE01", codes)

    def test_nested_chapters_stop_at_partida(self):
        raw = (
            b"~V|SOFT S.A.|FIEBDC-3/2002|Presto 8.8||ANSI|\n"
            b"~C|T01##||Obra test|100||OB|\n"
            b"~D|T01##|C01#\\1\\1\\C02#\\1\\1\\|\n"
            b"~C|C01#||Capitulo uno|80||CA|\n"
            b"~D|C01#|C01A#\\1\\1\\|\n"
            b"~C|C01A#||Subcapitulo|80||CA|\n"
            b"~D|C01A#|UO1\\1\\10\\|\n"
            b"~C|C02#||Capitulo dos|20||CA|\n"
            b"~D|C02#|UO2\\1\\2\\|\n"
            b"~C|UO1|m3|Partida uno|8.00||EU|\n"
            b"~D|UO1|MO01\\1\\1\\|\n"
            b"~C|UO2|ud|Partida dos|10.00||EU|\n"
            b"~C|MO01|h|Oficial|8.00||1|\n"
        )
        wizard = self.env["bc3.import.wizard"].create(
            {
                "bc3_file": base64.b64encode(raw),
                "bc3_file_name": "nested.bc3",
                "version_id": self.env.ref("bc3_importer.bc3_version_2020_v2").id,
                "partner_id": self.partner.id,
                "create_products": False,
            }
        )
        wizard.do_action()
        lines = wizard.sale_id.order_line.sorted("sequence")
        codes = lines.mapped("bc3_code")
        self.assertEqual(codes, ["C01", "C01A", "UO1", "C02", "UO2"])
        self.assertNotIn("MO01", codes)
        self.assertNotIn("T01", codes)
        uo1 = lines.filtered(lambda l: l.bc3_code == "UO1")
        self.assertAlmostEqual(uo1.product_uom_qty, 10.0)
        self.assertAlmostEqual(uo1.price_unit, 8.0)
        self.assertEqual(lines.filtered(lambda l: l.bc3_code == "C01").bc3_level, 0)
        self.assertEqual(lines.filtered(lambda l: l.bc3_code == "C01A").bc3_level, 1)
        self.assertEqual(uo1.bc3_level, 2)
        self.assertEqual(lines.filtered(lambda l: l.bc3_code == "C02").bc3_level, 0)
        self.assertEqual(lines.filtered(lambda l: l.bc3_code == "UO2").bc3_level, 1)
        c01a = lines.filtered(lambda l: l.bc3_code == "C01A")
        c02 = lines.filtered(lambda l: l.bc3_code == "C02")
        self.assertLess(c01a.sequence, uo1.sequence)
        self.assertLess(uo1.sequence, c02.sequence)

    def test_presto_hashless_children_are_chapters(self):
        raw = (
            b"~V|SOFT S.A.|FIEBDC-3/2002|Presto 8.8||ANSI|\n"
            b"~C|OBRA##||Obra test|100||0|\n"
            b"~D|OBRA##|C01\\1\\1\\|\n"
            b"~C|C01#||Albanileria|50||0|\n"
            b"~D|C01#|D01\\1\\2.52\\|\n"
            b"~C|D01|m2|Demolicion tabicon|6.83||0|\n"
            b"~D|D01|PEON\\1\\0.36\\|\n"
            b"~C|PEON|h|Peon|17.97||1|\n"
        )
        wizard = self.env["bc3.import.wizard"].create(
            {
                "bc3_file": base64.b64encode(raw),
                "bc3_file_name": "presto_hash.bc3",
                "version_id": self.env.ref("bc3_importer.bc3_version_2020_v2").id,
                "partner_id": self.partner.id,
                "create_products": False,
            }
        )
        wizard.do_action()
        lines = wizard.sale_id.order_line.sorted("sequence")
        self.assertEqual(lines.mapped("bc3_code"), ["C01", "D01"])
        self.assertEqual(lines[0].display_type, "line_section")
        self.assertIn("Albanileria", lines[0].name)
        self.assertFalse(lines[1].display_type)
        self.assertAlmostEqual(lines[1].product_uom_qty, 2.52)
        self.assertAlmostEqual(lines[1].price_unit, 17.97 * 0.36, places=2)

    def test_decomp_price_wins_over_stale_c(self):
        raw = (
            b"~V|SOFT S.A.|FIEBDC-3/2002|Presto 8.8||ANSI|\n"
            b"~C|OBRA##||Obra test|100||0|\n"
            b"~D|OBRA##|C01\\1\\1\\\n"
            b"~C|C01#||Albanileria|50||0|\n"
            b"~D|C01#|D18AD030\\1\\21.22\\\n"
            b"~C|D18AD030|m2|ALICATADO PLAQUETA GRES|42||0|\n"
            b"~D|D18AD030|U01FU011\\1\\1.2\\PEONORD\\1\\0.2\\D18AR010\\1\\1\\"
            b"U18AD041\\1\\1.05\\U18AZ012\\1\\7\\U18AZ100\\1\\2.2\\%CI\\1\\0.07\\\n"
            b"~C|D18AR010|m2|ENFOSCADO|12||0|\n"
            b"~D|D18AR010|OFICI1\\1\\0.3\\PEONORD\\1\\0.2\\A01JF003\\1\\0.015\\%CI\\1\\0.07\\\n"
            b"~C|U01FU011|m2|Mano de obra colocacion gres|13.5||0|\n"
            b"~C|PEONORD|h|Peon suelto|17.73||1|\n"
            b"~C|OFICI1|h|Oficial primera|19.7||1|\n"
            b"~C|A01JF003|m3|MORTERO CEMENTO M15|117.58||3|\n"
            b"~C|U18AD041|m2|Baldosa gres|24||3|\n"
            b"~C|U18AZ012|kg|weber.col classic blanco|0.18||3|\n"
            b"~C|U18AZ100|kg|weber.col junta fina|1.13||3|\n"
            b"~C|%CI|%|Costes indirectos|7||0|\n"
        )
        wizard = self.env["bc3.import.wizard"].create(
            {
                "bc3_file": base64.b64encode(raw),
                "bc3_file_name": "alicatado.bc3",
                "version_id": self.env.ref("bc3_importer.bc3_version_2020_v2").id,
                "partner_id": self.partner.id,
                "create_products": False,
            }
        )
        wizard.do_action()
        lines = wizard.sale_id.order_line.filtered(lambda l: l.bc3_code == "D18AD030")
        self.assertEqual(len(lines), 1)
        self.assertFalse(lines.display_type)
        self.assertAlmostEqual(lines.price_unit, 64.95, places=2)
        self.assertAlmostEqual(lines.product_uom_qty, 21.22)
        codes = wizard.sale_id.order_line.mapped("bc3_code")
        self.assertNotIn("PEONORD", codes)
        self.assertNotIn("U18AD041", codes)
