from odoo import api, fields, models, _
from odoo.exceptions import UserError


class OcrObraAssignWizard(models.TransientModel):
    _name = "ocr.obra.assign.wizard"
    _description = "Imputar líneas de factura a partidas"

    move_id = fields.Many2one("account.move", required=True, ondelete="cascade")
    project_id = fields.Many2one(related="move_id.project_id")
    line_ids = fields.One2many(
        "ocr.obra.assign.wizard.line",
        "wizard_id",
        string="Líneas",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        move = self.env["account.move"].browse(
            res.get("move_id") or self.env.context.get("default_move_id")
        )
        if move and "line_ids" in fields_list:
            res["line_ids"] = [
                (0, 0, {"move_line_id": line.id})
                for line in move.invoice_line_ids.filtered(
                    lambda l: l.display_type == "product" and not l.construction_line_id
                )
            ]
        return res

    def action_apply(self):
        self.ensure_one()
        chosen = self.line_ids.filtered("construction_line_id")
        if not chosen:
            raise UserError(_("Elige al menos una partida."))
        for line in chosen:
            # ponytail: solo imputación; si el core bloquea posted, skip_invoice_sync
            line.move_line_id.with_context(
                check_move_validity=False,
                skip_invoice_sync=True,
            ).write({"construction_line_id": line.construction_line_id.id})
        return {"type": "ir.actions.act_window_close"}


class OcrObraAssignWizardLine(models.TransientModel):
    _name = "ocr.obra.assign.wizard.line"
    _description = "Línea a imputar a partida"

    wizard_id = fields.Many2one(
        "ocr.obra.assign.wizard", required=True, ondelete="cascade"
    )
    move_line_id = fields.Many2one("account.move.line", required=True, ondelete="cascade")
    name = fields.Char(related="move_line_id.name")
    project_id = fields.Many2one(related="wizard_id.project_id")
    construction_section_id = fields.Many2one(related="move_line_id.construction_section_id")
    construction_line_id = fields.Many2one(
        "sale.order.line",
        string="Partida",
        domain="[('display_type', '=', False), ('order_id.project_id', '=', project_id), ('bc3_section_id', '=?', construction_section_id)]",
    )
    currency_id = fields.Many2one(related="move_line_id.currency_id")
    amount = fields.Monetary(related="move_line_id.price_subtotal", currency_field="currency_id")
