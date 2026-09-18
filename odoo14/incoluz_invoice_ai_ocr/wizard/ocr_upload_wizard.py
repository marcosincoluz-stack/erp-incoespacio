# -*- coding: utf-8 -*-
from odoo import fields, models


class OcrUploadWizard(models.TransientModel):
    _name = 'incoluz.ocr.upload.wizard'
    _description = 'Deprecated: the JS dialog calls account.move.upload_bills_batch'

    move_type = fields.Selection([
        ('in_invoice', 'Factura de proveedor'),
        ('out_invoice', 'Factura de cliente'),
        ('in_refund', 'Abono de proveedor'),
        ('out_refund', 'Abono de cliente'),
    ], default='in_invoice')


class OcrUploadWizardLine(models.TransientModel):
    _name = 'incoluz.ocr.upload.wizard.line'
    _description = 'Deprecated wizard line'

    wizard_id = fields.Many2one('incoluz.ocr.upload.wizard', ondelete='cascade')
