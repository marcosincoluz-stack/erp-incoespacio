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
    amount_cost_ahead = fields.Monetary(
        string="Coste adelantado",
        compute="_compute_order_forecast",
        currency_field="currency_id",
        help="Gastado en partidas que aún no tienen nada certificado. Puede ser "
        "normal (material comprado por adelantado) o un error de imputación. No "
        "entra en la desviación, que se mide sobre lo ejecutado.",
    )

    @api.depends(
        "amount_untaxed",
        "amount_cost_unassigned",
        "order_line.amount_po_cost",
        "order_line.amount_cost_incurred",
        "order_line.amount_cost_forecast",
        "order_line.amount_cost_ahead",
    )
    def _compute_order_forecast(self):
        for order in self:
            sale = order.amount_untaxed or 0.0
            po = sum(order.order_line.mapped("amount_po_cost"))
            incurred = sum(order.order_line.mapped("amount_cost_incurred"))
            # Lo gastado sin imputar a partida también es coste de la obra.
            cost_f = sum(order.order_line.mapped("amount_cost_forecast")) + (
                order.amount_cost_unassigned or 0.0
            )
            margin_f = sale - cost_f
            order.amount_cost_ahead = sum(order.order_line.mapped("amount_cost_ahead"))
            order.amount_po_partida = po
            order.amount_cost_incurred = incurred
            order.amount_cost_forecast = cost_f
            order.amount_margin_forecast = margin_f
            order.margin_percent_forecast = margin_f / sale * 100.0 if sale else 0.0

    @api.depends(
        "amount_untaxed",
        "amount_planned",
        "amount_job_cost",
        "amount_certified_origin",
        "planned_percent",
        "order_line.amount_vendor_cost",
        "order_line.amount_planned_done",
        "order_line.amount_cost_deviation",
        "certification_ids.state",
        "certification_ids.amount_total_origin",
    )
    def _compute_order_margins(self):
        # Aquí y no en incoespacio_construction_margins, que está en el tope de
        # líneas.
        # - Desviación de la obra = suma de la de sus partidas: la cabecera y la
        #   tabla cuadran; el coste de partidas sin avance va en «adelantado».
        # - Margen real = certificado menos todo el coste de la obra, también
        #   lo no imputado a partida (antes se quedaba fuera y la obra parecía
        #   perder menos). Coincide con amount_job_margin.
        res = super()._compute_order_margins()
        for order in self:
            deviations = order.order_line.mapped("amount_cost_deviation")
            order.amount_cost_deviation = sum(deviations)
            certified = order.amount_certified_origin or 0.0
            margin = certified - (order.amount_job_cost or 0.0)
            order.amount_margin_real = margin
            order.margin_percent_real = margin / certified * 100.0 if certified else 0.0
        return res


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    amount_cost_ahead = fields.Monetary(
        string="Adelantado",
        compute="_compute_cost_ahead",
        currency_field="currency_id",
        help="Coste de una partida que aún no tiene nada certificado.",
    )
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

    @api.depends("display_type", "amount_vendor_cost", "qty_cert_origin")
    def _compute_cost_ahead(self):
        for line in self:
            cost = line.amount_vendor_cost or 0.0
            ahead = cost > 0 and not line.qty_cert_origin and not line.display_type
            line.amount_cost_ahead = cost if ahead else 0.0

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
        "amount_vendor_cost",
        "amount_po_cost",
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
            billed = line.amount_vendor_cost or 0.0
            committed = line.amount_po_cost or 0.0
            qty_cert = line.qty_cert_origin or 0.0
            # Ritmo real con lo ya facturado; sin certificar, el objetivo.
            if qty_cert and billed:
                pu = billed / qty_cert
            else:
                pu = line.price_planned or 0.0
            remaining = max((line.product_uom_qty or 0.0) - qty_cert, 0.0)
            # Lo comprometido es lo que se va a gastar en lo que falta: no se
            # suma encima de la extrapolación (un pedido de la partida entera
            # se contaría dos veces); se compara con ella y manda la mayor.
            # Si el coste va por delante de la certificación, sobreestima: es
            # el riesgo que se quiere ver.
            forecast = billed + max(committed, remaining * pu)
            sale = line.price_subtotal or 0.0
            margin = sale - forecast
            line.price_unit_forecast = pu
            line.amount_cost_forecast = forecast
            line.amount_margin_forecast = margin
            line.margin_percent_forecast = margin / sale * 100.0 if sale else 0.0
