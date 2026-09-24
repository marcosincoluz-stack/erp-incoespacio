# -*- coding: utf-8 -*-
import datetime
import logging
import threading
from odoo import api, fields, models
import odoo

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def _create_move_with_attachment(self, attachment, move_type, journal_id, ctx=None):
        move = self.with_context(ctx or {}).create({
            'move_type': move_type,
            'ocr_status': 'pending',
            'journal_id': journal_id,
        })
        attachment.write({'res_model': 'account.move', 'res_id': move.id})
        move.with_context(
            account_predictive_bills_disable_prediction=True,
            no_new_invoice=True,
        ).message_post(attachment_ids=attachment.ids)
        return move

    @api.model
    def upload_bills_batch(self, files, context_vals=None):
        if not files:
            return []

        ctx = dict(self._context)
        if context_vals:
            ctx.update(context_vals)

        move_type = ctx.get('default_move_type') or 'in_invoice'
        journal_id = ctx.get('default_journal_id')

        if not journal_id:
            journal_type = 'purchase' if move_type in self.get_purchase_types(include_receipts=True) else 'sale'
            journal = self.env['account.journal'].search([
                *self.env['account.journal']._check_company_domain(self.env.company),
                ('type', '=', journal_type),
            ], limit=1)
            journal_id = journal.id if journal else False

        created_moves = []
        move_ids_to_process = []

        for f in files:
            filename = f.get('name') or 'factura.pdf'
            attachment = self.env['ir.attachment'].create({
                'name': filename,
                'datas': f.get('data') or '',
                'mimetype': f.get('mimetype') or 'application/pdf',
            })
            move = self._create_move_with_attachment(attachment, move_type, journal_id, ctx)
            created_moves.append({
                'id': move.id,
                'filename': filename,
                'status': 'pending',
            })
            move_ids_to_process.append(move.id)

        if move_ids_to_process:
            self._trigger_background_ocr_worker(move_ids_to_process)

        return created_moves

    @api.model
    def get_active_ocr_batch(self, move_ids=None):
        # Si se solicitan IDs específicos, consultarlos directamente
        if move_ids:
            domain = [('id', 'in', move_ids)]
        else:
            # Comportamiento tipo Google Drive:
            # En recarga (F5) o consulta general, retornar tareas activas Y
            # también las terminadas hace poco (últimos 30 min) del usuario actual,
            # para que el drawer sobreviva a recargas hasta que el usuario lo cierre con la X.
            limit_time = fields.Datetime.now() - datetime.timedelta(minutes=30)
            domain = [
                ('ocr_status', 'in', ('pending', 'processing', 'done', 'error', 'mismatch')),
                ('create_uid', '=', self.env.uid),
                ('create_date', '>=', limit_time),
            ]

        moves = self.search(domain, order='id desc', limit=50)
        result = []
        for m in moves:
            fname = 'Factura'
            if m.attachment_ids:
                fname = m.attachment_ids[0].name or 'Factura'
            result.append({
                'id': m.id,
                'name': m.name or f"Borrador #{m.id}",
                'filename': fname,
                'status': 'failed' if m.ocr_status == 'error' else m.ocr_status,
                'error': m.ocr_error_message or '',
                'mismatch': getattr(m, 'ocr_company_mismatch', False),
                'mismatch_details': getattr(m, 'ocr_mismatch_details', '') or '',
                'partner': m.partner_id.name if m.partner_id else '',
                'ref': m.ref or '',
                'amount_total': m.amount_total,
                'is_duplicate': m.is_duplicate_detected,
            })
        return result

    @api.model
    def _trigger_background_ocr_worker(self, move_ids):
        if not move_ids:
            return
        db_name = self.env.cr.dbname
        user_id = self.env.uid

        def _start_worker_thread():
            thread = threading.Thread(
                target=self._run_background_ocr,
                args=(db_name, user_id, list(move_ids)),
                daemon=True,
                name=f"ocr_worker_{db_name}"
            )
            thread.start()
            _logger.info("Worker OCR lanzado en hilo (post-commit) para facturas %s", move_ids)

        # Garantizar que el hilo arranque SOLO después de que la transacción HTTP haya hecho COMMIT
        # Esto elimina al 100% los errores 'could not serialize access due to concurrent update'
        if hasattr(self.env.cr, 'postcommit'):
            self.env.cr.postcommit.add(_start_worker_thread)
        else:
            _start_worker_thread()

    @classmethod
    def _run_background_ocr(cls, db_name, user_id, move_ids):
        registry = odoo.registry(db_name)

        def _process_single_move(mid):
            with registry.cursor() as worker_cr:
                worker_env = api.Environment(worker_cr, user_id, {})
                try:
                    move = worker_env['account.move'].browse(mid)
                    if not move.exists() or move.ocr_status == 'done':
                        return
                    move.ocr_status = 'processing'
                    worker_cr.commit()

                    move._notify_bus_status('processing')
                    move.action_scan_with_ai()
                    worker_cr.commit()

                    # Notificar el estado resultante real (done o mismatch)
                    move._notify_bus_status(move.ocr_status or 'done')
                except Exception as e:
                    worker_cr.rollback()
                    _logger.exception("Error en worker OCR para factura ID %s: %s", mid, e)
                    try:
                        move = worker_env['account.move'].browse(mid)
                        if move.exists():
                            move.write({
                                'ocr_status': 'error',
                                'ocr_error_message': str(e),
                            })
                            worker_cr.commit()
                            move._notify_bus_status('error')
                    except Exception:
                        pass

        for mid in move_ids:
            _process_single_move(mid)

    def _notify_bus_status(self, status):
        try:
            payload = {
                'id': self.id,
                'move_id': self.id,
                'status': status,
                'event': status,
                'filename': self.attachment_ids[0].name if self.attachment_ids else 'Factura',
                'partner_name': self.partner_id.name if self.partner_id else '',
                'partner': self.partner_id.name if self.partner_id else '',
                'total': self.amount_total,
                'amount_total': self.amount_total,
                'ref': self.ref or '',
                'move_name': self.name or '',
                'error': self.ocr_error_message or '',
                'is_duplicate': self.is_duplicate_detected,
                'iban_status': self.ocr_iban_status,
                'mismatch': getattr(self, 'ocr_company_mismatch', False),
                'mismatch_details': getattr(self, 'ocr_mismatch_details', '') or '',
            }
            target = self.env.user.partner_id
            self.env['bus.bus']._sendone(target, 'ocr_batch_status', payload)
        except Exception as e:
            _logger.debug("No se pudo enviar notificación bus: %s", e)

    @api.model
    def _cron_process_pending_ocr(self):
        stale = self.search([
            ('ocr_status', '=', 'processing'),
            ('write_date', '<', fields.Datetime.now() - datetime.timedelta(minutes=15)),
            ('move_type', 'in', ('in_invoice', 'in_receipt', 'in_refund', 'out_invoice', 'out_refund', 'out_receipt')),
        ])
        if stale:
            stale.write({'ocr_status': 'pending'})
        pending_moves = self.search([
            ('ocr_status', '=', 'pending'),
            ('move_type', 'in', ('in_invoice', 'in_receipt', 'in_refund', 'out_invoice', 'out_refund', 'out_receipt')),
        ], limit=10)
        if pending_moves:
            self._trigger_background_ocr_worker(pending_moves.ids)
