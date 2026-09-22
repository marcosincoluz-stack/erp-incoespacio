from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    project_id = fields.Many2one(
        "project.project",
        string="Proyecto / Obra",
        copy=False,
    )
    certification_ids = fields.One2many(
        "construction.certification",
        "order_id",
        string="Certificaciones de Obra",
    )
    certification_count = fields.Integer(
        string="Nº Certificaciones",
        compute="_compute_certification_count",
    )
    vendor_bill_count = fields.Integer(
        string="Gastos",
        compute="_compute_vendor_bill_count",
    )
    retention_return_invoice_id = fields.Many2one(
        "account.move",
        string="Factura devolución retención",
        copy=False,
        readonly=True,
    )
    retention_return_invoice_ids = fields.One2many(
        "account.move",
        "retention_order_id",
        string="Devoluciones de retención",
    )
    amount_retention_held = fields.Monetary(
        string="Retención acumulada",
        compute="_compute_retention",
        currency_field="currency_id",
    )
    amount_retention_returned = fields.Monetary(
        string="Retención devuelta",
        compute="_compute_retention",
        currency_field="currency_id",
    )
    amount_retention_to_return = fields.Monetary(
        string="Retención pendiente",
        compute="_compute_retention",
        currency_field="currency_id",
    )
    can_return_retention = fields.Boolean(compute="_compute_retention")
    amount_certified_origin = fields.Monetary(
        string="Certificado a origen",
        compute="_compute_job_margin",
        currency_field="currency_id",
    )
    amount_job_cost = fields.Monetary(
        string="Coste de obra",
        compute="_compute_job_margin",
        currency_field="currency_id",
    )
    amount_job_margin = fields.Monetary(
        string="Margen",
        compute="_compute_job_margin",
        currency_field="currency_id",
    )
    amount_job_po = fields.Monetary(
        string="Comprometido",
        compute="_compute_job_po",
        currency_field="currency_id",
        help="Pedidos de compra confirmados aún no facturados de esta obra.",
    )

    @api.depends("certification_ids")
    def _compute_certification_count(self):
        for order in self:
            order.certification_count = len(order.certification_ids)

    @api.depends("project_id")
    def _compute_vendor_bill_count(self):
        grouped = self.env["account.move"].read_group(
            [
                ("construction_order_id", "in", self.ids),
                ("move_type", "in", ("in_invoice", "in_refund")),
                ("state", "=", "posted"),
            ],
            ["construction_order_id"],
            ["construction_order_id"],
        )
        counts = {
            g["construction_order_id"][0]: g["construction_order_id_count"]
            for g in grouped
        }
        for order in self:
            order.vendor_bill_count = counts.get(order.id, 0)

    def action_view_vendor_bills(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "account.action_move_in_invoice_type"
        )
        action["domain"] = [
            ("construction_order_id", "=", self.id),
            ("move_type", "in", ("in_invoice", "in_refund")),
            ("state", "=", "posted"),
        ]
        action["context"] = {"default_move_type": "in_invoice", "create": False}
        return action

    @api.depends(
        "certification_ids.state",
        "certification_ids.amount_retention",
        "retention_return_invoice_ids.state",
        "retention_return_invoice_ids.amount_untaxed",
    )
    def _compute_retention(self):
        for order in self:
            held = sum(
                order.certification_ids.filtered(lambda c: c.state == "invoiced").mapped(
                    "amount_retention"
                )
            )
            returned = sum(
                inv.amount_untaxed
                for inv in order.retention_return_invoice_ids
                if inv.state != "cancel"
            )
            pending = held - returned
            open_certs = order.certification_ids.filtered(
                lambda c: c.state in ("draft", "confirmed")
            )
            order.amount_retention_held = held
            order.amount_retention_returned = returned
            order.amount_retention_to_return = pending
            order.can_return_retention = pending > 0 and not open_certs

    @api.depends(
        "certification_ids.state",
        "certification_ids.amount_total_origin",
        "project_id",
    )
    def _compute_job_margin(self):
        Move = self.env["account.move"]
        projects = self.mapped("project_id")
        cost_by_project = {}
        if projects:
            for g in Move.read_group(
                [
                    ("project_id", "in", projects.ids),
                    ("state", "=", "posted"),
                    ("move_type", "in", ("in_invoice", "in_refund")),
                ],
                ["amount_untaxed:sum"],
                ["project_id", "move_type"],
                lazy=False,
            ):
                pid = g["project_id"][0]
                amt = g["amount_untaxed"] or 0.0
                cost_by_project[pid] = cost_by_project.get(pid, 0.0) + (
                    amt if g["move_type"] == "in_invoice" else -amt
                )
        for order in self:
            invoiced = order.certification_ids.filtered(
                lambda c: c.state == "invoiced"
            ).sorted("number")
            certified = invoiced[-1].amount_total_origin if invoiced else 0.0
            cost = cost_by_project.get(order.project_id.id, 0.0) if order.project_id else 0.0
            order.amount_certified_origin = certified
            order.amount_job_cost = cost
            order.amount_job_margin = certified - cost

    @api.depends("project_id")
    def _compute_job_po(self):
        POL = self.env["purchase.order.line"]
        projects = self.mapped("project_id")
        by_proj = {pid: 0.0 for pid in projects.ids}
        if projects:
            lines = POL.search(
                [
                    ("order_id.project_id", "in", projects.ids),
                    ("order_id.state", "in", ("purchase", "done")),
                    ("display_type", "=", False),
                ]
            )
            for line in lines:
                pid = line.order_id.project_id.id
                by_proj[pid] = by_proj.get(pid, 0.0) + (
                    line.qty_to_invoice * line.price_unit
                )
        for order in self:
            order.amount_job_po = (
                by_proj.get(order.project_id.id, 0.0) if order.project_id else 0.0
            )

    def _ensure_project(self):
        for order in self:
            if order.project_id:
                continue
            name = (
                f"{order.name} — {order.partner_id.name}"
                if order.partner_id
                else order.name
            )
            order.project_id = self.env["project.project"].create(
                {
                    "name": name,
                    "partner_id": order.partner_id.id,
                    "company_id": order.company_id.id,
                }
            )
        return self.project_id

    def _check_unique_confirmed_project(self, treating_as_confirmed=False):
        # ponytail: no SQL unique; duplicados ya en BD se quedan
        for order in self:
            if not order.project_id:
                continue
            if not treating_as_confirmed and order.state not in ("sale", "done"):
                continue
            other = self.search(
                [
                    ("id", "!=", order.id),
                    ("project_id", "=", order.project_id.id),
                    ("state", "in", ("sale", "done")),
                ],
                limit=1,
            )
            if other:
                raise UserError(
                    _("Ya hay un pedido confirmado para esta obra (%s).") % other.name
                )

    def write(self, vals):
        res = super().write(vals)
        if "project_id" in vals:
            self._check_unique_confirmed_project()
        return res

    def action_confirm(self):
        self._check_unique_confirmed_project(treating_as_confirmed=True)
        res = super().action_confirm()
        self.filtered("bc3")._ensure_project()
        self._check_unique_confirmed_project()
        return res

    def action_view_certifications(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "incoespacio_construction_certification.action_construction_certification"
        )
        action["domain"] = [("order_id", "=", self.id)]
        action["context"] = {
            "default_order_id": self.id,
            "default_partner_id": self.partner_id.id,
            "default_project_id": self.project_id.id if self.project_id else False,
        }
        return action

    def action_create_certification(self):
        self.ensure_one()
        self._ensure_project()
        existing_certs = self.certification_ids.filtered(lambda c: c.state != "cancel")
        next_number = max([c.number for c in existing_certs], default=0) + 1

        prev_cert = existing_certs.sorted(key=lambda c: c.number, reverse=True)[:1]
        prev_qty_map = {}
        if prev_cert:
            for pline in prev_cert.line_ids:
                if pline.sale_order_line_id:
                    prev_qty_map[pline.sale_order_line_id.id] = pline.qty_origin

        cert_lines = []
        for line in self.order_line:
            if line.display_type:
                cert_lines.append(
                    (
                        0,
                        0,
                        {
                            "display_type": line.display_type,
                            "sequence": line.sequence,
                            "name": line.name,
                            "bc3_level": line.bc3_level,
                        },
                    )
                )
            else:
                prev_qty = prev_qty_map.get(line.id, 0.0)
                code_val = getattr(line, "bc3_code", False)
                name = line.name
                if line.is_modification:
                    code_val = code_val or "MOD"
                    if line.modification_ref:
                        name = f"[{line.modification_ref}] {line.name}"
                cert_lines.append(
                    (
                        0,
                        0,
                        {
                            "sale_order_line_id": line.id,
                            "sequence": line.sequence,
                            "bc3_level": line.bc3_level,
                            "code": code_val,
                            "name": name,
                            "is_modification": line.is_modification,
                            "product_uom_id": line.product_uom.id
                            if line.product_uom
                            else False,
                            "price_unit": line.price_unit,
                            "qty_budget": line.product_uom_qty,
                            "qty_previous": prev_qty,
                            "qty_origin": prev_qty,
                            "tax_ids": [(6, 0, line.tax_id.ids)],
                        },
                    )
                )

        certification = self.env["construction.certification"].create(
            {
                "order_id": self.id,
                "number": next_number,
                "date": fields.Date.context_today(self),
                "line_ids": cert_lines,
            }
        )

        return {
            "name": _("Certificación de Obra"),
            "type": "ir.actions.act_window",
            "res_model": "construction.certification",
            "view_mode": "form",
            "res_id": certification.id,
        }

    def action_return_retention(self):
        self.ensure_one()
        if self.certification_ids.filtered(lambda c: c.state in ("draft", "confirmed")):
            raise UserError(
                _(
                    "Solo se puede devolver la retención cuando todas las "
                    "certificaciones están facturadas o canceladas."
                )
            )
        if self.amount_retention_to_return <= 0:
            raise UserError(_("No hay retención pendiente de devolver."))
        account = self.env["construction.certification"]._get_or_create_retention_account(
            self.company_id
        )
        line_vals = {
            "name": _("Devolución retención de garantía - %s") % self.name,
            "quantity": 1,
            "price_unit": self.amount_retention_to_return,
            "account_id": account.id,
            "tax_ids": [(6, 0, [])],
        }
        analytic = self.project_id and getattr(self.project_id, "account_id", False)
        if analytic:
            line_vals["analytic_distribution"] = {str(analytic.id): 100}
        move = (
            self.env["account.move"]
            .with_context(default_move_type="out_invoice")
            .create(
                {
                    "move_type": "out_invoice",
                    "partner_id": self.partner_id.id,
                    "invoice_date": fields.Date.context_today(self),
                    "ref": _("Devolución retención - %s") % self.name,
                    "invoice_origin": self.name,
                    "company_id": self.company_id.id,
                    "currency_id": self.currency_id.id,
                    "retention_order_id": self.id,
                    "invoice_line_ids": [(0, 0, line_vals)],
                }
            )
        )
        self.retention_return_invoice_id = move.id
        return {
            "name": _("Factura devolución retención"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": move.id,
        }

    def action_view_retention_return(self):
        self.ensure_one()
        invoices = self.retention_return_invoice_ids or self.retention_return_invoice_id
        return {
            "name": _("Devolución retención"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "form" if len(invoices) == 1 else "tree,form",
            "res_id": invoices.id if len(invoices) == 1 else False,
            "domain": [("id", "in", invoices.ids)],
        }

    def action_add_modification(self):
        self.ensure_one()
        product = self.order_line.filtered(
            lambda l: l.product_id and not l.display_type
        ).product_id[:1]
        if not product:
            raise UserError(_("Añada al menos una partida antes de un modificado."))
        today = fields.Date.context_today(self)
        n = len(self.order_line.filtered("is_modification")) + 1
        self.order_line.create(
            {
                "order_id": self.id,
                "product_id": product.id,
                "name": _("Modificado"),
                "product_uom_qty": 1,
                "price_unit": 0,
                "is_modification": True,
                "modification_ref": _("Mod. %s — %s") % (n, today),
            }
        )
        return True


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    is_modification = fields.Boolean(string="Modificado")
    modification_ref = fields.Char(string="Ref. modificado")


class ProjectProject(models.Model):
    _inherit = "project.project"

    def get_formview_action(self, access_uid=None):
        self.ensure_one()
        if self.env.context.get("open_construction_order"):
            order = self.env["sale.order"].search(
                [("project_id", "=", self.id), ("state", "in", ("sale", "done"))],
                limit=1,
            )
            if order:
                return {
                    "type": "ir.actions.act_window",
                    "res_model": "sale.order",
                    "res_id": order.id,
                    "view_mode": "form",
                    "views": [(False, "form")],
                    "target": "current",
                }
        return super().get_formview_action(access_uid=access_uid)
