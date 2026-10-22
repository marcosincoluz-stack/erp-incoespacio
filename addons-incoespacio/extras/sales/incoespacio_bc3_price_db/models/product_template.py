from odoo import models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def action_open_price_text(self):
        self.ensure_one()
        view = self.env.ref("incoespacio_bc3_price_db.product_template_price_db_form")
        return {
            "type": "ir.actions.act_window",
            "name": "Descripción",
            "res_model": "product.template",
            "res_id": self.id,
            "view_mode": "form",
            "views": [(view.id, "form")],
            "target": "new",
        }
