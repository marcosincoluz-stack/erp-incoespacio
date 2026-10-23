from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    price_db_linked = fields.Boolean(compute="_compute_price_db_linked")
    price_product_code = fields.Char(related="product_id.default_code")

    def _price_db_category(self):
        return self.env.ref(
            "incoespacio_bc3_price_db.price_db_category", raise_if_not_found=False
        )

    def _linked_price_lines(self):
        categ = self._price_db_category()
        if not categ:
            return self.browse()
        return self.filtered(lambda line: line.product_id.categ_id == categ)

    @api.depends("product_id.categ_id")
    def _compute_price_db_linked(self):
        linked = self._linked_price_lines()
        for line in self:
            line.price_db_linked = line in linked
