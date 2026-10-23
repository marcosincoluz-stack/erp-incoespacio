import re

from odoo import api, models

_CODE_TAIL = re.compile(r"^(.*\D)(\d+)$")


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model
    def price_db_domain(self):
        categ = self._price_db_category()
        if not categ:
            return [("id", "=", 0)]
        return [("categ_id", "=", categ.id), ("sale_ok", "=", True)]

    @api.model
    def _name_search(self, name, domain=None, operator="ilike", limit=None, order=None):
        domain = list(domain or [])
        if self.env.context.get("price_db_only"):
            domain = self.price_db_domain() + domain
        return super()._name_search(name, domain, operator, limit=limit, order=order)

    def _price_db_category(self):
        return self.env.ref(
            "incoespacio_bc3_price_db.price_db_category", raise_if_not_found=False
        )

    def _next_price_code(self, base, extra=()):
        # ponytail: one ilike of this prefix, no lock. Two creates at once can take the same code.
        match = _CODE_TAIL.match((base or "").strip())
        if not match:
            return False
        prefix, digits = match.group(1), match.group(2)
        codes = list(extra)
        codes.extend(
            self.search([("default_code", "=ilike", prefix + "%")]).mapped("default_code")
        )
        tail = re.compile("^" + re.escape(prefix) + r"(\d+)$", re.IGNORECASE)
        max_n = int(digits)
        width = len(digits)
        for code in codes:
            found = tail.match(code or "")
            if not found:
                continue
            max_n = max(max_n, int(found.group(1)))
            width = max(width, len(found.group(1)))
        return prefix + str(max_n + 1).zfill(width)

    @api.model_create_multi
    def create(self, vals_list):
        base = self.env.context.get("price_db_base_code")
        categ = self._price_db_category() if base else False
        if categ:
            given = []
            for vals in vals_list:
                if vals.get("default_code"):
                    continue
                categ_id = vals.get("categ_id") or self.env.context.get("default_categ_id")
                if categ_id != categ.id:
                    continue
                code = self._next_price_code(base, given)
                if not code:
                    break
                vals["default_code"] = code
                given.append(code)
        return super().create(vals_list)
