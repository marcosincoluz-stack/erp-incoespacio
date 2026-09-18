from odoo import models, _
from odoo.exceptions import UserError


class OcrObraSplitWizard(models.TransientModel):
    _inherit = "ocr.obra.split.wizard"

    def action_apply(self):
        self.ensure_one()
        move = self.line_id.move_id
        posted = move.state == "posted"
        if posted:
            move._check_fiscalyear_lock_date()
            if move.payment_state not in ("not_paid", "partial"):
                raise UserError(_("No se puede repartir una factura pagada."))
            move.button_draft()
        res = super().action_apply()
        if posted:
            move.action_post()
        return res
