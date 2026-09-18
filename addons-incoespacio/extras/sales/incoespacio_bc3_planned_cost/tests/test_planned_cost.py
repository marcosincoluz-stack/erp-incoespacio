import base64

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestBC3PlannedCost(TransactionCase):
    def _line(self, **vals):
        partner = self.env["res.partner"].create({"name": "Obra %"})
        product = self.env["product.product"].create(
            {"name": "Demolicion", "list_price": 10.67}
        )
        order = self.env["sale.order"].create(
            {
                "partner_id": partner.id,
                "bc3": True,
                "planned_percent": 20.0,
            }
        )
        data = {
            "order_id": order.id,
            "product_id": product.id,
            "product_uom_qty": 2.0,
            "price_unit": 10.67,
        }
        data.update(vals)
        return self.env["sale.order.line"].create(data)

    def test_percent_and_qty_change(self):
        line = self._line()
        self.assertAlmostEqual(line.qty_planned, 2.0)
        self.assertAlmostEqual(line.price_planned, 8.54, places=2)
        self.assertAlmostEqual(line.amount_planned, 8.54 * 2.0, places=2)
        line.product_uom_qty = 3.0
        self.assertAlmostEqual(line.qty_planned, 3.0)
        self.assertAlmostEqual(line.amount_planned, 8.54 * 3.0, places=2)
        line.order_id.planned_percent = 0.0
        self.assertAlmostEqual(line.price_planned, 0.0)
        self.assertAlmostEqual(line.amount_planned, 0.0)
        self.assertAlmostEqual(line.order_id.amount_planned, 0.0)

    def test_qty_planned_can_diverge(self):
        line = self._line()
        line.qty_planned = 5.0
        line.product_uom_qty = 4.0
        self.assertAlmostEqual(line.qty_planned, 5.0)
        self.assertAlmostEqual(line.amount_planned, 8.54 * 5.0, places=2)

    def test_planned_percent_range(self):
        line = self._line()
        with self.assertRaises(ValidationError):
            line.order_id.planned_percent = 126.0
        with self.assertRaises(ValidationError):
            line.order_id.planned_percent = -5.0
        line.order_id.planned_percent = 0.0
        self.assertAlmostEqual(line.price_planned, 0.0)
        line.order_id.planned_percent = 99.0
        self.assertAlmostEqual(line.price_planned, 10.67 * 0.01, places=2)

    def test_manual_price_survives_percent_and_reset(self):
        line = self._line()
        line.price_planned = 5.0
        self.assertTrue(line.price_planned_manual)
        line.order_id.planned_percent = 10.0
        self.assertAlmostEqual(line.price_planned, 5.0)
        line.action_reset_price_planned()
        self.assertFalse(line.price_planned_manual)
        self.assertAlmostEqual(line.price_planned, 10.67 * 0.9, places=2)

    def test_bc3_second_price_is_planned_manual(self):
        raw = (
            b"~V|SOFT S.A.|FIEBDC-3/2002|Presto 8.8||ANSI|\n"
            b"~C|CAP01#||Capitulo pintura|0||CA|\n"
            b"~C|X|m2|Pintura|8.30\\6.10||EU|\n"
            b"~D|CAP01#|X\\1\\1\\|\n"
        )
        partner = self.env["res.partner"].create({"name": "BC3 objetivo"})
        wizard = self.env["bc3.import.wizard"].create(
            {
                "bc3_file": base64.b64encode(raw),
                "bc3_file_name": "objetivo.bc3",
                "version_id": self.env.ref("bc3_importer.bc3_version_2020_v2").id,
                "partner_id": partner.id,
                "create_products": False,
            }
        )
        wizard.do_action()
        line = wizard.sale_id.order_line.filtered(lambda l: l.bc3_code == "X")
        self.assertTrue(line)
        self.assertAlmostEqual(line.price_unit, 8.30)
        self.assertAlmostEqual(line.price_planned, 6.10)
        self.assertTrue(line.price_planned_manual)
        line.price_planned = 5.0
        wizard.sale_id.planned_percent = 20.0
        self.assertAlmostEqual(line.price_planned, 5.0)
        line.action_reset_price_planned()
        self.assertAlmostEqual(line.price_planned, 8.30 * 0.8, places=2)
        self.assertFalse(line.price_planned_manual)
