from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ConstructionCertification(models.Model):
    _inherit = "construction.certification"

    suggest_by = fields.Selection(
        [
            ("cost", "Por coste objetivo"),
            ("qty", "Por cantidad facturada"),
        ],
        compute="_compute_suggest_by",
        store=True,
        readonly=False,
        string="Sugerir medición",
    )
    assistant_line_count = fields.Integer(compute="_compute_assistant_totals")
    assistant_pending_cost = fields.Monetary(
        compute="_compute_assistant_totals",
        currency_field="currency_id",
    )
    assistant_suggested_amount = fields.Monetary(
        compute="_compute_assistant_totals",
        currency_field="currency_id",
    )
    assistant_suggested_percent = fields.Float(compute="_compute_assistant_totals")
    previous_cert_date = fields.Date(compute="_compute_previous_cert_date")
    pending_bill_period_ids = fields.Many2many(
        "account.move",
        compute="_compute_pending_bill_split",
        string="Facturas del periodo",
    )
    pending_bill_late_ids = fields.Many2many(
        "account.move",
        compute="_compute_pending_bill_split",
        string="Facturas de periodos anteriores",
    )
    pending_bill_late_count = fields.Integer(compute="_compute_pending_bill_split")
    pending_review_line_ids = fields.Many2many(
        "account.move.line",
        compute="_compute_pending_review",
        inverse="_inverse_pending_review",
        string="Líneas a revisar",
    )

    @api.depends("order_id.planned_percent", "order_id.order_line.price_planned")
    def _compute_suggest_by(self):
        for cert in self:
            cert.suggest_by = (
                "cost"
                if cert.order_id.planned_percent
                or any(cert.order_id.order_line.mapped("price_planned"))
                else "qty"
            )

    @api.depends(
        "line_ids.needs_measure",
        "line_ids.pending_cost_amount",
        "line_ids.qty_suggested",
        "line_ids.price_unit",
    )
    def _compute_assistant_totals(self):
        for cert in self:
            pending = cert.line_ids.filtered(lambda l: not l.display_type)
            need = pending.filtered("needs_measure")
            cost = sum(pending.mapped("pending_cost_amount"))
            suggested = sum(l.qty_suggested * l.price_unit for l in need)
            cert.assistant_line_count = len(need)
            cert.assistant_pending_cost = cost
            cert.assistant_suggested_amount = suggested
            cert.assistant_suggested_percent = (
                suggested / cost * 100.0 if cost else 0.0
            )

    @api.depends(
        "order_id.certification_ids.number",
        "order_id.certification_ids.date",
        "order_id.certification_ids.state",
        "number",
    )
    def _compute_previous_cert_date(self):
        for cert in self:
            prev = cert.order_id.certification_ids.filtered(
                lambda c: c.state != "cancel" and c.number < cert.number
            ).sorted("number")
            cert.previous_cert_date = prev[-1].date if prev else False

    @api.depends("project_id", "date", "state", "previous_cert_date")
    def _compute_pending_bill_split(self):
        Move = self.env["account.move"]
        for cert in self:
            bills = cert.pending_bill_ids
            cutoff = cert.previous_cert_date
            late = (
                bills.filtered(lambda b: b.invoice_date and b.invoice_date <= cutoff)
                if cutoff
                else Move
            )
            cert.pending_bill_late_ids = late
            cert.pending_bill_period_ids = bills - late
            cert.pending_bill_late_count = len(late)

    @api.depends("project_id", "date", "state", "line_ids.cost_alert")
    def _compute_pending_review(self):
        Line = self.env["account.move.line"]
        for cert in self:
            bills = cert.pending_bill_ids
            if not bills:
                cert.pending_review_line_ids = Line
                continue
            alert_sols = cert.line_ids.filtered("cost_alert").mapped(
                "sale_order_line_id"
            )
            cert.pending_review_line_ids = bills.invoice_line_ids.filtered(
                lambda l: l.display_type == "product"
                and (
                    not l.construction_line_id
                    or l.construction_line_id in alert_sols
                )
            )

    def _inverse_pending_review(self):
        return

    def action_confirm(self):
        self.ensure_one()
        measured = self.line_ids.filtered(
            lambda l: not l.display_type and l.qty_period and l.pending_cost_amount
        )
        notes = [
            "%s: +%s (%s)"
            % (
                line.code or (line.name or "").splitlines()[0],
                line.qty_period,
                line.pending_bill_names,
            )
            for line in measured
        ]
        res = super().action_confirm()
        if notes:
            self.message_post(
                body=_("Partidas medidas con factura: %s") % "; ".join(notes)
            )
        return res


