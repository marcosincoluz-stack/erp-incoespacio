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
            return self.product_id.name or ""
        return super()._get_sale_order_line_multiline_description_sale()

    def write(self, vals):
        vals = dict(vals)
        if (
            "bc3_code" in vals
            and "product_id" not in vals
            and not self.env.context.get("price_db_code_sync")
        ):
            linked = self._linked_price_lines()
            if linked:
                rest = self - linked
                if rest:
                    super(SaleOrderLine, rest).write(vals)
                kept = {key: value for key, value in vals.items() if key != "bc3_code"}
                if kept:
                    super(SaleOrderLine, linked).write(kept)
                for line in linked:
                    code = line.product_id.default_code or False
                    if line.bc3_code != code:
                        line.with_context(price_db_code_sync=True).write(
                            {"bc3_code": code}
                        )
                return True
        return super().write(vals)
