# -*- coding: utf-8 -*-
import logging
from odoo import api, models, _

_logger = logging.getLogger(__name__)


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    def create_document_from_attachment(self, attachment_ids):
        """Sobrescribe la redirección tras subir archivos para no forzar la vista formulario
        cuando la IA está activa, manteniendo al usuario en la vista de lista con el
        cajón flotante estilo Drive abajo a la derecha y permitiendo añadir más facturas.
        """
        action_vals = super().create_document_from_attachment(attachment_ids)
        icp = self.env['ir.config_parameter'].sudo()
        api_key = icp.get_param('incoespacio_invoice_ocr.gemini_api_key', default='').strip()
        if api_key and action_vals and action_vals.get('res_model') == 'account.move':
            action_vals.update({
                'views': [[False, "list"], [False, "kanban"], [False, "form"]],
                'view_mode': 'list, kanban, form',
            })
            action_vals.pop('res_id', None)
        return action_vals

    def _create_document_from_attachment(self, attachment_ids):
        """Sobrescribe la creación de documentos desde archivos adjuntos para que,
        cuando se use el botón 'Subir' con la IA activa, cree los borradores al instante
        y delegue la extracción al hilo en segundo plano del servidor (inmune a cierres de sesión).
        """
        icp = self.env['ir.config_parameter'].sudo()
        api_key = icp.get_param('incoespacio_invoice_ocr.gemini_api_key', default='').strip()
        move_type = self._context.get("default_move_type", "entry")

        # Si no hay API key o no es factura contable, usar el comportamiento estándar de Odoo
        allowed_types = ('in_invoice', 'in_receipt', 'in_refund', 'out_invoice', 'out_refund', 'out_receipt')
        if not api_key or move_type not in allowed_types:
            return super()._create_document_from_attachment(attachment_ids)

        if not self:
            self = self.env['account.journal'].browse(self._context.get("default_journal_id"))
        if not self:
            journal_type = "purchase" if move_type in self.env['account.move'].get_purchase_types(include_receipts=True) else "sale"
            self = self.env['account.journal'].search([
                *self.env['account.journal']._check_company_domain(self.env.company),
                ('type', '=', journal_type),
            ], limit=1)

        attachments = self.env['ir.attachment'].browse(attachment_ids)
        if not attachments:
            return super()._create_document_from_attachment(attachment_ids)

        all_invoices = self.env['account.move']
        for attachment in attachments:
            invoice = self.env['account.move'].create({
                'journal_id': self.id,
                'move_type': move_type,
                'ocr_status': 'pending',
            })
            attachment.write({'res_model': 'account.move', 'res_id': invoice.id})
            invoice.with_context(
                account_predictive_bills_disable_prediction=True,
                no_new_invoice=True,
            ).message_post(attachment_ids=attachment.ids)
            all_invoices |= invoice

        if all_invoices:
            _logger.info("Subida de %d facturas recibida en diario %s. Encolando para OCR en segundo plano...", len(all_invoices), self.name)
            self.env['account.move']._trigger_background_ocr_worker(all_invoices.ids)

        return all_invoices
