from unittest.mock import MagicMock, patch

import requests

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from odoo.addons.incoespacio_ai_core.models.ai_ocr_service import AiOcrService


class TestAiOcrService(TransactionCase):
    def setUp(self):
        super().setUp()
        params = self.env["ir.config_parameter"].sudo()
        params.set_param("incoespacio_invoice_ocr.gemini_api_key", "test-key")
        params.set_param("incoespacio_invoice_ocr.gemini_model", "gemini-2.5-flash")

    def test_retry_budget(self):
        retry = AiOcrService._new_session().get_adapter("https://").max_retries
        self.assertEqual(retry.total, 3)

    def test_strips_markdown_fence(self):
        response = MagicMock(status_code=200)
        response.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": '```json\n{"es_factura_valida": true, "factura": {"numero": "A1"}}\n```'
                            }
                        ]
                    }
                }
            ]
        }
        with patch.object(AiOcrService, "_new_session") as session:
            session.return_value.post.return_value = response
            data = AiOcrService.analyze_invoice_document(self.env, b"hola", "a.pdf")
        self.assertEqual(data["factura"]["numero"], "A1")

    def test_connection_error(self):
        with patch.object(AiOcrService, "_new_session") as session:
            session.return_value.post.side_effect = requests.exceptions.ConnectionError(
                "down"
            )
            with self.assertRaises(UserError):
                AiOcrService.analyze_invoice_document(self.env, b"hola", "a.pdf")

    def test_http_error_uses_api_message(self):
        response = MagicMock(status_code=400, text="no")
        response.json.return_value = {"error": {"message": "bad key"}}
        with patch.object(AiOcrService, "_new_session") as session:
            session.return_value.post.return_value = response
            with self.assertRaises(UserError) as caught:
                AiOcrService.analyze_invoice_document(self.env, b"hola", "a.pdf")
        self.assertIn("bad key", str(caught.exception))

    def test_unreadable_json(self):
        response = MagicMock(status_code=200)
        response.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "no es json"}]}}]
        }
        with patch.object(AiOcrService, "_new_session") as session:
            session.return_value.post.return_value = response
            with self.assertRaises(UserError):
                AiOcrService.analyze_invoice_document(self.env, b"hola", "a.pdf")

    def test_missing_key(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "incoespacio_invoice_ocr.gemini_api_key", ""
        )
        with self.assertRaises(UserError):
            AiOcrService.analyze_invoice_document(self.env, b"hola", "a.pdf")
        self.assertEqual(AiOcrService.complete_json(self.env, "hola"), {})
