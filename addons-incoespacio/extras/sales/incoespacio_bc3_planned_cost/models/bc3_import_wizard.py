from odoo import models


class Bc3ImportWizard(models.TransientModel):
    _inherit = "bc3.import.wizard"

    def _create_partida(
        self, code, concept, qty, concepts, tree, prices, level=0, parent="", detail=None
    ):
        super()._create_partida(
            code,
            concept,
            qty,
            concepts,
            tree,
            prices,
            level=level,
            parent=parent,
            detail=detail,
        )
        plist = concept.get("prices") or []
        if len(plist) < 2:
            return
        line_code = self._line_code(code)
        line = self.sale_id.order_line.filtered(
            lambda l: not l.display_type and l.bc3_code == line_code
        )[-1:]
        if line:
            line.write(
                {
                    "price_unit": max(plist),
                    "price_planned": min(plist),
                    "price_planned_manual": True,
                }
            )
