from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    margin_percent_job = fields.Float(
        string="% margen real",
        compute="_compute_margin_percent_job",
        digits=(16, 1),
        help="Margen real / certificado a origen. Usa el coste de obra completo, "
        "incluidas las facturas sin imputar a partida.",
    )

    @api.depends("amount_job_margin", "amount_certified_origin")
    def _compute_margin_percent_job(self):
        for order in self:
            order.margin_percent_job = (
                order.amount_job_margin / order.amount_certified_origin * 100.0
                if order.amount_certified_origin
                else 0.0
            )
