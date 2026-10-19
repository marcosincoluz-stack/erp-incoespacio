from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    bc3_code = fields.Char(
        compute="_compute_bc3_from_price_db",
        store=True,
        readonly=False,
    )
    bc3_text = fields.Text(
        compute="_compute_bc3_from_price_db",
        store=True,
        readonly=False,
    )

    def _price_db_category(self):
        return self.env.ref(
            "incoespacio_bc3_price_db.price_db_category", raise_if_not_found=False
        )

    @api.depends(
        "product_id.default_code",
        "product_id.description_sale",
        "product_id.categ_id",
    )
    def _compute_bc3_from_price_db(self):
        categ = self._price_db_category()
        for line in self:
            product = line.product_id
            if not categ or product.categ_id != categ:
                continue
            if product.default_code:
                line.bc3_code = product.default_code
            if product.description_sale:
                line.bc3_text = product.description_sale

    def _get_sale_order_line_multiline_description_sale(self):
        self.ensure_one()
        categ = self._price_db_category()
        if categ and self.product_id.categ_id == categ:
            return self.product_id.display_name
        return super()._get_sale_order_line_multiline_description_sale()
