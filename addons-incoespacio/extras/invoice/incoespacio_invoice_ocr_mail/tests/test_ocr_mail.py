# -*- coding: utf-8 -*-
import io
import json
from datetime import timedelta
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import make_msgid
from unittest.mock import patch

from PyPDF2 import PdfFileWriter

from odoo import fields
from odoo.tests.common import TransactionCase

from odoo.addons.incoespacio_ai_core.models.ai_ocr_service import AiOcrService


class TestOcrMail(TransactionCase):
    def setUp(self):
        super().setUp()
        queued = self.env["account.move"].search(
            [("ocr_status", "in", ("pending", "processing"))]
        )
        if queued:
            queued.write({"ocr_status": "done"})
        self.env.company.vat = "ESB25962432"
        self.sender = self.env["res.partner"].create(
            {"name": "Remitente correo", "email": "remite-ocr@example.com"}
        )

    def _pdf(self, width):
        writer = PdfFileWriter()
        writer.addBlankPage(width, width)
        buffer = io.BytesIO()
        writer.write(buffer)
        return buffer.getvalue()

    def _raw(self, files, from_addr="Proveedor <prov-ocr@example.com>"):
        msg = MIMEMultipart()
        msg["From"] = from_addr
        msg["To"] = "facturas@example.com"
        msg["Subject"] = "Factura"
        msg["Message-Id"] = make_msgid()
        msg.attach(MIMEText("Factura adjunta", "plain", "utf-8"))
        for name, raw in files:
            part = MIMEApplication(raw, _subtype="pdf")
            part.add_header("Content-Disposition", "attachment", filename=name)
            msg.attach(part)
        return msg.as_bytes()

    def _incoming(self, raw, user=None):
        thread = self.env["mail.thread"]
        if user:
            thread = thread.with_user(user)
        last = self.env["account.move"].search([], order="id desc", limit=1)
        thread.with_context(fetchmail_cron_running=True).message_process(
            "account.move", raw
        )
        return self.env["account.move"].search([("id", ">", last.id or 0)])

    def _data(self, emisor, receptor, numero="F-1"):
        return {
            "factura": {
                "numero": numero,
                "total": 10,
                "fecha_emision": "2026-01-15",
            },
            "emisor": {"cif": emisor, "nombre": "Emisor"},
            "receptor": {"cif": receptor, "nombre": "Receptor"},
            "lineas": [
                {
                    "descripcion": "Obra",
                    "cantidad": 1,
                    "precio_unitario": 10,
                    "porcentaje_iva": 21,
                }
            ],
            "pago": {},
        }

    def _mail_move(self):
        move = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "ocr_from_mail": True,
                "partner_id": self.sender.id,
            }
        )
        return move

    def test_two_pdfs_are_queued(self):
        moves = self._incoming(
            self._raw([("a.pdf", self._pdf(72)), ("b.pdf", self._pdf(90))])
        )
        self.assertEqual(len(moves), 2)
        self.assertEqual(set(moves.mapped("move_type")), {"in_invoice"})
        self.assertEqual(set(moves.mapped("ocr_status")), {"pending"})
        self.assertTrue(all(moves.mapped("ocr_from_mail")))

    def test_mail_without_attachment_goes_to_review(self):
        moves = self._incoming(self._raw([]))
        self.assertEqual(len(moves), 1)
        self.assertEqual(moves.ocr_status, "review")
        self.assertEqual(moves.ocr_review_reason, "no_attachment")
        self.assertTrue(moves.ocr_from_mail)

    def test_internal_forward_without_accounting_rights(self):
        user = self.env["res.users"].create(
            {
                "name": "Reenvio interno",
                "login": "reenvio_ocr_mail",
                "email": "reenvio_ocr_mail@example.com",
                "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        moves = self._incoming(
            self._raw([], from_addr="Reenvio <reenvio_ocr_mail@example.com>"),
            user=user,
        )
        self.assertEqual(len(moves), 1)
        self.assertEqual(moves.ocr_review_reason, "no_attachment")

    def test_decoder_error_does_not_raise(self):
        with patch.object(
            type(self.env["account.move"]),
            "_ocr_mail_take_pdf",
            side_effect=RuntimeError("boom"),
        ):
            moves = self._incoming(self._raw([("a.pdf", self._pdf(72))]))
        self.assertEqual(len(moves), 1)
        self.assertEqual(moves.ocr_status, "error")

    def test_same_pdf_is_duplicate_and_skips_gemini(self):
        pdf = self._pdf(72)
        first = self._incoming(self._raw([("a.pdf", pdf)]))
        second = self._incoming(
            self._raw([("a.pdf", pdf)], from_addr="Otro <otro-ocr@example.com>")
        )
        self.assertEqual(first.ocr_status, "pending")
        self.assertEqual(second.ocr_review_reason, "duplicate_file")
        self.assertEqual(second.duplicate_move_id, first)
        with patch.object(
            AiOcrService, "analyze_invoice_document", return_value={}
        ) as mock:
            self.env["account.move"]._cron_process_pending_ocr()
        self.assertEqual(mock.call_count, 1)
        self.assertEqual(second.ocr_review_reason, "duplicate_file")

    def test_cancelled_original_is_not_a_duplicate(self):
        pdf = self._pdf(64)
        first = self._incoming(self._raw([("a.pdf", pdf)]))
        first.button_cancel()
        second = self._incoming(
            self._raw([("a.pdf", pdf)], from_addr="Otro <otro2-ocr@example.com>")
        )
        self.assertEqual(second.ocr_status, "pending")
        self.assertFalse(second.ocr_review_reason)

    def test_process_anyway_requeues(self):
        pdf = self._pdf(50)
        self._incoming(self._raw([("a.pdf", pdf)]))
        second = self._incoming(
            self._raw([("a.pdf", pdf)], from_addr="Otro <otro3-ocr@example.com>")
        )
        second.action_ocr_mail_process_anyway()
        self.assertEqual(second.ocr_status, "pending")
        self.assertFalse(second.is_duplicate_detected)
        self.assertFalse(second.duplicate_move_id)

    def test_emisor_company_becomes_customer_invoice(self):
        move = self._mail_move()
        move._apply_ai_extracted_data(self._data("B25962432", "B12345678", "C-1"))
        self.assertEqual(move.move_type, "out_invoice")
        self.assertEqual(move.journal_id.type, "sale")
        self.assertNotEqual(move.partner_id, self.sender)
        self.assertTrue(
            move.invoice_line_ids.filtered(lambda line: line.display_type == "product")
        )

    def test_receptor_company_stays_vendor_bill(self):
        move = self._mail_move()
        move._apply_ai_extracted_data(self._data("B12345678", "B25962432", "P-1"))
        self.assertEqual(move.move_type, "in_invoice")
        self.assertEqual(move.journal_id.type, "purchase")
        self.assertNotEqual(move.partner_id, self.sender)

    def test_unknown_or_both_cifs_go_to_review(self):
        unknown = self._mail_move()
        unknown._apply_ai_extracted_data(self._data("B12345678", "A58818501"))
        self.assertEqual(unknown.ocr_status, "review")
        self.assertEqual(unknown.ocr_review_reason, "unknown_type")
        self.assertFalse(
            unknown.invoice_line_ids.filtered(
                lambda line: line.display_type == "product"
            )
        )
        both = self._mail_move()
        both._apply_ai_extracted_data(self._data("B25962432", "ESB25962432"))
        self.assertEqual(both.ocr_review_reason, "unknown_type")

    def test_as_customer_reuses_stored_json(self):
        move = self._mail_move()
        move.write(
            {
                "ocr_status": "review",
                "ocr_review_reason": "unknown_type",
                "ocr_raw_extracted_json": json.dumps(
                    self._data("B25962432", "B12345678", "C-2")
                ),
            }
        )
        with patch.object(AiOcrService, "analyze_invoice_document") as mock:
            move.action_ocr_mail_as_customer()
            mock.assert_not_called()
        self.assertEqual(move.move_type, "out_invoice")
        self.assertEqual(move.ocr_status, "done")

    def test_not_invoice_stays_in_review(self):
        move = self._mail_move()
        with patch.object(
            AiOcrService,
            "analyze_invoice_document",
            return_value={"es_factura_valida": False, "motivo": "Es un albarán"},
        ):
            move._process_ai_ocr_content(b"%PDF", "albaran.pdf")
        self.assertEqual(move.ocr_status, "review")
        self.assertEqual(move.ocr_review_reason, "not_invoice")

    def test_mail_error_is_retried_for_thirty_minutes(self):
        move = self._aged_error(0)
        with patch.object(
            type(move),
            "action_scan_with_ai",
            lambda this: this.write({"ocr_status": "done"}),
        ):
            self.env["account.move"]._cron_process_pending_ocr()
        self.assertEqual(move.ocr_mail_retries, 1)
        self.assertEqual(move.ocr_status, "done")

    def test_mail_error_stops_after_three_retries(self):
        move = self._aged_error(3)
        self.env["account.move"]._cron_process_pending_ocr()
        self.assertEqual(move.ocr_status, "error")
        self.assertEqual(move.ocr_mail_retries, 3)

    def test_company_without_vat_is_explained(self):
        self.env.company.vat = False
        move = self._mail_move()
        move._apply_ai_extracted_data(self._data("B12345678", "B25962432"))
        self.assertEqual(move.ocr_review_reason, "unknown_type")
        self.assertIn("no tiene CIF", move.message_ids[:1].body)

    def test_multi_pdf_classifies_each_part(self):
        move = self._mail_move()
        payload = {
            "es_factura_valida": True,
            "es_multifactura": True,
            "documentos_particionados": [
                self._data("B12345678", "A58818501", "P-1"),
                self._data("B25962432", "B12345678", "C-9"),
            ],
        }
        with patch.object(
            AiOcrService, "analyze_invoice_document", return_value=payload
        ):
            move._process_ai_ocr_content(b"not-a-pdf", "lote.pdf")
        other = self.env["account.move"].search(
            [("ocr_from_mail", "=", True), ("id", "!=", move.id)]
        )
        self.assertEqual(move.ocr_review_reason, "unknown_type")
        self.assertEqual(len(other), 1)
        self.assertEqual(other.move_type, "out_invoice")
        self.assertTrue(other.ocr_from_mail)

    def _aged_error(self, retries):
        move = self._mail_move()
        move.write(
            {
                "ocr_status": "error",
                "ocr_mail_retries": retries,
                "ocr_error_message": "caida",
            }
        )
        self.env.flush_all()
        past = fields.Datetime.to_string(fields.Datetime.now() - timedelta(minutes=40))
        self.env.cr.execute(
            "UPDATE account_move SET write_date = %s WHERE id = %s",
            [past, move.id],
        )
        move.invalidate_recordset()
        return move

    def _server(self, messages):
        server = self.env["fetchmail.server"].create(
            {
                "name": "Facturas test %s" % make_msgid(),
                "server_type": "imap",
                "server": "imap.example.com",
                "port": 993,
                "is_ssl": True,
                "user": "facturas@example.com",
                "object_id": self.env["ir.model"]._get("account.move").id,
                "attach": True,
            }
        )
        server.write({"state": "done"})
        return server, FakeImap(messages)

    def _fetch(self, server, imap):
        last = self.env["account.move"].search([], order="id desc", limit=1)
        with patch.object(type(server), "connect", lambda this: imap):
            server.fetch_mail()
        return self.env["account.move"].search([("id", ">", last.id or 0)])

    def test_fetch_processes_seen_and_unseen(self):
        server, imap = self._server(
            [
                (b"1", self._raw([("a.pdf", self._pdf(72))])),
                (b"2", self._raw([("b.pdf", self._pdf(90))])),
            ]
        )
        moves = self._fetch(server, imap)
        self.assertEqual(len(moves), 2)
        self.assertEqual(set(moves.mapped("ocr_status")), {"pending"})
        self.assertEqual(len(imap.folders["Odoo-Procesadas"]), 2)
        self.assertFalse(any("UNSEEN" in str(call) for call in imap.calls))

    def test_fetch_ignores_mail_without_invoice_file(self):
        server, imap = self._server([(b"1", self._raw([]))])
        moves = self._fetch(server, imap)
        self.assertFalse(moves)
        self.assertEqual(len(imap.folders["Odoo-Ignorados"]), 1)
        self.assertFalse(imap.folders["Odoo-Procesadas"])

    def test_fetch_moves_failures_and_continues(self):
        server, imap = self._server(
            [
                (b"1", self._raw([("a.pdf", self._pdf(70))])),
                (b"2", self._raw([("b.pdf", self._pdf(80))])),
            ]
        )
        real = type(self.env["mail.thread"]).message_process
        state = {"n": 0}

        def _process(
            this,
            model,
            message,
            custom_values=None,
            save_original=False,
            strip_attachments=False,
            thread_id=None,
        ):
            state["n"] += 1
            if state["n"] == 1:
                raise RuntimeError("boom")
            return real(
                this,
                model,
                message,
                custom_values,
                save_original,
                strip_attachments,
                thread_id,
            )

        last = self.env["account.move"].search([], order="id desc", limit=1)
        with (
            patch.object(type(server), "connect", lambda this: imap),
            patch.object(type(self.env["mail.thread"]), "message_process", _process),
        ):
            server.fetch_mail()
        moves = self.env["account.move"].search([("id", ">", last.id or 0)])
        self.assertEqual(len(moves), 1)
        self.assertEqual(len(imap.folders["Odoo-Errores"]), 1)
        self.assertEqual(len(imap.folders["Odoo-Procesadas"]), 1)

    def test_fetch_same_message_id_once(self):
        raw = self._raw([("a.pdf", self._pdf(60))])
        server, imap = self._server([(b"1", raw), (b"2", raw)])
        moves = self._fetch(server, imap)
        self.assertEqual(len(moves), 1)
        self.assertEqual(len(imap.folders["Odoo-Procesadas"]), 2)

    def test_fetch_searches_since_server_was_created(self):
        server, imap = self._server([(b"1", self._raw([]))])
        self._fetch(server, imap)
        search = [call for call in imap.calls if call[0].upper() == "SEARCH"]
        self.assertEqual(len(search), 1)
        self.assertIn(server._ocr_mail_since(server.create_date), search[0][1])

    def _silence_other_servers(self, server):
        others = self.env["fetchmail.server"].search([("id", "!=", server.id)])
        if others:
            others.write({"active": False})

    def test_health_notifies_when_connect_fails(self):
        server, _imap = self._server([])
        self._silence_other_servers(server)
        notified = []

        def _notify(this, **kwargs):
            notified.append(kwargs)
            return True

        def _boom(this):
            raise RuntimeError("token caducado")

        with (
            patch.object(type(server), "connect", _boom),
            patch.object(type(self.env["mail.thread"]), "message_notify", _notify),
        ):
            self.env["fetchmail.server"]._cron_ocr_mail_health()
        self.assertEqual(len(notified), 1)
        self.assertIn("token caducado", notified[0]["body"])
        managers = self.env.ref("account.group_account_manager").users.partner_id
        self.assertTrue(set(notified[0]["partner_ids"]) & set(managers.ids))

    def test_health_notifies_error_folder(self):
        server, imap = self._server([])
        self._silence_other_servers(server)
        imap.folders["Odoo-Errores"].extend([b"a", b"b"])
        notified = []

        def _notify(this, **kwargs):
            notified.append(kwargs)
            return True

        with (
            patch.object(type(server), "connect", lambda this: imap),
            patch.object(type(self.env["mail.thread"]), "message_notify", _notify),
        ):
            server._ocr_mail_health()
        self.assertEqual(len(notified), 1)
        self.assertIn("2", notified[0]["body"])


class FakeImap:
    def __init__(self, messages):
        self.inbox = list(messages)
        self.folders = {
            "Odoo-Procesadas": [],
            "Odoo-Ignorados": [],
            "Odoo-Errores": [],
        }
        self.calls = []

    def select(self, mailbox="INBOX"):
        self.calls.append(("SELECT", (mailbox,)))
        return "OK", [b"1"]

    def uid(self, command, *args):
        self.calls.append((command, args))
        command = command.upper()
        if command == "SEARCH":
            uids = b" ".join(uid for uid, _raw in self.inbox)
            return "OK", [uids]
        if command == "FETCH":
            raw = dict(self.inbox)[args[0]]
            return "OK", [(b"1 (RFC822)", raw), b")"]
        if command == "MOVE":
            uid, folder = args
            raw = dict(self.inbox)[uid]
            self.inbox = [item for item in self.inbox if item[0] != uid]
            self.folders.setdefault(folder, []).append(raw)
            return "OK", [b""]
        return "OK", [b""]

    def create(self, name):
        self.folders.setdefault(name, [])
        return "OK", [b"Created"]

    def status(self, mailbox, names):
        count = len(self.folders.get(mailbox, []))
        return "OK", [("%s (MESSAGES %s)" % (mailbox, count)).encode()]

    def logout(self):
        return "OK", [b"Bye"]
