import re
import unicodedata

from odoo import fields, models


def _fold(text):
    text = unicodedata.normalize("NFD", text or "")
    return "".join(c for c in text if unicodedata.category(c) != "Mn").lower()


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    construction_section_id = fields.Many2one(
        "sale.order.line",
        string="Capítulo de obra",
        domain="[('display_type', '=', 'line_section')]",
        ondelete="set null",
    )

    def _match_bc3_section(self, sections):
        self.ensure_one()
        desc = _fold(self.name)
        if not desc or not sections:
            return self.env["sale.order.line"]
        blobs = {sec.id: _fold(sec.name) for sec in sections}
        current = False
        for sol in sections.order_id.order_line.sorted(
            lambda l: (l.sequence, l._origin.id or 0)
        ):
            if sol.display_type == "line_section":
                current = sol.id
            elif current in blobs and sol.display_type not in ("line_section", "line_note"):
                blobs[current] += " " + _fold(sol.name)
        words = [w for w in re.findall(r"[a-z0-9]+", desc) if len(w) > 4]
        best, score, tied = self.env["sale.order.line"], 0, False
        for sec in sections:
            hits = sum(1 for w in words if w in blobs.get(sec.id, ""))
            if hits > score:
                best, score, tied = sec, hits, False
            elif hits == score and hits > 0:
                tied = True
        return self.env["sale.order.line"] if tied or not score else best
