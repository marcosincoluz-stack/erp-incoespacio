# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    ocr_has_pdf = fields.Boolean(compute='_compute_ocr_pdf_file', string="Tiene PDF")
    ocr_pdf_file = fields.Binary(compute='_compute_ocr_pdf_file', string="Archivo PDF Factura")
    ocr_show_split_view = fields.Boolean(
        string="Modo Pantalla Dividida",
        default=False,
        help="Muestra el PDF original de la factura al lado del formulario."
    )

    @api.depends('attachment_ids')
    def _compute_ocr_pdf_file(self):
        for move in self:
            pdf_attach = move.attachment_ids.filtered(
                lambda a: a.mimetype == 'application/pdf' or (a.name and a.name.lower().endswith('.pdf'))
            )
            if pdf_attach:
                move.ocr_has_pdf = True
                move.ocr_pdf_file = pdf_attach[0].datas
            else:
                move.ocr_has_pdf = False
                move.ocr_pdf_file = False

    def action_toggle_split_view(self):
        self.ensure_one()
        self.ocr_show_split_view = not self.ocr_show_split_view
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
