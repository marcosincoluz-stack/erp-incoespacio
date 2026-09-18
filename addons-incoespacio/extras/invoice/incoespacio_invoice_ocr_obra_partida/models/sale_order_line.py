import re

from odoo import api, fields, models

# ponytail: corte en unidad+punto (m². descripción larga); 90 chars si no hay unidad
_UNIT_DOT = re.compile(r"(?i)(?:m[²³23]|m³|ud|kg)\.\s+")


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    bc3_section_id = fields.Many2one(
        "sale.order.line",
        string="Capítulo BC3",
        compute="_compute_bc3_section_id",
        store=True,
        index=True,
    )

    @api.depends(
        "display_type",
        "sequence",
        "order_id",
        "order_id.order_line",
        "order_id.order_line.display_type",
        "order_id.order_line.sequence",
    )
    def _compute_bc3_section_id(self):
        section_of = {}
        for order in self.mapped("order_id"):
            section = self.env["sale.order.line"]
            for line in order.order_line.sorted(
                lambda l: (l.sequence, l._origin.id or 0)
            ):
                if line.display_type == "line_section":
                    section = line
                    section_of[line.id] = False
                else:
                    section_of[line.id] = section
        for line in self:
            line.bc3_section_id = section_of.get(line.id) or False

    def _short_construction_label(self):
        self.ensure_one()
        raw = (self.name or "").replace("\n", " ").strip()
        unit = _UNIT_DOT.search(raw)
        if unit and len(raw) - unit.end() > 30:
            short = raw[: unit.end()].rstrip(". ").strip()
        else:
            short = raw
        if len(short) > 90:
            short = short[:87].rstrip() + "…"
        code = self.bc3_code or ""
        if code and "[%s]" % code not in short:
            short = "[%s] %s" % (code, short) if short else "[%s]" % code
        return short or (self.product_id.name if self.product_id else "")

    amount_vendor_cost = fields.Monetary(
        string="Coste",
        compute="_compute_amount_vendor_cost",
        currency_field="currency_id",
    )

    @api.depends("display_type")
    def _compute_amount_vendor_cost(self):
        Line = self.env["account.move.line"]
        sols = self.filtered(lambda l: not l.display_type)
        by_sol = {}
        if sols:
            domain_base = [
                ("construction_line_id", "in", sols.ids),
                ("parent_state", "=", "posted"),
            ]
            for move_type, sign in (("in_invoice", 1.0), ("in_refund", -1.0)):
                for g in Line.read_group(
                    domain_base + [("move_id.move_type", "=", move_type)],
                    ["price_subtotal:sum"],
                    ["construction_line_id"],
                ):
                    sid = g["construction_line_id"][0]
                    by_sol[sid] = by_sol.get(sid, 0.0) + (g["price_subtotal"] or 0.0) * sign
        for line in self:
            line.amount_vendor_cost = (
                by_sol.get(line.id, 0.0) if not line.display_type else 0.0
            )

    def _compute_display_name(self):
        if not self.env.context.get("short_construction_line"):
            return super()._compute_display_name()
        for line in self:
            line.display_name = line._short_construction_label()
