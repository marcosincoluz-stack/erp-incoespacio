from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    planned_percent = fields.Float(
        string="Margen objetivo %",
        default=0.0,
        help="Coste objetivo = P.U. × (100 − margen) %. 0 = sin objetivo. "
        "Debe estar entre 0 y 99,9 (es un % sobre la venta, no un recargo sobre coste).",
    )
    amount_planned = fields.Monetary(
        string="Coste objetivo",
        compute="_compute_amount_planned",
        store=True,
        currency_field="currency_id",
    )

    @api.constrains("planned_percent")
    def _check_planned_percent(self):
        for order in self:
            pct = order.planned_percent or 0.0
            if pct < 0.0 or pct >= 100.0:
                raise ValidationError(
                    _(
                        "El margen objetivo es un %% sobre la venta y debe estar "
                        "entre 0 y 99,9. Ejemplo: 20 = el coste objetivo es el "
                        "80 %% de la venta. Si piensas en recargo sobre coste "
                        "(×1,26), el margen equivalente es 20,6 %%."
                    )
                )

    @api.depends("order_line.amount_planned")
    def _compute_amount_planned(self):
        for order in self:
            order.amount_planned = sum(order.order_line.mapped("amount_planned"))


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    qty_planned = fields.Float(
        string="Ud. objetivo",
        digits="Product Unit of Measure",
    )
    price_planned = fields.Float(
        string="P. objetivo",
        compute="_compute_planned",
        inverse="_inverse_price_planned",
        store=True,
        readonly=False,
        digits="Product Price",
    )
    price_planned_manual = fields.Boolean()
    amount_planned = fields.Monetary(
        string="Importe objetivo",
        compute="_compute_planned",
        store=True,
        currency_field="currency_id",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("display_type") and "qty_planned" not in vals:
                vals["qty_planned"] = vals.get("product_uom_qty") or 0.0
        return super().create(vals_list)

    def write(self, vals):
        new_qty = vals.get("product_uom_qty")
        follow = self.env["sale.order.line"]
        if new_qty is not None and "qty_planned" not in vals:
            follow = self.filtered(
                lambda l: not l.display_type and l.qty_planned == l.product_uom_qty
            )
        res = super().write(vals)
        if follow:
            follow.qty_planned = new_qty
        return res

    @api.onchange("product_uom_qty")
    def _onchange_product_uom_qty_planned(self):
        if self.qty_planned == self._origin.product_uom_qty:
            self.qty_planned = self.product_uom_qty

    @api.depends(
        "display_type",
        "price_unit",
        "qty_planned",
        "order_id.planned_percent",
        "price_planned_manual",
    )
    def _compute_planned(self):
        for line in self:
            if line.display_type:
                line.price_planned = 0.0
                line.amount_planned = 0.0
                continue
            if line.price_planned_manual:
                line.price_planned = line.price_planned
                line.amount_planned = (line.price_planned or 0.0) * (
                    line.qty_planned or 0.0
                )
                continue
            pct = line.order_id.planned_percent or 0.0
            line.price_planned = (
                line.price_unit * (100.0 - pct) / 100.0 if pct else 0.0
            )
            line.amount_planned = line.price_planned * line.qty_planned

    def _inverse_price_planned(self):
        for line in self:
            if line.display_type:
                continue
            line.price_planned_manual = True
            line.amount_planned = (line.price_planned or 0.0) * (line.qty_planned or 0.0)

    def action_reset_price_planned(self):
        self.price_planned_manual = False
