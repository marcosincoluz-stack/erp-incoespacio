# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase


class TestOcrProduct(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        cls.partner = cls.env["res.partner"].create(
            {"name": "Gestoría Prueba OCR", "vat": "B22222222", "supplier_rank": 1}
        )
        cls.customer = cls.env["res.partner"].create(
            {"name": "Cliente Prueba OCR", "vat": "B33333333", "customer_rank": 1}
        )
        cls.expense = cls.env["account.account"].search(
            [
                ("account_type", "=", "expense"),
                ("company_id", "=", company.id),
            ],
            limit=1,
        )
        cls.income = cls.env["account.account"].search(
            [
                ("account_type", "=", "income"),
                ("company_id", "=", company.id),
            ],
            limit=1,
        )
        cls.iva_service = cls.env["account.tax"].create(
            {
                "name": "IVA 21 servicios OCR",
                "amount": 21,
                "amount_type": "percent",
                "type_tax_use": "purchase",
            }
        )
        cls.iva_goods = cls.env["account.tax"].create(
            {
                "name": "IVA 21 bienes OCR",
                "amount": 21,
                "amount_type": "percent",
                "type_tax_use": "purchase",
            }
        )
        cls.iva_10 = cls.env["account.tax"].create(
            {
                "name": "IVA 10 OCR",
                "amount": 10,
                "amount_type": "percent",
                "type_tax_use": "purchase",
            }
        )
        cls.iva_4 = cls.env["account.tax"].create(
            {
                "name": "IVA 4 OCR",
                "amount": 4,
                "amount_type": "percent",
                "type_tax_use": "purchase",
            }
        )
        cls.irpf = cls.env["account.tax"].create(
            {
                "name": "IRPF 15 OCR",
                "amount": -15,
                "amount_type": "percent",
                "type_tax_use": "purchase",
            }
        )
        cls.sale_tax = cls.env["account.tax"].create(
            {
                "name": "IVA 21 venta OCR",
                "amount": 21,
                "amount_type": "percent",
                "type_tax_use": "sale",
            }
        )
        cls.laboral = cls._product("Asesoramiento laboral", cls.iva_service)
        cls.fiscal = cls._product("Asesoramiento fiscal", cls.iva_service)
        cls.nominas = cls._product("Cálculo nóminas", cls.iva_service)
        cls.bare = cls._product("Servicio sin IVA", cls.env["account.tax"])
        cls.sold = cls.env["product.product"].create(
            {
                "name": "Servicio al cliente",
                "detailed_type": "service",
                "list_price": 0,
                "taxes_id": [(6, 0, cls.sale_tax.ids)],
                "property_account_income_id": cls.income.id,
            }
        )

    @classmethod
    def _product(cls, name, taxes):
        return cls.env["product.product"].create(
            {
                "name": name,
                "detailed_type": "service",
                "standard_price": 0,
                "list_price": 0,
                "supplier_taxes_id": [(6, 0, taxes.ids)],
                "property_account_expense_id": cls.expense.id,
            }
        )

    def _data(
        self, desc, price=150, iva=21, irpf=0, vendor=True, cif="B22222222", total=None
    ):
        if total is None:
            total = round(price * (1 + iva / 100.0 - irpf / 100.0), 2)
        factura = {"numero": "OCR-1", "total": total}
        if irpf:
            factura["retencion_irpf_porcentaje"] = irpf
        if vendor:
            emisor = {"cif": cif, "nombre": "Gestoría Prueba OCR"}
            receptor = {}
        else:
            emisor = {"cif": "B25962432", "nombre": "Empresa"}
            receptor = {"cif": "B33333333", "nombre": "Cliente Prueba OCR"}
        return {
            "es_factura_valida": True,
            "factura": factura,
            "emisor": emisor,
            "receptor": receptor,
            "lineas": [
                {
                    "descripcion": desc,
                    "cantidad": 1,
                    "precio_unitario": price,
                    "porcentaje_iva": iva,
                }
            ],
            "pago": {},
        }

    def _draft(self, move_type, partner):
        return self.env["account.move"].create(
            {
                "move_type": move_type,
                "partner_id": partner.id,
                "invoice_date": "2026-11-01",
            }
        )

    def _posted(self, move_type, partner, product, name):
        vals = {
            "move_type": move_type,
            "partner_id": partner.id,
            "invoice_date": "2026-10-01",
            "invoice_line_ids": [
                (
                    0,
                    0,
                    {
                        "name": name,
                        "product_id": product.id,
                        "quantity": 1,
                        "price_unit": 80,
                        "tax_ids": [(6, 0, [])],
                    },
                )
            ],
        }
        if (
            move_type in ("in_invoice", "in_refund")
            and "construction_not_job" in self.env["account.move"]._fields
        ):
            vals["construction_not_job"] = True
        move = self.env["account.move"].create(vals)
        move.action_post()
        return move

    def _line(self, move):
        return move.invoice_line_ids.filtered(
            lambda item: item.display_type == "product"
        )

    def test_manual_product_keeps_pdf_price(self):
        move = self._draft("in_invoice", self.partner)
        move._apply_ai_extracted_data(
            self._data("Asesoramiento laboral mes anterior"), force=True
        )
        line = self._line(move)
        self.assertEqual(line.price_unit, 150)
        line.product_id = self.laboral
        self.assertEqual(line.price_unit, 150)
        self.assertEqual(line.name, "Asesoramiento laboral mes anterior")

    def test_manual_product_keeps_customer_price(self):
        move = self._draft("out_invoice", self.customer)
        move._apply_ai_extracted_data(
            self._data("Servicio octubre", vendor=False), force=True
        )
        line = self._line(move)
        line.product_id = self.sold
        self.assertEqual(line.price_unit, 150)
        self.assertEqual(line.name, "Servicio octubre")

    def test_learns_product_and_keeps_price(self):
        self._posted(
            "in_invoice",
            self.partner,
            self.laboral,
            "Asesoramiento laboral mes anterior",
        )
        move = self._draft("in_invoice", self.partner)
        move._apply_ai_extracted_data(
            self._data("Asesoramiento laboral octubre"), force=True
        )
        line = self._line(move)
        self.assertEqual(line.product_id, self.laboral)
        self.assertEqual(line.price_unit, 150)
        self.assertEqual(line.name, "Asesoramiento laboral octubre")
        self.assertEqual(line.account_id, self.expense)

    def test_no_history_leaves_product_empty(self):
        other = self.env["res.partner"].create(
            {"name": "Proveedor nuevo", "vat": "B44444444", "supplier_rank": 1}
        )
        move = self._draft("in_invoice", other)
        move._apply_ai_extracted_data(
            self._data("Asesoramiento laboral octubre", cif="B44444444"), force=True
        )
        line = self._line(move)
        self.assertFalse(line.product_id)
        self.assertEqual(line.price_unit, 150)

    def test_tie_leaves_product_empty(self):
        self._posted(
            "in_invoice", self.partner, self.laboral, "Cálculo nóminas septiembre"
        )
        self._posted(
            "in_invoice", self.partner, self.nominas, "Cálculo nóminas septiembre"
        )
        move = self._draft("in_invoice", self.partner)
        move._apply_ai_extracted_data(
            self._data("Cálculo nóminas septiembre"), force=True
        )
        self.assertFalse(self._line(move).product_id)

    def test_close_description_does_not_match(self):
        self._posted(
            "in_invoice",
            self.partner,
            self.laboral,
            "Asesoramiento laboral mes anterior",
        )
        move = self._draft("in_invoice", self.partner)
        move._apply_ai_extracted_data(
            self._data("Asesoramiento fiscal mes anterior"), force=True
        )
        self.assertFalse(self._line(move).product_id)

    def test_learns_customer_product(self):
        self._posted(
            "out_invoice",
            self.customer,
            self.sold,
            "Asesoramiento laboral mes anterior",
        )
        move = self._draft("out_invoice", self.customer)
        move._apply_ai_extracted_data(
            self._data("Asesoramiento laboral octubre", vendor=False), force=True
        )
        line = self._line(move)
        self.assertEqual(line.product_id, self.sold)
        self.assertEqual(line.price_unit, 150)
        self.assertEqual(line.account_id, self.income)

    def test_product_tax_replaces_first_21(self):
        self._posted(
            "in_invoice",
            self.partner,
            self.laboral,
            "Asesoramiento laboral mes anterior",
        )
        move = self._draft("in_invoice", self.partner)
        move._apply_ai_extracted_data(
            self._data("Asesoramiento laboral octubre", iva=21), force=True
        )
        line = self._line(move)
        self.assertEqual(line.tax_ids, self.iva_service)
        self.assertNotEqual(move.ocr_review_reason, "tax_mismatch")

    def test_tax_rate_mismatch_goes_to_review(self):
        self._posted(
            "in_invoice",
            self.partner,
            self.laboral,
            "Asesoramiento laboral mes anterior",
        )
        move = self._draft("in_invoice", self.partner)
        move._apply_ai_extracted_data(
            self._data("Asesoramiento laboral octubre", iva=10), force=True
        )
        line = self._line(move)
        self.assertEqual(line.product_id, self.laboral)
        self.assertEqual(line.tax_ids, self.iva_service)
        self.assertEqual(move.ocr_status, "review")
        self.assertEqual(move.ocr_review_reason, "tax_mismatch")
        self.assertTrue(
            any("IVA distinto" in (msg.body or "") for msg in move.message_ids)
        )

    def test_pdf_irpf_is_added_when_sheet_has_none(self):
        self._posted(
            "in_invoice",
            self.partner,
            self.laboral,
            "Asesoramiento laboral mes anterior",
        )
        move = self._draft("in_invoice", self.partner)
        move._apply_ai_extracted_data(
            self._data("Asesoramiento laboral octubre", irpf=15), force=True
        )
        line = self._line(move)
        self.assertIn(self.iva_service, line.tax_ids)
        self.assertTrue(any(tax.amount < 0 for tax in line.tax_ids))
        self.assertNotEqual(move.ocr_review_reason, "tax_mismatch")

    def test_empty_sheet_keeps_pdf_tax(self):
        self._posted(
            "in_invoice",
            self.partner,
            self.bare,
            "Servicio sin IVA octubre",
        )
        move = self._draft("in_invoice", self.partner)
        move._apply_ai_extracted_data(
            self._data("Servicio sin IVA noviembre", iva=4), force=True
        )
        line = self._line(move)
        self.assertEqual(line.product_id, self.bare)
        self.assertTrue(line.tax_ids)
        self.assertTrue(all(tax.amount == 4 for tax in line.tax_ids if tax.amount > 0))

    def test_fiscal_position_maps_sheet_tax(self):
        isp = self.env["account.tax"].create(
            {
                "name": "ISP OCR",
                "amount": 0,
                "amount_type": "percent",
                "type_tax_use": "purchase",
            }
        )
        position = self.env["account.fiscal.position"].create(
            {
                "name": "ISP prueba",
                "tax_ids": [
                    (
                        0,
                        0,
                        {"tax_src_id": self.iva_service.id, "tax_dest_id": isp.id},
                    )
                ],
            }
        )
        self.partner.property_account_position_id = position
        self._posted(
            "in_invoice",
            self.partner,
            self.laboral,
            "Asesoramiento laboral mes anterior",
        )
        move = self._draft("in_invoice", self.partner)
        move._apply_ai_extracted_data(
            self._data("Asesoramiento laboral octubre", iva=0), force=True
        )
        line = self._line(move)
        self.assertEqual(line.tax_ids, isp)
        self.assertNotEqual(move.ocr_review_reason, "tax_mismatch")

    def test_short_label_needs_exact_words(self):
        self._posted("in_invoice", self.partner, self.laboral, "Material pladur obra")
        move = self._draft("in_invoice", self.partner)
        move._apply_ai_extracted_data(self._data("Material"), force=True)
        self.assertFalse(self._line(move).product_id)

    def test_one_word_exact_match(self):
        self._posted("in_invoice", self.partner, self.laboral, "Portes")
        move = self._draft("in_invoice", self.partner)
        move._apply_ai_extracted_data(self._data("Portes"), force=True)
        self.assertEqual(self._line(move).product_id, self.laboral)

    def test_close_scores_leave_product_empty(self):
        shared = "tabique pladur pintura solado alicatado fontaneria"
        self._posted(
            "in_invoice",
            self.partner,
            self.laboral,
            shared + " electricidad",
        )
        self._posted(
            "in_invoice",
            self.partner,
            self.fiscal,
            shared + " carpinteria",
        )
        move = self._draft("in_invoice", self.partner)
        move._apply_ai_extracted_data(self._data(shared + " electricidad"), force=True)
        self.assertFalse(self._line(move).product_id)

    def test_matching_total_stays_done(self):
        move = self._draft("in_invoice", self.partner)
        move._apply_ai_extracted_data(
            self._data("Linea sin historial", total=181.5), force=True
        )
        self.assertFalse(move.ocr_review_reason)
        self.assertNotEqual(move.ocr_status, "review")

    def test_wrong_total_goes_to_review(self):
        move = self._draft("in_invoice", self.partner)
        move._apply_ai_extracted_data(
            self._data("Linea sin historial", total=200), force=True
        )
        self.assertEqual(move.ocr_status, "review")
        self.assertEqual(move.ocr_review_reason, "total_mismatch")
        self.assertTrue(
            any("no cuadra" in (msg.body or "") for msg in move.message_ids)
        )

    def test_tax_mismatch_wins_over_total(self):
        self._posted(
            "in_invoice",
            self.partner,
            self.laboral,
            "Asesoramiento laboral mes anterior",
        )
        move = self._draft("in_invoice", self.partner)
        move._apply_ai_extracted_data(
            self._data("Asesoramiento laboral octubre", iva=10, total=200),
            force=True,
        )
        self.assertEqual(move.ocr_review_reason, "tax_mismatch")
