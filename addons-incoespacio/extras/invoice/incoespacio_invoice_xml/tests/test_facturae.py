# -*- coding: utf-8 -*-
import os
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import make_msgid

from odoo.tests.common import TransactionCase

from odoo.addons.incoespacio_invoice_xml.models.facturae_parser import parse

_FIX = os.path.join(os.path.dirname(__file__), "fixtures", "sample_facturae.xml")


class TestFacturae(TransactionCase):
    def setUp(self):
        super().setUp()
        self.env.company.vat = "ESB25962432"

    def _xml(self, invoice_class="OO", extra=""):
        with open(_FIX, encoding="utf-8") as handle:
            raw = handle.read()
        raw = raw.replace(
            "<InvoiceClass>OO</InvoiceClass>",
            "<InvoiceClass>%s</InvoiceClass>" % invoice_class,
        )
        if extra:
            raw = raw.replace("</Invoices>", extra + "</Invoices>")
        return raw.encode()

    def _raw(self, payload, name="factura.xml"):
        msg = MIMEMultipart()
        msg["From"] = "Proveedor <prov-xml@example.com>"
        msg["To"] = "facturacion@incoespacio.com"
        msg["Subject"] = "Facturae"
        msg["Message-Id"] = make_msgid()
        msg.attach(MIMEText("XML adjunto", "plain", "utf-8"))
        part = MIMEApplication(payload, _subtype="xml")
        part.add_header("Content-Disposition", "attachment", filename=name)
        msg.attach(part)
        return msg.as_bytes()

    def _incoming(self, payload, name="factura.xml"):
        last = self.env["account.move"].search([], order="id desc", limit=1)
        self.env["mail.thread"].with_context(
            fetchmail_cron_running=True
        ).message_process("account.move", self._raw(payload, name))
        return self.env["account.move"].search([("id", ">", last.id or 0)])

    def test_parse_sample(self):
        data = parse(self._xml())
        self.assertEqual(data["emisor"]["cif"], "B11111111")
        self.assertEqual(data["receptor"]["cif"], "B25962432")
        self.assertEqual(data["factura"]["numero"], "FA-104")
        self.assertEqual(data["factura"]["total"], 121.0)
        self.assertEqual(len(data["lineas"]), 1)
        self.assertEqual(data["lineas"][0]["porcentaje_iva"], 21.0)
        self.assertIn("P260285", data["lineas"][0]["descripcion"])
        self.assertEqual(data["pago"]["iban"], "ES9121000418450200051332")
        self.assertFalse(data["es_rectificativa"])
        self.assertEqual(data["facturas_en_lote"], 1)

    def test_parse_rejects_other_xml(self):
        self.assertIsNone(parse(b"<root/>"))
        self.assertIsNone(parse(b"esto no es xml"))
        self.assertIsNone(parse(b""))

    def test_mail_fills_vendor_bill(self):
        moves = self._incoming(self._xml())
        self.assertEqual(len(moves), 1)
        move = moves
        self.assertEqual(move.move_type, "in_invoice")
        self.assertEqual(move.ref, "FA-104")
        self.assertIn("11111111", move.partner_id.vat or "")
        self.assertAlmostEqual(move.amount_total, 121.0, places=2)
        self.assertIn("P260285", " ".join(move.invoice_line_ids.mapped("name")))
        self.assertEqual(move.ocr_status, "done")
        self.assertTrue(move.ocr_from_mail)

    def test_other_xml_stays_in_review(self):
        moves = self._incoming(b"<pedido/>", name="pedido.xml")
        self.assertEqual(len(moves), 1)
        self.assertEqual(moves.ocr_status, "review")
        self.assertEqual(moves.ocr_review_reason, "xml_unreadable")

    def test_corrective_is_refund(self):
        moves = self._incoming(self._xml("OR"), name="abono.xml")
        self.assertEqual(moves.move_type, "in_refund")
        self.assertAlmostEqual(moves.amount_total, 121.0, places=2)

    def test_same_number_and_cif_is_duplicate(self):
        partner = self.env["res.partner"].create(
            {"name": "Fontaneria Prueba SL", "vat": "B11111111", "supplier_rank": 1}
        )
        existing = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": partner.id,
                "ref": "FA-104",
            }
        )
        moves = self._incoming(self._xml(), name="otra.xml")
        self.assertEqual(moves.ocr_review_reason, "duplicate_file")
        self.assertEqual(moves.duplicate_move_id, existing)

    def test_batch_keeps_first_and_warns(self):
        second = """
        <Invoice>
          <InvoiceHeader>
            <InvoiceNumber>105</InvoiceNumber>
            <InvoiceSeriesCode>FA</InvoiceSeriesCode>
            <InvoiceClass>OO</InvoiceClass>
          </InvoiceHeader>
          <InvoiceIssueData><IssueDate>2026-11-16</IssueDate></InvoiceIssueData>
          <InvoiceTotals><InvoiceTotal>10.00</InvoiceTotal></InvoiceTotals>
        </Invoice>
        """
        data = parse(self._xml(extra=second))
        self.assertEqual(data["facturas_en_lote"], 2)
        self.assertEqual(data["factura"]["numero"], "FA-104")
        moves = self._incoming(self._xml(extra=second), name="lote.xml")
        self.assertEqual(len(moves), 1)
        self.assertEqual(moves.ref, "FA-104")
        self.assertTrue(any("primera" in (msg.body or "") for msg in moves.message_ids))
