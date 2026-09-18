from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    chapter_cost_text = fields.Text(
        string="Coste por capítulo",
        compute="_compute_chapter_cost",
    )
    amount_cost_in_chapter = fields.Monetary(
        string="Imputado a capítulo",
        compute="_compute_chapter_cost",
        currency_field="currency_id",
    )
    amount_cost_no_chapter = fields.Monetary(
        string="Sin capítulo",
        compute="_compute_chapter_cost",
        currency_field="currency_id",
        help="Gasto de esta obra publicado sin capítulo en las líneas.",
    )

    @api.depends("project_id", "amount_job_cost", "order_line")
    def _compute_chapter_cost(self):
        Line = self.env["account.move.line"]
        for order in self:
            sections = order.order_line.filtered(lambda l: l.display_type == "line_section")
            in_chapter = 0.0
            by_sec = {}
            if sections:
                domain_base = [
                    ("construction_section_id", "in", sections.ids),
                    ("parent_state", "=", "posted"),
                ]
                for move_type, sign in (("in_invoice", 1.0), ("in_refund", -1.0)):
                    for g in Line.read_group(
                        domain_base + [("move_id.move_type", "=", move_type)],
                        ["price_subtotal:sum"],
                        ["construction_section_id"],
                    ):
                        amt = (g["price_subtotal"] or 0.0) * sign
                        sid = g["construction_section_id"][0]
                        by_sec[sid] = by_sec.get(sid, 0.0) + amt
                        in_chapter += amt
            order.amount_cost_in_chapter = in_chapter
            order.amount_cost_no_chapter = (order.amount_job_cost or 0.0) - in_chapter
            rows = [
                f"{sec.name}: {by_sec[sec.id]:.2f} {order.currency_id.symbol or ''}"
                for sec in sections
                if by_sec.get(sec.id)
            ]
            order.chapter_cost_text = "\n".join(rows) if rows else False
