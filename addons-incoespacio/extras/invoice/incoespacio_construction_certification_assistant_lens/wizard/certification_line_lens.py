from odoo import api, fields, models, _


class ConstructionCertificationLine(models.Model):
    _inherit = "construction.certification.line"

    def action_open_lens(self):
        self.ensure_one()
        label = (self.name or "").splitlines()[0]
        title = "[%s] %s" % (self.code, label) if self.code else (label or _("Partida"))
        return {
            "type": "ir.actions.act_window",
            "name": title,
            "res_model": "certification.line.lens",
            "view_mode": "form",
            "target": "new",
            "context": {"default_line_id": self.id},
        }


class CertificationLineLens(models.TransientModel):
    _name = "certification.line.lens"
    _description = "Lupa de partida de certificación"

    line_id = fields.Many2one(
        "construction.certification.line", required=True, ondelete="cascade"
    )
    sol_id = fields.Many2one(related="line_id.sale_order_line_id")
    order_id = fields.Many2one(related="line_id.certification_id.order_id")
    currency_id = fields.Many2one(related="line_id.currency_id")
    code = fields.Char(related="line_id.code")
    name = fields.Text(related="line_id.name")
    product_uom_id = fields.Many2one(related="line_id.product_uom_id")
    qty_budget = fields.Float(related="line_id.qty_budget")
    qty_previous = fields.Float(related="line_id.qty_previous")
    price_unit = fields.Float(related="line_id.price_unit")
    price_planned = fields.Float(related="sol_id.price_planned")
    planned_percent = fields.Float(related="sol_id.order_id.planned_percent")
    pending_cost_qty = fields.Float(related="line_id.pending_cost_qty")
    pending_cost_amount = fields.Monetary(
        related="line_id.pending_cost_amount", currency_field="currency_id"
    )
    pending_bill_names = fields.Char(related="line_id.pending_bill_names")
    cost_alert = fields.Selection(related="line_id.cost_alert")
    qty_suggested = fields.Float(related="line_id.qty_suggested")
    suggest_basis = fields.Selection(related="line_id.suggest_basis")
    qty_remaining = fields.Float(compute="_compute_remaining")
    amount_remaining = fields.Monetary(
        compute="_compute_remaining", currency_field="currency_id"
    )
    amount_planned_remaining = fields.Monetary(
        compute="_compute_remaining", currency_field="currency_id"
    )
    price_unit_cost = fields.Float(compute="_compute_cost_metrics")
    cost_vs_planned_percent = fields.Float(compute="_compute_cost_metrics")
    verdict = fields.Char(compute="_compute_verdict")
    verdict_level = fields.Selection(
        [("danger", "danger"), ("warning", "warning"), ("success", "success")],
        compute="_compute_verdict",
    )
    qty_period = fields.Float(digits="Product Unit of Measure", string="Med. periodo")
    amount_period_new = fields.Monetary(
        compute="_compute_preview", currency_field="currency_id"
    )
    percent_origin_new = fields.Float(compute="_compute_preview")
    margin_new = fields.Monetary(
        compute="_compute_preview", currency_field="currency_id"
    )
    margin_percent_new = fields.Float(compute="_compute_preview")
    bill_line_ids = fields.One2many(
        "certification.line.lens.bill", "wizard_id", string="Facturas imputadas"
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        line = self.env["construction.certification.line"].browse(
            res.get("line_id") or self.env.context.get("default_line_id")
        )
        if not line:
            return res
        res["line_id"] = line.id
        if "qty_period" in fields_list:
            res["qty_period"] = line.qty_period or line.qty_suggested
        if "bill_line_ids" in fields_list:
            amls = line.certification_id.pending_bill_ids.invoice_line_ids.filtered(
                lambda l: l.display_type == "product"
                and l.construction_line_id == line.sale_order_line_id
            )
            res["bill_line_ids"] = [
                (
                    0,
                    0,
                    {
                        "move_line_id": aml.id,
                        "construction_line_id": aml.construction_line_id.id,
                    },
                )
                for aml in amls
            ]
        return res

    @api.depends("qty_budget", "qty_previous", "price_unit", "price_planned")
    def _compute_remaining(self):
        for wiz in self:
            remaining = max((wiz.qty_budget or 0.0) - (wiz.qty_previous or 0.0), 0.0)
            wiz.qty_remaining = remaining
            wiz.amount_remaining = remaining * (wiz.price_unit or 0.0)
            wiz.amount_planned_remaining = remaining * (wiz.price_planned or 0.0)

    @api.depends(
        "pending_cost_amount", "pending_cost_qty", "qty_remaining", "price_planned"
    )
    def _compute_cost_metrics(self):
        for wiz in self:
            qty = wiz.pending_cost_qty or 0.0
            wiz.price_unit_cost = (wiz.pending_cost_amount / qty) if qty else 0.0
            planned_left = wiz.qty_remaining * (wiz.price_planned or 0.0)
            wiz.cost_vs_planned_percent = (
                wiz.pending_cost_amount / planned_left * 100.0 if planned_left else 0.0
            )

    @api.depends(
        "qty_period", "price_unit", "qty_previous", "qty_budget", "pending_cost_amount"
    )
    def _compute_preview(self):
        for wiz in self:
            amount = (wiz.qty_period or 0.0) * (wiz.price_unit or 0.0)
            budget = wiz.qty_budget or 0.0
            wiz.amount_period_new = amount
            wiz.percent_origin_new = (
                ((wiz.qty_previous or 0.0) + (wiz.qty_period or 0.0)) / budget * 100.0
                if budget
                else 0.0
            )
            wiz.margin_new = amount - (wiz.pending_cost_amount or 0.0)
            wiz.margin_percent_new = wiz.margin_new / amount * 100.0 if amount else 0.0

    @api.depends(
        "cost_alert",
        "pending_cost_amount",
        "amount_remaining",
        "cost_vs_planned_percent",
        "qty_suggested",
        "suggest_basis",
        "amount_period_new",
        "margin_new",
        "price_unit",
    )
    def _compute_verdict(self):
        basis_note = {
            "qty": _("sugerida por cantidad facturada"),
            "planned": _("sugerida por coste / P.U. objetivo"),
            "sale": _("sugerida por coste / P.U. venta (sin objetivo)"),
        }
        for wiz in self:
            cost = wiz.pending_cost_amount or 0.0
            sale_left = wiz.amount_remaining or 0.0
            suffix = basis_note.get(wiz.suggest_basis)
            suffix = (" %s." % suffix) if suffix else ""
            if wiz.cost_alert == "over_sale":
                wiz.verdict_level = "danger"
                wiz.verdict = _(
                    "La factura (%.2f) supera la venta que queda por certificar (%.2f). "
                    "Crea un modificado o reparte el coste."
                ) % (cost, sale_left) + suffix
            elif wiz.cost_alert == "certified":
                wiz.verdict_level = "warning"
                wiz.verdict = _(
                    "Esta partida ya está certificada al 100 %. "
                    "El coste debería ir a otra partida."
                ) + suffix
            elif wiz.cost_vs_planned_percent > 100:
                wiz.verdict_level = "warning"
                wiz.verdict = _(
                    "El coste supera el objetivo (%.0f %% del objetivo restante). "
                    "Certificando esta medición el margen es %.2f."
                ) % (wiz.cost_vs_planned_percent, wiz.margin_new) + suffix
            else:
                wiz.verdict_level = "success"
                suggested = wiz.qty_suggested or 0.0
                wiz.verdict = _(
                    "Coste dentro de objetivo (%.0f %%). "
                    "Sugerido certificar %s ud. por %.2f."
                ) % (
                    wiz.cost_vs_planned_percent,
                    suggested,
                    suggested * (wiz.price_unit or 0.0),
                ) + suffix

    def _reopen(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_use_suggested(self):
        self.qty_period = self.qty_suggested
        return self._reopen()

    def action_fill_remaining(self):
        self.qty_period = self.qty_remaining
        return self._reopen()

    def action_create_modification(self):
        self.ensure_one()
        self.line_id.action_create_modification()
        return {"type": "ir.actions.act_window_close"}

    def action_accept(self):
        self.ensure_one()
        self.line_id.qty_period = self.qty_period
        for bill in self.bill_line_ids:
            if bill.move_line_id.construction_line_id != bill.construction_line_id:
                bill.move_line_id.write(
                    {"construction_line_id": bill.construction_line_id.id}
                )
        return {"type": "ir.actions.act_window_close"}


class CertificationLineLensBill(models.TransientModel):
    _name = "certification.line.lens.bill"
    _description = "Línea de factura en lupa de partida"

    wizard_id = fields.Many2one(
        "certification.line.lens", required=True, ondelete="cascade"
    )
    move_line_id = fields.Many2one(
        "account.move.line", required=True, ondelete="cascade"
    )
    move_id = fields.Many2one(related="move_line_id.move_id")
    name = fields.Char(related="move_line_id.name")
    quantity = fields.Float(related="move_line_id.quantity")
    currency_id = fields.Many2one(related="move_line_id.currency_id")
    price_subtotal = fields.Monetary(
        related="move_line_id.price_subtotal", currency_field="currency_id"
    )
    construction_section_id = fields.Many2one(
        related="move_line_id.construction_section_id"
    )
    order_id = fields.Many2one(related="wizard_id.order_id")
    construction_line_id = fields.Many2one(
        "sale.order.line",
        string="Partida",
        domain="[('order_id', '=', order_id), ('display_type', '=', False), ('bc3_section_id', '=?', construction_section_id)]",
    )

    def action_split_partida(self):
        self.ensure_one()
        return self.move_line_id.action_split_partida()
