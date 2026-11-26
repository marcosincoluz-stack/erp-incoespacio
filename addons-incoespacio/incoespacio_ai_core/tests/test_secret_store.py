import os
from unittest.mock import MagicMock, patch

import requests
from cryptography.fernet import Fernet

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger

from odoo.addons.incoespacio_ai_core.models.ai_ocr_service import AiOcrService
from odoo.addons.incoespacio_ai_core.models.secret_store import (
    GEMINI_KEY,
    MASTER_ENV,
    PREFIX,
)

_LOG = "odoo.addons.incoespacio_ai_core.models.secret_store"
_KEY = "AIzaSy-clave-de-prueba-a1B2"


class TestSecretStore(TransactionCase):
    def setUp(self):
        super().setUp()
        self.master = Fernet.generate_key().decode()
        self.params = self.env["ir.config_parameter"].sudo()
        self.secrets = self.env["incoespacio.secret"]
        self.params.set_param(GEMINI_KEY, "")

    def _env(self, master):
        return patch.dict(os.environ, {MASTER_ENV: master or ""})

    def test_roundtrip_stores_only_ciphertext(self):
        with self._env(self.master), mute_logger(_LOG):
            self.secrets._set_secret(GEMINI_KEY, _KEY)
            raw = self.params.get_param(GEMINI_KEY)
            self.assertTrue(raw.startswith(PREFIX))
            self.assertNotIn(_KEY, raw)
            self.assertEqual(self.secrets._get_secret(GEMINI_KEY), _KEY)
            status = self.secrets._secret_status(GEMINI_KEY)
        self.assertIn("…a1B2", status)
        self.assertNotIn(_KEY, status)

    def test_without_master_nothing_is_stored_in_clear(self):
        with self._env(None), self.assertRaises(UserError):
            self.secrets._set_secret(GEMINI_KEY, _KEY)
        self.assertFalse(self.params.get_param(GEMINI_KEY))

    def test_wrong_master_fails_cleanly(self):
        with self._env(self.master), mute_logger(_LOG):
            self.secrets._set_secret(GEMINI_KEY, _KEY)
        other = Fernet.generate_key().decode()
        with self._env(other), mute_logger(_LOG):
            self.assertEqual(self.secrets._get_secret(GEMINI_KEY), "")
            self.assertIn("vuelve a pegar", self.secrets._secret_status(GEMINI_KEY))

    def test_legacy_plain_key_is_encrypted_when_master_exists(self):
        self.params.set_param(GEMINI_KEY, _KEY)
        with self._env(None), mute_logger(_LOG):
            self.assertEqual(self.secrets._get_secret(GEMINI_KEY), _KEY)
            self.assertIn("En claro", self.secrets._secret_status(GEMINI_KEY))
        self.assertEqual(self.params.get_param(GEMINI_KEY), _KEY)
        with self._env(self.master), mute_logger(_LOG):
            self.assertEqual(self.secrets._get_secret(GEMINI_KEY), _KEY)
            self.assertTrue(self.params.get_param(GEMINI_KEY).startswith(PREFIX))
            self.assertEqual(self.secrets._get_secret(GEMINI_KEY), _KEY)

    def test_clear_removes_key_and_hints(self):
        with self._env(self.master), mute_logger(_LOG):
            self.secrets._set_secret(GEMINI_KEY, _KEY)
            self.secrets._clear_secret(GEMINI_KEY)
        for suffix in ("", ".hint", ".updated"):
            self.assertFalse(self.params.get_param(GEMINI_KEY + suffix))

    def test_settings_never_return_the_key(self):
        with self._env(self.master), mute_logger(_LOG):
            settings = self.env["res.config.settings"].create({"gemini_api_key": _KEY})
            settings.execute()
            self.assertEqual(self.secrets._get_secret(GEMINI_KEY), _KEY)
            fresh = self.env["res.config.settings"].create({})
            self.assertFalse(fresh.gemini_api_key)
            self.assertIn("…a1B2", fresh.gemini_api_key_status)
            values = fresh.read(["gemini_api_key", "gemini_api_key_status"])[0]
            # Lo que recibe la pantalla al abrir Ajustes (registro nuevo).
            shown = self.env["res.config.settings"].onchange(
                {}, [], {"gemini_api_key_status": {}, "gemini_api_key": {}}
            )["value"]
        self.assertNotIn(_KEY, str(values))
        self.assertIn("…a1B2", shown["gemini_api_key_status"])
        self.assertFalse(shown.get("gemini_api_key"))

    def test_secrets_are_not_callable_from_rpc(self):
        # Los métodos con _ no se pueden llamar desde el navegador.
        for name in ("_get_secret", "_set_secret", "_clear_secret", "_secret_status"):
            self.assertTrue(name.startswith("_"))
            self.assertFalse(hasattr(self.secrets, name.lstrip("_")))

    def test_gemini_errors_do_not_leak_the_key(self):
        with self._env(self.master), mute_logger(_LOG):
            self.secrets._set_secret(GEMINI_KEY, _KEY)
            with patch.object(AiOcrService, "_new_session") as session:
                session.return_value.post.side_effect = (
                    requests.exceptions.ConnectionError("down")
                )
                with (
                    self.assertRaises(UserError) as caught,
                    mute_logger(
                        "odoo.addons.incoespacio_ai_core.models.ai_ocr_service"
                    ),
                ):
                    AiOcrService.analyze_invoice_document(self.env, b"hola", "a.pdf")
                sent = session.return_value.post.call_args
            self.assertNotIn(_KEY, str(caught.exception))
            self.assertEqual(sent.kwargs["headers"]["x-goog-api-key"], _KEY)
            self.assertNotIn(_KEY, sent.args[0])
            response = MagicMock(status_code=400, text="no")
            response.json.return_value = {"error": {"message": "API key not valid"}}
            with patch.object(AiOcrService, "_new_session") as session:
                session.return_value.post.return_value = response
                with self.assertRaises(UserError) as caught:
                    AiOcrService.analyze_invoice_document(self.env, b"hola", "a.pdf")
        self.assertNotIn(_KEY, str(caught.exception))
