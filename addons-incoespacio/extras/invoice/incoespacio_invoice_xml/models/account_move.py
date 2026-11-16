# -*- coding: utf-8 -*-
import json
import logging

from markupsafe import Markup

from odoo import _, fields, models

from .facturae_parser import parse

_logger = logging.getLogger(__name__)
_INVOICE_TYPES = ("in_invoice", "in_refund", "out_invoice", "out_refund")


class AccountMove(models.Model):
    _inherit = "account.move"

    ocr_review_reason = fields.Selection(
        selection_add=[("xml_unreadable", "XML no legible")],
        ondelete={"xml_unreadable": "set null"},
    )

    def _get_edi_decoder(self, file_data, new=False):
        if file_data.get("type") == "xml" and self.env.context.get(
            "fetchmail_cron_running"
        ):

            def _decode(move, data, new=False):
                try:
                    return move._xml_take(data)
                except Exception:
                    _logger.exception(
                        "Facturae: no se pudo leer %s", data.get("filename")
                    )
                    move.write(
                        {
                            "ocr_from_mail": True,
                            "ocr_status": "error",
                            "ocr_error_message": _(
                                "No se pudo leer el XML del correo."
                            ),
                        }
                    )
                    return False

            return _decode
        return super()._get_edi_decoder(file_data, new=new)

    def _xml_take(self, file_data):
        self.ensure_one()
        data = parse(file_data.get("content") or b"")
        if not data:
            self.write(
                {
                    "ocr_from_mail": True,
                    "ocr_status": "review",
                    "ocr_review_reason": "xml_unreadable",
                }
            )
            self.message_post(
                body=Markup("<div class='alert alert-warning'><b>%s</b> %s</div>")
                % (
                    _("Facturae:"),
                    _("el XML no es un Facturae legible."),
                ),
                subtype_xmlid="mail.mt_note",
            )
            return True
        duplicate = self._ocr_mail_duplicate_move(file_data.get("attachment"))
        if not duplicate:
            duplicate = self._xml_same_invoice(data)
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
                "ocr_review_reason": False,
                "ocr_raw_extracted_json": json.dumps(data, ensure_ascii=False),
            }
        )
        self.with_context(
            ocr_xml_rectificativa=bool(data.get("es_rectificativa"))
        )._apply_ai_extracted_data(data)
        if data.get("facturas_en_lote", 1) > 1:
            self.message_post(
                body=Markup("<div class='alert alert-warning'><b>%s</b> %s</div>")
                % (
                    _("Facturae:"),
                    _("el lote trae %s facturas; solo se ha leído la primera.")
                    % data["facturas_en_lote"],
                ),
                subtype_xmlid="mail.mt_note",
            )
        return True

    def _xml_same_invoice(self, data):
        number = ((data.get("factura") or {}).get("numero") or "").strip()
        cif = self._clean_vat((data.get("emisor") or {}).get("cif"))
        if not number or not cif:
            return self.env["account.move"]
        found = (
            self.env["account.move"]
            .sudo()
            .search(
                [
                    ("state", "!=", "cancel"),
                    ("id", "!=", self.id),
                    ("move_type", "in", _INVOICE_TYPES),
                    "|",
                    ("ref", "=", number),
                    ("name", "=", number),
                ]
            )
        )
        return found.filtered(lambda move: self._clean_vat(move.partner_id.vat) == cif)[
            :1
        ]

    def _ocr_mail_set_kind(self, kind):
        result = super()._ocr_mail_set_kind(kind)
        if self.env.context.get("ocr_xml_rectificativa"):
            self.move_type = "out_refund" if kind == "out" else "in_refund"
        return result
