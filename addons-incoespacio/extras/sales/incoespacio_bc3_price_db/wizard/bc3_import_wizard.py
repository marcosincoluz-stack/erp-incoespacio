from odoo import models


class Bc3ImportWizard(models.TransientModel):
    _inherit = "bc3.import.wizard"

    def _product_for_line(self, line_code, concept):
        product, uom_id = super()._product_for_line(line_code, concept)
        categ = self.env.ref(
            "incoespacio_bc3_price_db.price_db_category", raise_if_not_found=False
        )
        if not categ:
            return product, uom_id
        linked = self.env["product.product"].search(
            [
                ("default_code", "=", line_code),
                ("categ_id", "=", categ.id),
            ],
            limit=1,
        )
        if linked:
            return linked, linked.uom_id.id
        return product, uom_id
