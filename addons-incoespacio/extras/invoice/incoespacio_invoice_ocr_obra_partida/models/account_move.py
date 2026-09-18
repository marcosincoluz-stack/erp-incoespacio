from odoo import _, api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    has_unassigned_partida = fields.Boolean(
        compute="_compute_has_unassigned_partida",
        search="_search_has_unassigned_partida",
    )

    @api.depends("invoice_line_ids.construction_line_id", "invoice_line_ids.display_type")
    def _compute_has_unassigned_partida(self):
        for move in self:
            move.has_unassigned_partida = any(
                line.display_type == "product" and not line.construction_line_id
                for line in move.invoice_line_ids
            )

    @api.model
    def _search_has_unassigned_partida(self, operator, value):
        if operator not in ("=", "!="):
            return [("id", "=", False)]
        wanted = (operator == "=" and value) or (operator == "!=" and not value)
        moves = (
            self.env["account.move.line"]
            .search(
                [
                    ("display_type", "=", "product"),
                    ("construction_line_id", "=", False),
                    ("move_id.move_type", "in", ("in_invoice", "in_refund")),
                ]
            )
            .move_id
        )
        return [("id", "in" if wanted else "not in", moves.ids)]

    def action_assign_partida(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Imputar a partidas"),
            "res_model": "ocr.obra.assign.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_move_id": self.id},
        }

    def _suggest_partidas(self):
        self.ensure_one()
        if not self.project_id:
            return
        so = self.env["sale.order"].search(
            [("project_id", "=", self.project_id.id), ("state", "in", ("sale", "done"))],
            limit=1,
        )
        partidas = so.order_line.filtered(lambda l: not l.display_type)
        if not partidas:
            return
        for line in self.invoice_line_ids.filtered(lambda l: l.display_type == "product"):
            if (
                line.construction_line_id
                and line.construction_line_id.order_id.project_id == self.project_id
            ):
                continue
            pool = partidas
            if line.construction_section_id:
                pool = partidas.filtered(
                    lambda p: p.bc3_section_id == line.construction_section_id
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
        products = last.invoice_line_ids.filtered(lambda l: l.display_type == "product")
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
        for line in self.invoice_line_ids.filtered(lambda l: l.display_type == "product"):
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
