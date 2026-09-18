import base64

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestOcrScan(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {"name": "Proveedor OCR", "is_company": True, "vat": "B12345678"}
        )
        cls.product = cls.env["product.product"].search([], limit=1)

    def _bill(self, ref=None, lines=False):
        vals = {
            "move_type": "in_invoice",
            "partner_id": self.partner.id,
            "invoice_date": "2026-01-15",
        }
        if ref:
            vals["ref"] = ref
        if lines:
            vals["invoice_line_ids"] = [
                (
                    0,
                    0,
                    {
                        "name": "Linea existente",
                        "product_id": self.product.id,
                        "quantity": 1,
                        "price_unit": 10,
                        "tax_ids": [(6, 0, [])],
                    },
                )
            ]
        return self.env["account.move"].create(vals)

    def test_chatter_attachment_found(self):
        move = self._bill()
        attach = self.env["ir.attachment"].create(
            {
                "name": "factura.pdf",
                "datas": base64.b64encode(b"%PDF-1.4 test"),
                "mimetype": "application/pdf",
            }
        )
        move.message_post(attachment_ids=[attach.id])
        atts = move._ocr_attachments().filtered(
            lambda a: a.mimetype == "application/pdf"
            or (a.name and a.name.lower().endswith(".pdf"))
        )
        self.assertTrue(atts)

    def test_scan_raises_without_file(self):
        move = self._bill()
        with self.assertRaises(UserError):
            move.action_scan_with_ai()

    def test_duplicate_by_ref(self):
        self._bill(ref="F-100")
        other = self._bill()
        other._check_invoice_duplicate(self.partner, "F-100", 0)
        self.assertTrue(other.is_duplicate_detected)
        other._check_invoice_duplicate(self.partner, "F-999", 0)
        self.assertFalse(other.is_duplicate_detected)

    def test_reocr_keeps_lines(self):
        move = self._bill(lines=True)
        names = move.invoice_line_ids.mapped("name")
        move._apply_ai_extracted_data(
            {
                "factura": {"numero": "F-KEEP", "total": 10},
                "emisor": {"cif": "B12345678", "nombre": "Proveedor OCR"},
                "receptor": {},
                "lineas": [
                    {
                        "descripcion": "Nueva linea OCR",
                        "cantidad": 1,
                        "precio_unitario": 99,
                    }
                ],
                "pago": {},
            },
            force=True,
        )
        self.assertEqual(move.invoice_line_ids.mapped("name"), names)
        self.assertEqual(move.ref, "F-KEEP")

    def test_fiscal_mismatch_skips_lines(self):
        self.env.company.vat = "B25962432"
        move = self._bill()
        move._apply_ai_extracted_data(
            {
                "factura": {"numero": "F-MIS", "total": 50},
                "emisor": {"cif": "B25962432", "nombre": self.env.company.name},
                "receptor": {"cif": "B12345678", "nombre": "Proveedor OCR"},
                "lineas": [
                    {
                        "descripcion": "No debe crearse",
                        "cantidad": 1,
                        "precio_unitario": 50,
                    }
                ],
                "pago": {},
            }
        )
        self.assertEqual(move.ocr_status, "mismatch")
        self.assertTrue(move.ocr_company_mismatch)
        self.assertFalse(move.invoice_line_ids.filtered(lambda l: l.display_type == "product"))

    def test_header_irpf_skipped_on_many_lines(self):
        move = self._bill()
        move._apply_ai_extracted_data(
            {
                "factura": {
                    "numero": "F-IRPF",
                    "retencion_irpf_porcentaje": 15,
                    "total": 30,
                },
                "emisor": {"cif": "B12345678", "nombre": "Proveedor OCR"},
                "receptor": {},
                "lineas": [
                    {
                        "descripcion": "Linea A",
                        "cantidad": 1,
                        "precio_unitario": 10,
                        "porcentaje_iva": 21,
                    },
                    {
                        "descripcion": "Linea B",
                        "cantidad": 1,
                        "precio_unitario": 20,
                        "porcentaje_iva": 21,
                    },
                ],
                "pago": {},
            },
            force=True,
        )
        lines = move.invoice_line_ids.filtered(lambda l: l.display_type == "product")
        self.assertEqual(len(lines), 2)
        self.assertFalse(any(t.amount == -15 for t in lines.tax_ids))

    def test_new_iban_does_not_create_bank(self):
        move = self._bill()
        move._process_iban_verification(self.partner, "ES91 2100 0418 4502 0005 1332")
        self.assertEqual(move.ocr_iban_status, "new")
        self.assertFalse(
            self.env["res.partner.bank"].search(
                [("partner_id", "=", self.partner.id)]
            )
        )

    def test_ocr_attachments_prefers_parte(self):
        move = self._bill()
        self.env["ir.attachment"].create(
            {
                "name": "factura.pdf",
                "datas": base64.b64encode(b"%PDF-1.4 full"),
                "mimetype": "application/pdf",
                "res_model": "account.move",
                "res_id": move.id,
            }
        )
        part = self.env["ir.attachment"].create(
            {
                "name": "factura_parte_1.pdf",
                "datas": base64.b64encode(b"%PDF-1.4 part"),
                "mimetype": "application/pdf",
                "res_model": "account.move",
                "res_id": move.id,
            }
        )
        atts = move._ocr_attachments()
        self.assertEqual(atts.ids, part.ids)
