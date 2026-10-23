from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    amount_po_partida = fields.Monetary(
        string="Comprometido a partida",
        compute="_compute_order_forecast",
        currency_field="currency_id",
    )
    amount_cost_incurred = fields.Monetary(
        string="Incurrido",
        compute="_compute_order_forecast",
        currency_field="currency_id",
    )
    amount_cost_forecast = fields.Monetary(
        string="Coste previsto",
        compute="_compute_order_forecast",
        currency_field="currency_id",
    )
    amount_margin_forecast = fields.Monetary(
        string="Margen previsto",
        compute="_compute_order_forecast",
        currency_field="currency_id",
    )
    margin_percent_forecast = fields.Float(
        string="% margen previsto",
        compute="_compute_order_forecast",
        digits=(16, 1),
    )

    @api.depends(
        "amount_untaxed",
        "order_line.amount_po_cost",
        "order_line.amount_cost_incurred",
        "order_line.amount_cost_forecast",
        "order_line.amount_margin_forecast",
    )
    def _compute_order_forecast(self):
        for order in self:
            sale = order.amount_untaxed or 0.0
            po = sum(order.order_line.mapped("amount_po_cost"))
            incurred = sum(order.order_line.mapped("amount_cost_incurred"))
            cost_f = sum(order.order_line.mapped("amount_cost_forecast"))
            margin_f = sum(order.order_line.mapped("amount_margin_forecast"))
            order.amount_po_partida = po
            order.amount_cost_incurred = incurred
            order.amount_cost_forecast = cost_f
            order.amount_margin_forecast = margin_f
            order.margin_percent_forecast = (
                margin_f / sale * 100.0 if sale else 0.0
            )


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    construction_po_line_ids = fields.One2many(
        "purchase.order.line", "construction_line_id"
    )
    amount_po_cost = fields.Monetary(
        string="Comprometido",
        compute="_compute_po_cost",
        currency_field="currency_id",
    )
    amount_cost_incurred = fields.Monetary(
        string="Incurrido",
        compute="_compute_po_cost",
        currency_field="currency_id",
    )
    price_unit_forecast = fields.Float(
        string="P.U. previsto",
        compute="_compute_forecast",
        digits="Product Price",
    )
    amount_cost_forecast = fields.Monetary(
        string="Coste previsto",
        compute="_compute_forecast",
        currency_field="currency_id",
    )
    amount_margin_forecast = fields.Monetary(
        string="Margen previsto",
        compute="_compute_forecast",
        currency_field="currency_id",
    )
    margin_percent_forecast = fields.Float(
        string="% margen previsto",
        compute="_compute_forecast",
        digits=(16, 1),
    )

    @api.depends(
        "display_type",
        "amount_vendor_cost",
        "construction_po_line_ids.qty_to_invoice",
        "construction_po_line_ids.price_unit",
        "construction_po_line_ids.order_id.state",
    )
    def _compute_po_cost(self):
        for line in self:
            if line.display_type:
                line.amount_po_cost = 0.0
                line.amount_cost_incurred = 0.0
                continue
            po = 0.0
            for pol in line.construction_po_line_ids:
                if pol.order_id.state in ("purchase", "done"):
                    po += (pol.qty_to_invoice or 0.0) * (pol.price_unit or 0.0)
            line.amount_po_cost = po
            line.amount_cost_incurred = (line.amount_vendor_cost or 0.0) + po

    @api.depends(
        "display_type",
        "amount_cost_incurred",
        "qty_cert_origin",
        "price_planned",
        "product_uom_qty",
        "price_subtotal",
    )
    def _compute_forecast(self):
        for line in self:
            if line.display_type:
                line.price_unit_forecast = 0.0
                line.amount_cost_forecast = 0.0
                line.amount_margin_forecast = 0.0
                line.margin_percent_forecast = 0.0
                continue
            incurred = line.amount_cost_incurred or 0.0
            qty_cert = line.qty_cert_origin or 0.0
            if qty_cert and incurred:
                pu = incurred / qty_cert
            else:
                pu = line.price_planned or 0.0
            remaining = max((line.product_uom_qty or 0.0) - qty_cert, 0.0)
            # ponytail: si el coste va por delante de la certificación sobreestima; es el riesgo que se quiere ver
            forecast = incurred + remaining * pu
            sale = line.price_subtotal or 0.0
            margin = sale - forecast
            line.price_unit_forecast = pu
            line.amount_cost_forecast = forecast
            line.amount_margin_forecast = margin
            line.margin_percent_forecast = margin / sale * 100.0 if sale else 0.0
