from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    project_id = fields.Many2one("project.project", string="Proyecto / Obra", copy=True)

    def _prepare_invoice(self):
        vals = super()._prepare_invoice()
        if self.project_id:
            vals["project_id"] = self.project_id.id
        return vals