class ConstructionCertificationLine(models.Model):
    _inherit = "construction.certification.line"

    pending_cost_amount = fields.Monetary(
        compute="_compute_pending_cost",
        currency_field="currency_id",
        string="Coste pend.",
    )
    pending_cost_qty = fields.Float(
        compute="_compute_pending_cost",
        digits="Product Unit of Measure",
    )
    pending_bill_names = fields.Char(compute="_compute_pending_cost", string="Facturas")
    needs_measure = fields.Boolean(compute="_compute_pending_cost")
    qty_suggested = fields.Float(
        compute="_compute_pending_cost",
        digits="Product Unit of Measure",
        string="Med. sug.",
    )
    cost_alert = fields.Selection(
        [
            ("over_sale", "Coste supera venta"),
            ("certified", "Ya certificada"),
        ],
        compute="_compute_pending_cost",
    )
    uom_mismatch = fields.Boolean(compute="_compute_pending_cost")
    suggest_basis = fields.Selection(
        [
            ("qty", "Cantidad factura"),
            ("planned", "Coste / P. objetivo"),
            ("sale", "Coste / P.U. venta"),
        ],
        compute="_compute_pending_cost",
        string="Base sug.",
    )

    @api.depends(
        "sale_order_line_id",
        "sale_order_line_id.price_planned",
        "sale_order_line_id.product_uom",
        "qty_period",
        "qty_budget",
        "qty_previous",
        "price_unit",
        "display_type",
        "certification_id.project_id",
        "certification_id.date",
        "certification_id.state",
        "certification_id.suggest_by",
    )
    def _compute_pending_cost(self):
        Line = self.env["account.move.line"]
        by_cert = {}
        for cert in self.certification_id:
            sols = cert.line_ids.mapped("sale_order_line_id")
            bills = cert.pending_bill_ids
            by_sol = {}
            if sols and bills:
                for aml in Line.search(
                    [
                        ("move_id", "in", bills.ids),
                        ("display_type", "=", "product"),
                        ("construction_line_id", "in", sols.ids),
                    ]
                ):
                    rec = by_sol.setdefault(
                        aml.construction_line_id.id,
                        {"amount": 0.0, "qty": 0.0, "names": set(), "mismatch": False},
                    )
                    sign = -1.0 if aml.move_id.move_type == "in_refund" else 1.0
                    rec["amount"] += (aml.price_subtotal or 0.0) * sign
                    qty, mismatch = self._aml_qty_in_sol_uom(
                        aml, aml.construction_line_id
                    )
                    if mismatch:
                        rec["mismatch"] = True
                    else:
                        rec["qty"] += qty * sign
                    rec["names"].add(aml.move_id.name)
            by_cert[cert.id] = by_sol
        for line in self:
            data = (
                by_cert.get(line.certification_id.id, {}).get(
                    line.sale_order_line_id.id, {}
                )
                if line.sale_order_line_id and not line.display_type
                else {}
            )
            amount = data.get("amount", 0.0)
            qty = data.get("qty", 0.0)
            mismatch = data.get("mismatch", False)
            line.pending_cost_amount = amount
            line.pending_cost_qty = qty
            line.pending_bill_names = ", ".join(sorted(data.get("names", [])))
            line.needs_measure = bool(amount) and not line.qty_period
            line.uom_mismatch = mismatch
            remaining = (
                max(line.qty_budget - line.qty_previous, 0.0) if line.qty_budget else 0.0
            )
            if amount:
                basis, raw = line._suggestion(amount, qty, mismatch)
            else:
                basis, raw = False, 0.0
            line.suggest_basis = basis
            # ponytail: tope al presupuesto restante
            if line.qty_budget:
                line.qty_suggested = min(raw, remaining) if raw > 0 else 0.0
            else:
                line.qty_suggested = raw if raw > 0 else 0.0
            sale_left = remaining * (line.price_unit or 0.0)
            if line.qty_budget and line.qty_previous >= line.qty_budget and amount:
                line.cost_alert = "certified"
            elif amount > sale_left:
                line.cost_alert = "over_sale"
            else:
                line.cost_alert = False

    @api.model
    def _aml_qty_in_sol_uom(self, aml, sol):
        qty = aml.quantity or 0.0
        src = aml.product_uom_id
        dst = sol.product_uom
        if not src or not dst or src == dst:
            return qty, False
        if src.category_id != dst.category_id:
            return 0.0, True
        try:
            return src._compute_quantity(qty, dst), False
        except UserError:
            return 0.0, True

    def _suggestion(self, amount, qty, mismatch):
        planned = (
            self.sale_order_line_id.price_planned if self.sale_order_line_id else 0.0
        )
        sale_pu = self.price_unit or 0.0
        if self.certification_id.suggest_by == "qty" and not mismatch:
            return "qty", qty
        if planned:
            return "planned", amount / planned
        if sale_pu:
            return "sale", amount / sale_pu
        return "sale", 0.0

    def action_apply_suggested(self):
        for line in self:
            if line.qty_suggested:
                line.qty_period = line.qty_suggested

    def action_create_modification(self):
        self.ensure_one()
        origin = self.sale_order_line_id
        if not origin:
            raise UserError(_("La partida no está ligada al presupuesto."))
        order = origin.order_id
        pct = order.planned_percent or 0.0
        cost = self.pending_cost_amount
        price = cost / ((100.0 - pct) / 100.0) if pct else cost
        today = fields.Date.context_today(self)
        n = len(order.order_line.filtered("is_modification")) + 1
        code = self.code or getattr(origin, "bc3_code", False) or ""
        sol = order.order_line.create(
            {
                "order_id": order.id,
                "product_id": origin.product_id.id,
                "name": _("Modificado s/ [%s] — %s")
                % (code, self.pending_bill_names),
                "product_uom_qty": 1,
                "price_unit": price,
                "is_modification": True,
                "modification_ref": _("Mod. %s — %s") % (n, today),
                "tax_id": [(6, 0, origin.tax_id.ids)],
            }
        )
        self.create(
            {
                "certification_id": self.certification_id.id,
                "sale_order_line_id": sol.id,
                "sequence": self.sequence + 1,
                "code": "MOD",
                "name": sol.name,
                "is_modification": True,
                "product_uom_id": self.product_uom_id.id,
                "price_unit": price,
                "qty_budget": 1,
                "qty_previous": 0,
                "qty_origin": 1,
                "tax_ids": [(6, 0, self.tax_ids.ids)],
            }
        )
        bills = self.certification_id.pending_bill_ids
        self.env["account.move.line"].search(
            [
                ("move_id", "in", bills.ids),
                ("construction_line_id", "=", origin.id),
                ("display_type", "=", "product"),
            ]
        ).write({"construction_line_id": sol.id})
        self.certification_id.message_post(
            body=_("Modificado creado s/ %s (%s).") % (code, self.pending_bill_names)
        )
