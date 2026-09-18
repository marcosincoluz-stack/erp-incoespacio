from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare


class OcrObraSplitWizard(models.TransientModel):
    _name = "ocr.obra.split.wizard"
    _description = "Repartir línea de factura entre partidas"

    line_id = fields.Many2one("account.move.line", required=True, ondelete="cascade")
    currency_id = fields.Many2one(related="line_id.currency_id")
    amount_total = fields.Monetary(related="line_id.price_subtotal", currency_field="currency_id")
    amount_remaining = fields.Monetary(
        string="Queda por repartir",
        compute="_compute_amount_remaining",
        currency_field="currency_id",
    )
    split_line_ids = fields.One2many(
        "ocr.obra.split.wizard.line",
        "wizard_id",
        string="Partidas",
    )

    @api.depends("amount_total", "split_line_ids.amount")
    def _compute_amount_remaining(self):
        for wiz in self:
            wiz.amount_remaining = (wiz.amount_total or 0.0) - sum(
                wiz.split_line_ids.mapped("amount")
            )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        line = self.env["account.move.line"].browse(
            res.get("line_id") or self.env.context.get("default_line_id")
        )
        if line and "split_line_ids" in fields_list:
            res["split_line_ids"] = [
                (
                    0,
                    0,
                    {
                        "construction_line_id": line.construction_line_id.id,
                        "amount": 0.0,
                    },
                )
            ]
        return res

    @api.onchange("split_line_ids")
    def _onchange_fill_remaining(self):
        empty = self.split_line_ids.filtered(lambda l: not l.amount)
        filled = self.split_line_ids - empty
        if len(empty) != 1 or not filled:
            return
        empty.amount = (self.amount_total or 0.0) - sum(filled.mapped("amount"))

    def action_apply(self):
        self.ensure_one()
        aml = self.line_id
        if aml.move_id.state != "draft":
            raise UserError(_("Solo se puede repartir en borrador."))
        splits = self.split_line_ids.filtered(lambda s: s.amount)
        if len(splits) < 2:
            raise UserError(_("Indica al menos dos partidas."))
        if any(not s.construction_line_id for s in splits):
            raise UserError(_("Cada importe necesita una partida."))
        rounding = aml.currency_id.rounding or 0.01
        if float_compare(sum(splits.mapped("amount")), aml.price_subtotal, precision_rounding=rounding) != 0:
            raise UserError(
                _("Los importes deben sumar %s.") % aml.price_subtotal
            )
        first, *rest = splits
        self._apply_amount(aml, first.amount, first.construction_line_id)
        for split in rest:
            copy = aml.copy(
                {
                    "construction_line_id": split.construction_line_id.id,
                }
            )
            self._apply_amount(copy, split.amount, split.construction_line_id)
        return {"type": "ir.actions.act_window_close"}

    def _apply_amount(self, aml, amount, partida):
        vals = {"construction_line_id": partida.id}
        if aml.price_unit:
            vals["quantity"] = amount / aml.price_unit
        else:
            vals["quantity"] = 1.0
            vals["price_unit"] = amount
        aml.write(vals)


class OcrObraSplitWizardLine(models.TransientModel):
    _name = "ocr.obra.split.wizard.line"
    _description = "Línea de reparto a partida"

    wizard_id = fields.Many2one("ocr.obra.split.wizard", required=True, ondelete="cascade")
    project_id = fields.Many2one(related="wizard_id.line_id.move_id.project_id")
    construction_line_id = fields.Many2one(
        "sale.order.line",
        string="Partida",
        required=True,
        domain="[('display_type', '=', False), ('order_id.project_id', '=', project_id)]",
    )
    currency_id = fields.Many2one(related="wizard_id.currency_id")
    amount = fields.Monetary(string="Importe", currency_field="currency_id", required=True)
