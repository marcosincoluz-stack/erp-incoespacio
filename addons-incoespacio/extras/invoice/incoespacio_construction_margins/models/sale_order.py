from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    amount_cost_partida = fields.Monetary(
        string="Coste imputado",
        compute="_compute_order_margins",
        currency_field="currency_id",
        help="Suma de facturas de proveedor imputadas a partida.",
    )
    amount_cost_unassigned = fields.Monetary(
        string="Sin imputar a partida",
        compute="_compute_order_margins",
        currency_field="currency_id",
        help="Coste de obra publicado que aún no está en ninguna partida.",
    )
    amount_margin_planned = fields.Monetary(
        string="Margen objetivo",
        compute="_compute_order_margins",
        currency_field="currency_id",
    )
    margin_percent_planned = fields.Float(
        string="% margen objetivo",
        compute="_compute_order_margins",
        digits=(16, 1),
    )
    progress_percent = fields.Float(
        string="% avance",
        compute="_compute_order_margins",
        digits=(16, 1),
    )
    amount_planned_done = fields.Monetary(
        string="Objetivo ejecutado",
        compute="_compute_order_margins",
        currency_field="currency_id",
    )
    amount_cost_deviation = fields.Monetary(
        string="Desv. vs objetivo",
        compute="_compute_order_margins",
        currency_field="currency_id",
        help="Positivo = el coste real supera el objetivo ejecutado.",
    )
    amount_margin_real = fields.Monetary(
        string="Margen real",
        compute="_compute_order_margins",
        currency_field="currency_id",
    )
    margin_percent_real = fields.Float(
        string="% margen real",
        compute="_compute_order_margins",
        digits=(16, 1),
    )

    def _last_invoiced_cert(self):
        self.ensure_one()
        invoiced = self.certification_ids.filtered(
            lambda c: c.state == "invoiced"
        ).sorted("number")
        return invoiced[-1] if invoiced else self.env["construction.certification"]

    @api.depends(
        "amount_untaxed",
        "amount_planned",
        "amount_job_cost",
        "amount_certified_origin",
        "planned_percent",
        "order_line.amount_vendor_cost",
        "order_line.amount_planned_done",
        "certification_ids.state",
        "certification_ids.amount_total_origin",
    )
    def _compute_order_margins(self):
        for order in self:
            sale = order.amount_untaxed or 0.0
            planned = order.amount_planned or 0.0
            cost = sum(order.order_line.mapped("amount_vendor_cost"))
            certified = order.amount_certified_origin or 0.0
            planned_done = sum(order.order_line.mapped("amount_planned_done"))
            order.amount_cost_partida = cost
            order.amount_cost_unassigned = (order.amount_job_cost or 0.0) - cost
            order.amount_margin_planned = sale - planned
            order.margin_percent_planned = (
                (sale - planned) / sale * 100.0 if sale else 0.0
            )
            order.progress_percent = certified / sale * 100.0 if sale else 0.0
            order.amount_planned_done = planned_done
            order.amount_cost_deviation = (cost - planned_done) if certified else 0.0
            order.amount_margin_real = certified - cost
            order.margin_percent_real = (
                (certified - cost) / certified * 100.0 if certified else 0.0
            )


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    qty_cert_origin = fields.Float(
        string="Med. certificada",
        compute="_compute_line_margin",
        digits="Product Unit of Measure",
    )
    progress_percent = fields.Float(
        string="Avance %",
        compute="_compute_line_margin",
        digits=(16, 1),
    )
    amount_cert_origin = fields.Monetary(
        string="Cert. a origen",
        compute="_compute_line_margin",
        currency_field="currency_id",
    )
    amount_planned_done = fields.Monetary(
        string="Obj. ejecutado",
        compute="_compute_line_margin",
        currency_field="currency_id",
    )
    amount_cost_deviation = fields.Monetary(
        string="Desv.",
        compute="_compute_line_margin",
        currency_field="currency_id",
    )
    amount_margin_planned = fields.Monetary(
        string="Margen previsto",
        compute="_compute_line_margin",
        currency_field="currency_id",
    )
    margin_percent_planned = fields.Float(
        string="% margen previsto",
        compute="_compute_line_margin",
        digits=(16, 1),
    )
    amount_margin = fields.Monetary(
        string="Margen",
        compute="_compute_line_margin",
        currency_field="currency_id",
    )
    margin_percent = fields.Float(
        string="% margen",
        compute="_compute_line_margin",
        digits=(16, 1),
    )
    price_unit_real = fields.Float(
        string="P.U. real",
        compute="_compute_line_margin",
        digits="Product Price",
        help="Coste imputado / medición certificada a origen.",
    )
    vendor_cost_line_ids = fields.One2many(
        "account.move.line",
        "construction_line_id",
        string="Facturas imputadas",
        domain=[
            ("parent_state", "=", "posted"),
            ("move_id.move_type", "in", ("in_invoice", "in_refund")),
        ],
    )

    @api.depends(
        "display_type",
        "price_unit",
        "product_uom_qty",
        "price_subtotal",
        "price_planned",
        "amount_planned",
        "amount_vendor_cost",
        "order_id.certification_ids.state",
        "order_id.certification_ids.number",
        "order_id.certification_ids.line_ids.qty_origin",
        "order_id.certification_ids.line_ids.sale_order_line_id",
        "order_id.certification_ids.line_ids.display_type",
    )
    def _compute_line_margin(self):
        qty_by_sol = {}
        for order in self.mapped("order_id"):
            cert = order._last_invoiced_cert() if order else False
            if not cert:
                continue
            for cline in cert.line_ids:
                if cline.sale_order_line_id and not cline.display_type:
                    qty_by_sol[cline.sale_order_line_id.id] = cline.qty_origin or 0.0
        for line in self:
            if line.display_type:
                line.qty_cert_origin = 0.0
                line.progress_percent = 0.0
                line.amount_cert_origin = 0.0
                line.amount_planned_done = 0.0
                line.amount_cost_deviation = 0.0
                line.amount_margin_planned = 0.0
                line.margin_percent_planned = 0.0
                line.amount_margin = 0.0
                line.margin_percent = 0.0
                line.price_unit_real = 0.0
                continue
            qty = line.product_uom_qty or 0.0
            qty_cert = qty_by_sol.get(line.id, 0.0)
            cost = line.amount_vendor_cost or 0.0
            cert_amt = qty_cert * (line.price_unit or 0.0)
            planned_done = qty_cert * (line.price_planned or 0.0)
            line.qty_cert_origin = qty_cert
            line.progress_percent = qty_cert / qty * 100.0 if qty else 0.0
            line.amount_cert_origin = cert_amt
            line.amount_planned_done = planned_done
            line.amount_cost_deviation = (cost - planned_done) if qty_cert else 0.0
            sale = line.price_subtotal or 0.0
            target = line.amount_planned or 0.0
            line.amount_margin_planned = sale - target
            line.margin_percent_planned = (sale - target) / sale * 100.0 if sale else 0.0
            line.amount_margin = cert_amt - cost
            line.margin_percent = (
                (cert_amt - cost) / cert_amt * 100.0 if cert_amt else 0.0
            )
            line.price_unit_real = cost / qty_cert if qty_cert else 0.0
