from odoo.tests.common import TransactionCase


class TestPrintPreset(TransactionCase):
    def test_save_and_apply_returns_the_same_values(self):
        order = self.env["sale.order"].create(
            {"partner_id": self.env["res.partner"].create({"name": "Perfil"}).id}
        )
        order.write({"print_hide_null_price": True, "print_hide_null_qty": False})
        preset = self.env["construction.print.preset"].create(
            {"name": "Para cliente", "res_model": "sale.order"}
        )
        order.print_preset_id = preset
        order.action_save_print_preset()
        self.assertTrue(preset.values["print_hide_null_price"])
        self.assertFalse(preset.values["print_hide_null_qty"])

        order.write({"print_hide_null_price": False, "print_hide_null_qty": True})
        order._onchange_print_preset_id()
        self.assertTrue(order.print_hide_null_price)
        self.assertFalse(order.print_hide_null_qty)
