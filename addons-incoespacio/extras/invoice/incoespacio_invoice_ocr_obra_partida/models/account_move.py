from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _suggest_partidas(self):
        self.ensure_one()
        if not self.project_id:
            return
        so = self.env["sale.order"].search(
            [("project_id", "=", self.project_id.id), ("state", "in", ("sale", "done"))],
            limit=1,
        )
        partidas = so.order_line.filtered(lambda line: not line.display_type)
        if not partidas:
            return
        for line in self.invoice_line_ids.filtered(lambda item: item.display_type == "product"):
            if (
                line.construction_line_id
                and line.construction_line_id.order_id.project_id == self.project_id
            ):
                continue
            pool = partidas
            if line.construction_section_id:
                pool = partidas.filtered(
                    lambda partida: partida.bc3_section_id == line.construction_section_id
                )
            matched = line._match_bc3_line(pool)
            if matched:
                line.construction_line_id = matched.id

    def _sticky_partidas(self):
        self.ensure_one()
        if not self.partner_id or not self.project_id:
            return
        last = self.search(
            [
                ("partner_id", "=", self.partner_id.id),
                ("project_id", "=", self.project_id.id),
                ("move_type", "in", ("in_invoice", "in_refund")),
                ("state", "=", "posted"),
                ("id", "!=", self._origin.id or 0),
            ],
            order="invoice_date desc, id desc",
            limit=1,
        )
        if not last:
            return
        products = last.invoice_line_ids.filtered(lambda line: line.display_type == "product")
        uos = products.mapped("construction_line_id")
        if (
            not products
            or len(uos) != 1
            or any(not line.construction_line_id for line in products)
        ):
            return
        sticky = uos
        so = sticky.order_id
        if so.project_id != self.project_id:
            return
        for line in self.invoice_line_ids.filtered(lambda item: item.display_type == "product"):
            if line.construction_line_id:
                continue
            if (
                line.construction_section_id
                and sticky.bc3_section_id
                and sticky.bc3_section_id != line.construction_section_id
            ):
                continue
            line.construction_line_id = sticky.id

    def _suggest_chapters(self):
        super()._suggest_chapters()
        self._suggest_partidas()
        self._sticky_partidas()
