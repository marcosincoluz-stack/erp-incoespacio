from odoo import api, fields, models, _


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    construction_line_suggested_id = fields.Many2one(
        "sale.order.line",
        compute="_compute_construction_line_suggested",
        string="Partida sugerida",
    )
    review_reason = fields.Char(compute="_compute_review_reason", string="Motivo")

    def write(self, vals):
        if list(vals) == ["construction_line_id"]:
            self = self.with_context(
                check_move_validity=False,
                skip_invoice_sync=True,
            )
        return super().write(vals)

    def _partidas_for_suggestion(self):
        self.ensure_one()
        if not self.move_id.project_id:
            return self.env["sale.order.line"]
        order = self.env["sale.order"].search(
            [("project_id", "=", self.move_id.project_id.id)],
            limit=1,
        )
        last = order.certification_ids.filtered(
            lambda c: c.state == "invoiced"
        ).sorted("number")[-1:]
        full = {
            line.sale_order_line_id.id
            for line in last.line_ids
            if line.sale_order_line_id
            and not line.display_type
            and line.qty_budget
            and line.qty_origin >= line.qty_budget
        }
        current = self.construction_line_id.id
        partidas = order.order_line.filtered(
            lambda l: not l.display_type and l.id != current and l.id not in full
        )
        section = self.construction_section_id or (
            self._section_of(self.construction_line_id)
            if self.construction_line_id
            else self.env["sale.order.line"]
        )
        if section:
            partidas = partidas.filtered(lambda l: self._section_of(l) == section)
        return partidas

    @api.depends(
        "name",
        "construction_line_id",
        "construction_section_id",
        "move_id.project_id",
    )
    def _compute_construction_line_suggested(self):
        for aml in self:
            aml.construction_line_suggested_id = (
                aml._match_bc3_line(aml._partidas_for_suggestion())
                if aml.display_type == "product"
                else False
            )

    @api.depends("construction_line_id")
    def _compute_review_reason(self):
        cert = self.env["construction.certification"].browse(
            self.env.context.get("certification_id")
        )
        alerts = {
            line.sale_order_line_id.id: line.cost_alert
            for line in cert.line_ids
            if line.cost_alert and line.sale_order_line_id
        }
        for aml in self:
            alert = alerts.get(aml.construction_line_id.id)
            if not aml.construction_line_id:
                aml.review_reason = _("Sin partida")
            elif alert == "over_sale":
                aml.review_reason = _("Coste supera venta")
            elif alert == "certified":
                aml.review_reason = _("Partida ya certificada")
            else:
                aml.review_reason = False

    def action_use_suggested_partida(self):
        for line in self:
            if line.construction_line_suggested_id:
                line.construction_line_id = line.construction_line_suggested_id
