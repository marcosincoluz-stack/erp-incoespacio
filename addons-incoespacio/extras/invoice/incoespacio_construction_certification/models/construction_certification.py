from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import config


class ConstructionCertification(models.Model):
    _name = "construction.certification"
    _description = "Certificación de Obra a Origen"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(
        string="Referencia",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("Nuevo"),
    )
    number = fields.Integer(
        string="Nº Certificación",
        required=True,
        default=1,
        copy=False,
        tracking=True,
        help="Número correlativo de certificación para esta obra",
    )
    order_id = fields.Many2one(
        "sale.order",
        string="Presupuesto / Obra",
        required=True,
        ondelete="cascade",
        tracking=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Cliente",
        related="order_id.partner_id",
        store=True,
        readonly=True,
    )
    project_id = fields.Many2one(
        "project.project",
        string="Proyecto / Obra",
        related="order_id.project_id",
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        related="order_id.company_id",
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Moneda",
        related="order_id.currency_id",
        store=True,
        readonly=True,
    )
    date = fields.Date(
        string="Fecha Certificación",
        default=fields.Date.context_today,
        required=True,
        tracking=True,
    )
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("confirmed", "Aprobada"),
            ("invoiced", "Facturada"),
            ("cancel", "Cancelada"),
        ],
        string="Estado",
        default="draft",
        required=True,
        tracking=True,
        copy=False,
    )
    retention_rate = fields.Float(
        string="% Retención Garantía",
        default=0.0,
        tracking=True,
        help="Porcentaje de retención en concepto de garantía de buena ejecución. 0 = sin retención.",
    )
    line_ids = fields.One2many(
        "construction.certification.line",
        "certification_id",
        string="Líneas de Certificación",
        copy=True,
    )
    invoice_id = fields.Many2one(
        "account.move",
        string="Factura Emitida",
        readonly=True,
        copy=False,
        tracking=True,
    )
    notes = fields.Html(string="Observaciones")
    lines_editable = fields.Boolean(
        string="Editar partidas",
        default=False,
        help="Desbloquea código, precio, medición de presupuesto y el resto de campos de partida.",
    )

    amount_total_budget = fields.Monetary(
        string="Total Presupuestado",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )
    amount_previous_origin = fields.Monetary(
        string="Anteriormente Certificado",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )
    amount_total_origin = fields.Monetary(
        string="Total Ejecutado a Origen",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )
    amount_period_untaxed = fields.Monetary(
        string="Base Imponible del Periodo",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )
    amount_retention = fields.Monetary(
        string="Retención de Garantía",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )
    amount_net_period = fields.Monetary(
        string="Líquido Periodo antes de IVA",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )
    amount_period_tax = fields.Monetary(
        string="IVA del Periodo",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )
    amount_period_total = fields.Monetary(
        string="Total a Percibir (Líquido + IVA)",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )
    progress_origin = fields.Float(
        string="% Ejecutado a Origen",
        compute="_compute_amounts",
        store=True,
    )

    @api.depends(
        "line_ids.amount_budget",
        "line_ids.amount_previous",
        "line_ids.amount_origin",
        "line_ids.amount_period",
        "line_ids.tax_ids",
        "retention_rate",
    )
    def _compute_amounts(self):
        for cert in self:
            content_lines = cert.line_ids.filtered(lambda l: not l.display_type)
            total_budget = sum(content_lines.mapped("amount_budget"))
            total_previous = sum(content_lines.mapped("amount_previous"))
            total_origin = sum(content_lines.mapped("amount_origin"))
            period_untaxed = sum(content_lines.mapped("amount_period"))

            retention = period_untaxed * (cert.retention_rate / 100.0)
            net_period = period_untaxed - retention

            period_tax = 0.0
            for line in content_lines:
                if line.tax_ids and line.amount_period:
                    taxes_res = line.tax_ids.compute_all(
                        line.amount_period,
                        currency=cert.currency_id,
                        quantity=1.0,
                        partner=cert.partner_id,
                    )
                    period_tax += sum(t["amount"] for t in taxes_res.get("taxes", []))

            cert.amount_total_budget = total_budget
            cert.amount_previous_origin = total_previous
            cert.amount_total_origin = total_origin
            cert.amount_period_untaxed = period_untaxed
            cert.amount_retention = retention
            cert.amount_net_period = net_period
            cert.amount_period_tax = period_tax
            cert.amount_period_total = net_period + period_tax
            cert.progress_origin = (
                (total_origin / total_budget * 100.0) if total_budget else 0.0
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("Nuevo")) == _("Nuevo"):
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code(
                        "construction.certification"
                    )
                    or _("Nuevo")
                )
        return super().create(vals_list)

    def action_confirm(self):
        self.ensure_one()
        if not self.line_ids.filtered(lambda l: not l.display_type):
            raise UserError(_("La certificación debe tener al menos una partida de obra."))
        self.write({"state": "confirmed"})

    def action_confirm_and_invoice(self):
        self.ensure_one()
        if self.state == "draft":
            self.action_confirm()
            # ponytail: un RPC; sin commit el UserError de la factura deshace el aprobar
            if not config["test_enable"]:
                self.env.cr.commit()
        return self.action_create_invoice()

    def action_draft(self):
        self.write({"state": "draft"})

    def action_cancel(self):
        if any(c.invoice_id and c.invoice_id.state != "cancel" for c in self):
            raise UserError(_("No puede cancelar una certificación cuya factura no haya sido cancelada."))
        self.write({"state": "cancel"})

    def _get_or_create_retention_account(self, company):
        Account = self.env["account.account"]
        account = Account.search(
            [("code", "=like", "4308%"), ("company_id", "=", company.id)],
            limit=1,
        )
        if not account:
            account = Account.create({
                "code": "430800",
                "name": "Clientes, retenciones por garantía de obra",
                "account_type": "asset_current",
                "company_id": company.id,
            })
        elif account.account_type != "asset_current":
            account.write({"account_type": "asset_current"})
        return account

    def action_create_invoice(self):
        self.ensure_one()
        if self.invoice_id:
            raise UserError(_("Esta certificación ya tiene una factura asignada: %s") % self.invoice_id.name)
        if self.state != "confirmed":
            raise UserError(_("Solo se pueden facturar certificaciones en estado 'Aprobada'."))

        valid_lines = self.line_ids.filtered(
            lambda l: not l.display_type and l.qty_period > 0
        )
        if not valid_lines:
            raise UserError(_("No hay partidas con medición ejecutada en este periodo para facturar."))

        invoice_lines = []
        for line in valid_lines:
            prod_id = (
                line.sale_order_line_id.product_id.id
                if line.sale_order_line_id and line.sale_order_line_id.product_id
                else False
            )
            line_vals = {
                "name": f"[{line.code or ''}] {line.name} (Cert. {self.number}: {line.qty_period:.2f} {line.product_uom_id.name or ''})",
                "quantity": line.qty_period,
                "price_unit": line.price_unit,
                "tax_ids": [(6, 0, line.tax_ids.ids)],
                "product_uom_id": line.product_uom_id.id if line.product_uom_id else False,
            }
            if prod_id:
                line_vals["product_id"] = prod_id
            if line.sale_order_line_id:
                line_vals["sale_line_ids"] = [(4, line.sale_order_line_id.id)]
            analytic = self.project_id and getattr(self.project_id, "account_id", False)
            if analytic:
                line_vals["analytic_distribution"] = {str(analytic.id): 100}
            invoice_lines.append((0, 0, line_vals))

        if self.amount_retention > 0:
            retention_acc = self._get_or_create_retention_account(self.company_id)
            ret_vals = {
                "name": f"Retención de garantía ({self.retention_rate}%) s/ base {self.amount_period_untaxed:.2f} €",
                "quantity": 1,
                "price_unit": -self.amount_retention,
                "account_id": retention_acc.id,
                "tax_ids": False,
            }
            analytic = self.project_id and getattr(self.project_id, "account_id", False)
            if analytic:
                ret_vals["analytic_distribution"] = {str(analytic.id): 100}
            invoice_lines.append((0, 0, ret_vals))

        move = self.env["account.move"].with_context(default_move_type="out_invoice").create({
            "move_type": "out_invoice",
            "partner_id": self.partner_id.id,
            "invoice_date": self.date,
            "ref": f"Certificación Nº {self.number} - {self.order_id.name}",
            "invoice_origin": f"{self.name} ({self.order_id.name})",
            "project_id": self.project_id.id if self.project_id else False,
            "company_id": self.company_id.id,
            "currency_id": self.currency_id.id,
            "invoice_line_ids": invoice_lines,
        })

        self.write({
            "invoice_id": move.id,
            "state": "invoiced",
        })

        return {
            "name": _("Factura de Certificación"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": move.id,
        }

    def action_view_invoice(self):
        self.ensure_one()
        return {
            "name": _("Factura"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.invoice_id.id,
        }

    def action_print_certification(self):
        self.ensure_one()
        return self.env.ref(
            "incoespacio_construction_certification.action_report_construction_certification"
        ).report_action(self)

    def action_toggle_lines_editable(self):
        self.ensure_one()
        self.lines_editable = not self.lines_editable

    def _get_report_lines(self):
        """PDF: partidas con medición a origen y sus capítulos; el resto del presupuesto no se imprime."""
        self.ensure_one()
        keep = []
        section = None
        notes = []
        for line in self.line_ids:
            if line.display_type == "line_section":
                section = line
                notes = []
            elif line.display_type == "line_note":
                notes.append(line)
            elif line.qty_origin:
                if section:
                    keep.append(section)
                    section = None
                keep.extend(notes)
                notes = []
                keep.append(line)
        return self.line_ids.browse([line.id for line in keep])


class ConstructionCertificationLine(models.Model):
    _name = "construction.certification.line"
    _description = "Línea de Certificación de Obra"
    _order = "sequence, id"

    certification_id = fields.Many2one(
        "construction.certification",
        string="Certificación",
        required=True,
        ondelete="cascade",
    )
    sale_order_line_id = fields.Many2one(
        "sale.order.line",
        string="Línea de Presupuesto",
        ondelete="set null",
    )
    sequence = fields.Integer(string="Secuencia", default=10)
    display_type = fields.Selection(
        [
            ("line_section", "Capítulo / Sección"),
            ("line_note", "Nota"),
        ],
        string="Tipo de Línea",
        default=False,
    )
    code = fields.Char(string="Código")
    name = fields.Text(string="Concepto / Partida", required=True)
    is_modification = fields.Boolean(string="Modificado")
    product_uom_id = fields.Many2one("uom.uom", string="Ud.")
    price_unit = fields.Float(string="Precio Unit.", digits="Product Price")
    qty_budget = fields.Float(string="Med. Presupuesto", digits="Product Unit of Measure")
    qty_previous = fields.Float(string="Med. Anterior", digits="Product Unit of Measure", default=0.0)
    qty_origin = fields.Float(string="Med. a Origen", digits="Product Unit of Measure", default=0.0)
    qty_period = fields.Float(
        string="Med. Periodo",
        digits="Product Unit of Measure",
        compute="_compute_qty_period",
        inverse="_inverse_qty_period",
        store=True,
    )
    percentage_origin = fields.Float(
        string="% Origen",
        compute="_compute_amounts",
        store=True,
    )
    amount_budget = fields.Monetary(
        string="Imp. Presupuesto",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )
    amount_previous = fields.Monetary(
        string="Imp. Anterior",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )
    amount_origin = fields.Monetary(
        string="Imp. a Origen",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )
    amount_period = fields.Monetary(
        string="Imp. Periodo",
        compute="_compute_amounts",
        store=True,
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="certification_id.currency_id",
        store=True,
        readonly=True,
    )
    tax_ids = fields.Many2many("account.tax", string="Impuestos")

    def _get_report_name(self):
        """PDF: código ya va en su columna; aquí el resumen, no el pliego."""
        self.ensure_one()
        text = (self.name or "").strip()
        if self.code:
            prefix = "[%s]" % self.code
            if text.startswith(prefix):
                text = text[len(prefix) :].strip()
        text = text.splitlines()[0] if text else ""
        # ponytail: 110 chars, texto completo si piden el pliego en el PDF
        if len(text) > 110:
            text = text[:107].rsplit(" ", 1)[0] + "..."
        return text

    @api.depends("qty_origin", "qty_previous")
    def _compute_qty_period(self):
        for line in self:
            line.qty_period = line.qty_origin - line.qty_previous

    def _inverse_qty_period(self):
        for line in self:
            line.qty_origin = line.qty_previous + line.qty_period

    @api.depends("qty_budget", "qty_previous", "qty_origin", "qty_period", "price_unit")
    def _compute_amounts(self):
        for line in self:
            if line.display_type:
                line.percentage_origin = 0.0
                line.amount_budget = 0.0
                line.amount_previous = 0.0
                line.amount_origin = 0.0
                line.amount_period = 0.0
            else:
                line.percentage_origin = (
                    (line.qty_origin / line.qty_budget * 100.0) if line.qty_budget else 0.0
                )
                line.amount_budget = line.qty_budget * line.price_unit
                line.amount_previous = line.qty_previous * line.price_unit
                line.amount_origin = line.qty_origin * line.price_unit
                line.amount_period = line.qty_period * line.price_unit
