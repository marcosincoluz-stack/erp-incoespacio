from odoo import models

from .product_product import price_abbrev_domain


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def _search(self, domain, offset=0, limit=None, order=None, access_rights_uid=None):
        domain = price_abbrev_domain(self, domain)
        return super()._search(
            domain,
            offset=offset,
            limit=limit,
            order=order,
            access_rights_uid=access_rights_uid,
        )

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
