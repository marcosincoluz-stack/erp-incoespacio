from odoo import fields
from odoo.tests.common import TransactionCase


class TestInvoiceDate(TransactionCase):
    def test_empty_invoice_date_keeps_accounting_date(self):
        move = self.env["account.move"].new({"move_type": "out_invoice"})
        move.date = fields.Date.from_string("2026-03-08")
        move.invoice_date = False
        move._onchange_invoice_date_inherit()
        self.assertEqual(str(move.date), "2026-03-08")

    def test_create_copies_invoice_date(self):
        partner = self.env["res.partner"].create({"name": "Fecha OCR"})
        move = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": partner.id,
                "invoice_date": "2026-03-08",
            }
        )
        self.assertEqual(str(move.date), "2026-03-08")
