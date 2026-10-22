from odoo import api, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model
    def price_db_domain(self):
        categ = self.env.ref(
            "incoespacio_bc3_price_db.price_db_category", raise_if_not_found=False
        )
        if not categ:
            return [("id", "=", 0)]
        return [("categ_id", "=", categ.id), ("sale_ok", "=", True)]

    @api.model
    def _name_search(self, name, domain=None, operator="ilike", limit=None, order=None):
        domain = list(domain or [])
        if self.env.context.get("price_db_only"):
            domain = self.price_db_domain() + domain
        return super()._name_search(name, domain, operator, limit=limit, order=order)
