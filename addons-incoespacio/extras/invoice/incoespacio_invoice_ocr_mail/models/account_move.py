# -*- coding: utf-8 -*-
import json
import logging
from datetime import timedelta

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    ocr_status = fields.Selection(
        selection_add=[("review", "Pendiente de revisar")],
        ondelete={"review": "set default"},
    )
    ocr_from_mail = fields.Boolean(string="Llegó por correo", copy=False)
    ocr_review_reason = fields.Selection(
        [
            ("no_attachment", "Sin PDF válido"),
            ("duplicate_file", "PDF duplicado"),
            ("unknown_type", "Tipo desconocido"),
            ("not_invoice", "No es una factura"),
        ],
        string="Motivo de revisión",
        copy=False,
    )
    ocr_mail_retries = fields.Integer(string="Reintentos OCR correo", copy=False)

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        custom_values = dict(custom_values or {})
        from_mail = bool(self.env.context.get("fetchmail_cron_running"))
        if from_mail:
            # sudo justificado: fetchmail puede atribuir el correo a un empleado
            # sin permisos de contabilidad; el borrador lo crea el buzón.
            self = self.sudo()
        if from_mail and custom_values.get("move_type", "entry") not in (
            "out_invoice",
            "in_invoice",
        ):
            journal = self._ocr_mail_journal("purchase")
            if journal:
                custom_values.update(
                    {
                        "move_type": "in_invoice",
                        "journal_id": journal.id,
                        "company_id": journal.company_id.id,
                    }
                )
        move = super().message_new(msg_dict, custom_values=custom_values)
        if from_mail and move:
            # El PDF, si lo hay, llega después en message_post y el decoder
            # sustituye este estado.
            move.write(
                {
                    "ocr_from_mail": True,
                    "ocr_status": "review",
                    "ocr_review_reason": "no_attachment",
                }
            )
        return move

    def _get_edi_decoder(self, file_data, new=False):
        if file_data.get("type") == "pdf" and self.env.context.get(
            "fetchmail_cron_running"
        ):
            # ponytail: jpeg/png no llegan aquí; el core los tira
            # (ALLOWED_MIMETYPES). Para aceptarlos, tratar aquí type binary
            # con mimetype image/*.
            def _mail_decoder(move, fd, new=False):
                try:
                    return move._ocr_mail_take_pdf(fd)
                except Exception:
                    _logger.exception(
                        "OCR mail: no se pudo encolar %s", fd.get("filename")
                    )
                    move.write(
                        {
                            "ocr_from_mail": True,
                            "ocr_status": "error",
                            "ocr_error_message": _(
                                "No se pudo encolar el PDF del correo."
                            ),
                        }
                    )
                    return False

            return _mail_decoder
        return super()._get_edi_decoder(file_data, new=new)

    def _ocr_mail_take_pdf(self, file_data):
        self.ensure_one()
        if not self.is_invoice(include_receipts=True):
            journal = self._ocr_mail_journal("purchase")
            self.write(
                {
                    "move_type": "in_invoice",
                    "journal_id": journal.id,
                    "company_id": journal.company_id.id,
                }
            )
        duplicate = self._ocr_mail_duplicate_move(file_data.get("attachment"))
        if duplicate:
            self.write(
                {
                    "ocr_from_mail": True,
                    "ocr_status": "review",
                    "ocr_review_reason": "duplicate_file",
                    "is_duplicate_detected": True,
                    "duplicate_move_id": duplicate.id,
                }
            )
            return True
        self.write(
            {
                "ocr_from_mail": True,
                "ocr_status": "pending",
                "ocr_review_reason": False,
            }
        )
        self._trigger_ocr_cron()
        return True

    def _ocr_mail_duplicate_move(self, attachment):
        checksum = attachment.checksum if attachment else False
        if not checksum:
            return self.env["account.move"]
        # sudo justificado: el remitente no lee los adjuntos de otras facturas
        dup_atts = (
            self.env["ir.attachment"]
            .sudo()
            .search(
                [
                    ("checksum", "=", checksum),
                    ("res_model", "=", "account.move"),
                    ("res_id", "!=", 0),
                    ("id", "!=", attachment.id),
                ]
            )
        )
        moves = (
            self.env["account.move"]
            .sudo()
            .browse(dup_atts.mapped("res_id"))
            .exists()
            .filtered(lambda m: m.id != self.id and m.state != "cancel")
        )
        return moves[:1]

    def _ocr_mail_journal(self, journal_type):
        company = self.company_id or self.env.company
        return self.env["account.journal"].search(
            [
                *self.env["account.journal"]._check_company_domain(company),
                ("type", "=", journal_type),
            ],
            limit=1,
        )

    def _ocr_mail_kind(self, data):
        company_vat = self._clean_vat(self.company_id.vat)
        if not company_vat:
            return False
        emisor = self._clean_vat((data.get("emisor") or {}).get("cif"))
        receptor = self._clean_vat((data.get("receptor") or {}).get("cif"))
        emisor_is_us = bool(emisor) and emisor == company_vat
        receptor_is_us = bool(receptor) and receptor == company_vat
        if emisor_is_us and not receptor_is_us:
            return "out"
        if receptor_is_us and not emisor_is_us:
            return "in"
        return False

    def _ocr_mail_set_kind(self, kind):
        journal_type = "sale" if kind == "out" else "purchase"
        journal = self._ocr_mail_journal(journal_type)
        if not journal:
            raise UserError(
                _("No hay un diario de %s para registrar esta factura.") % journal_type
            )
        # El remitente del correo no es el tercero de la factura.
        self.write(
            {
                "move_type": "out_invoice" if kind == "out" else "in_invoice",
                "journal_id": journal.id,
                "partner_id": False,
                "ocr_review_reason": False,
            }
        )
        return True

    def _apply_ai_extracted_data(self, data, force=False):
        self.ensure_one()
        # ponytail: una rectificativa entra como factura. Upgrade: campo
        # es_rectificativa en el prompt de incoespacio_ai_core.
        if self.ocr_from_mail and not force:
            kind = self._ocr_mail_kind(data)
            if not kind:
                self.write(
                    {
                        "ocr_status": "review",
                        "ocr_review_reason": "unknown_type",
                    }
                )
                self.message_post(
                    body=self._ocr_mail_unknown_note(data),
                    subtype_xmlid="mail.mt_note",
                )
                return False
            self._ocr_mail_set_kind(kind)
        return super()._apply_ai_extracted_data(data, force=force)

    def _ocr_mail_unknown_note(self, data):
        if not self._clean_vat(self.company_id.vat):
            text = _("La empresa no tiene CIF y la factura no se puede clasificar.")
        else:
            emisor = (data.get("emisor") or {}).get("cif") or "—"
            receptor = (data.get("receptor") or {}).get("cif") or "—"
            text = _("Tipo desconocido. Emisor %s, receptor %s.") % (emisor, receptor)
        return (
            Markup("<div class='alert alert-warning'><b>OCR correo:</b> %s</div>")
            % text
        )

    def _process_ai_ocr_content(self, file_bytes, filename, force=False):
        self.ensure_one()
        target = self
        if self.ocr_from_mail:
            target = self.with_context(default_ocr_from_mail=True)
        result = super(AccountMove, target)._process_ai_ocr_content(
            file_bytes, filename, force=force
        )
        data = {}
        if self.ocr_from_mail and self.ocr_raw_extracted_json:
            try:
                data = json.loads(self.ocr_raw_extracted_json)
            except json.JSONDecodeError:
                data = {}
        if data.get("es_factura_valida") is False:
            self.write({"ocr_status": "review", "ocr_review_reason": "not_invoice"})
        return result

    @api.model
    def _cron_process_pending_ocr(self):
        limit = fields.Datetime.now() - timedelta(minutes=30)
        retry = self.search(
            [
                ("ocr_from_mail", "=", True),
                ("ocr_status", "=", "error"),
                "|",
                ("ocr_mail_retries", "=", False),
                ("ocr_mail_retries", "<", 3),
                ("write_date", "<", limit),
            ]
        )
        for move in retry:
            move.write(
                {"ocr_status": "pending", "ocr_mail_retries": move.ocr_mail_retries + 1}
            )
        return super()._cron_process_pending_ocr()

    def _ocr_mail_force(self, kind):
        self.ensure_one()
        self._ocr_mail_set_kind(kind)
        if self.ocr_raw_extracted_json:
            self._apply_ai_extracted_data(
                json.loads(self.ocr_raw_extracted_json), force=True
            )
            return True
        self.write({"ocr_status": "pending", "ocr_review_reason": False})
        self._trigger_ocr_cron()
        return True

    def action_ocr_mail_as_supplier(self):
        return self._ocr_mail_force("in")

    def action_ocr_mail_as_customer(self):
        return self._ocr_mail_force("out")

    def action_ocr_mail_process_anyway(self):
        self.ensure_one()
        self.write(
            {
                "ocr_status": "pending",
                "ocr_review_reason": False,
                "is_duplicate_detected": False,
                "duplicate_move_id": False,
            }
        )
        self._trigger_ocr_cron()
        return True
