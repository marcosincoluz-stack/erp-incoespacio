# -*- coding: utf-8 -*-
import base64

from odoo import api, fields, models, _
from odoo.exceptions import UserError

MAX_FILE_SIZE = 25 * 1024 * 1024


class OcrUploadWizard(models.TransientModel):
    _name = 'incoluz.ocr.upload.wizard'
    _description = 'Subida de facturas para digitalización con IA'

    line_ids = fields.One2many('incoluz.ocr.upload.wizard.line', 'wizard_id', string="Archivos")
    move_type = fields.Selection([
        ('in_invoice', 'Factura de proveedor'),
        ('in_receipt', 'Recibo de proveedor'),
        ('in_refund', 'Abono de proveedor'),
        ('out_invoice', 'Factura de cliente'),
        ('out_refund', 'Abono de cliente'),
    ], string="Tipo de documento", default='in_invoice', required=True)

    def action_add_line(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'incoluz.ocr.upload.wizard.line',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_wizard_id': self.id},
        }

    def action_process(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Añade al menos un archivo PDF o imagen antes de procesar."))
        files = []
        for line in self.line_ids:
            if not line.file_data:
                continue
            if line.file_size > MAX_FILE_SIZE:
                raise UserError(_("El archivo %s supera el límite de 25 MB.") % line.file_name)
            files.append({
                'name': line.file_name or 'factura.pdf',
                'data': line.file_data,
                'mimetype': line.file_mimetype or 'application/pdf',
            })
        if not files:
            raise UserError(_("Añade al menos un archivo PDF o imagen antes de procesar."))
        created = self.env['account.move'].with_context(default_move_type=self.move_type).upload_bills_batch(files)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("OCR IA"),
                'message': _("Se han enviado %s factura(s) a la cola de digitalización con IA.") % len(created),
                'type': 'success',
                'next': {'type': 'ir.actions.act_window', 'res_model': 'account.move', 'view_mode': 'tree,form',
                         'domain': [('id', 'in', [c['id'] for c in created])]},
            },
        }


class OcrUploadWizardLine(models.TransientModel):
    _name = 'incoluz.ocr.upload.wizard.line'
    _description = 'Archivo del asistente de digitalización'

    wizard_id = fields.Many2one('incoluz.ocr.upload.wizard', required=True, ondelete='cascade')
    file_data = fields.Binary(string="Archivo", attachment=True)
    file_name = fields.Char(string="Nombre")
    file_mimetype = fields.Char(string="MIME")
    file_size = fields.Integer(string="Tamaño (bytes)")

    @api.onchange('file_data')
    def _onchange_file_data(self):
        if self.file_data:
            raw = base64.b64decode(self.file_data)
            self.file_size = len(raw)
            if raw.startswith(b'%PDF-'):
                self.file_mimetype = 'application/pdf'
            elif raw.startswith(b'\xff\xd8'):
                self.file_mimetype = 'image/jpeg'
            elif raw.startswith(b'\x89PNG'):
                self.file_mimetype = 'image/png'
            else:
                self.file_mimetype = 'application/pdf'
