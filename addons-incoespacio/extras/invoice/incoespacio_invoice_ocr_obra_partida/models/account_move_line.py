import re

from odoo import api, fields, models, _

from odoo.addons.incoespacio_invoice_ocr_obra.models.account_move_line import _fold


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    construction_line_id = fields.Many2one(
        "sale.order.line",
        string="Partida de obra",
        domain="[('display_type', '=', False)]",
        ondelete="set null",
    )

    def _section_of(self, sol):
        section = sol.env["sale.order.line"] if sol else self.env["sale.order.line"]
        if not sol:
            return section
        for line in sol.order_id.order_line.sorted(
            lambda l: (l.sequence, l._origin.id or 0)
        ):
            if line.display_type == "line_section":
                section = line
            elif line == sol:
                return section
        return section

    def _match_bc3_line(self, partidas):
        self.ensure_one()
        desc = _fold(self.name)
        if not desc or not partidas:
            return self.env["sale.order.line"]
        words = [w for w in re.findall(r"[a-z0-9]+", desc) if len(w) > 4]
        best, score, tied = self.env["sale.order.line"], 0, False
        for sol in partidas:
            blob = _fold("%s %s" % (sol.bc3_code or "", sol.name or ""))
            hits = sum(1 for w in words if w in blob)
            if hits > score:
                best, score, tied = sol, hits, False
            elif hits == score and hits > 0:
                tied = True
        return self.env["sale.order.line"] if tied or not score else best

    def _sync_section_from_partida(self):
        for line in self:
            if not line.construction_line_id:
                continue
            section = line._section_of(line.construction_line_id)
            if section and line.construction_section_id != section:
                super(AccountMoveLine, line).write({"construction_section_id": section.id})

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._sync_section_from_partida()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if vals.get("construction_line_id"):
            self._sync_section_from_partida()
        elif "construction_section_id" in vals and "construction_line_id" not in vals:
            for line in self:
                if (
                    line.construction_line_id
                    and line._section_of(line.construction_line_id) != line.construction_section_id
                ):
                    super(AccountMoveLine, line).write({"construction_line_id": False})
        return res

    @api.onchange("construction_line_id")
    def _onchange_construction_line_id(self):
        if self.construction_line_id:
            self.construction_section_id = self._section_of(self.construction_line_id)

    @api.onchange("construction_section_id")
    def _onchange_construction_section_clears_line(self):
        if (
            self.construction_line_id
            and self._section_of(self.construction_line_id) != self.construction_section_id
        ):
            self.construction_line_id = False

    def action_split_partida(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Repartir entre partidas"),
            "res_model": "ocr.obra.split.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_line_id": self.id},
        }
