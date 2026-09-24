from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    ocr_pending_review = fields.Boolean(
        string="Contacto OCR pendiente de revisar",
        copy=False,
    )
