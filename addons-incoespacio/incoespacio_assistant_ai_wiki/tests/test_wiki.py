import copy
import os
import shutil
import tempfile
from unittest.mock import patch

from odoo.tests.common import TransactionCase

BC3 = "1. Entra en **Ventas**.\n2. Pulsa **BC3 → Importar BC3**.\n"


class TestWiki(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmp = tempfile.mkdtemp()
        cls.addClassCleanup(shutil.rmtree, cls.tmp, ignore_errors=True)
        cls.root = os.path.join(cls.tmp, "wiki")
        os.makedirs(os.path.join(cls.root, "ventas"))
        os.makedirs(os.path.join(cls.root, ".git"))
        cls._write("wiki/README.md", "# Wiki\n- [BC3](ventas/importar-bc3.md)\n")
        cls._write("wiki/ventas/importar-bc3.md", BC3)
        cls._write("wiki/ventas/notas.txt", "no es md")
        cls._write("wiki/.git/oculto.md", "oculto")
        cls._write("secreto.md", "CLAVE-SECRETA")
        os.symlink(
            os.path.join(cls.tmp, "secreto.md"),
            os.path.join(cls.root, "enlace.md"),
        )
        cls.env["ir.config_parameter"].sudo().set_param(
            "incoespacio_assistant_ai.wiki_path", cls.root
        )
        user = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Ana Wiki",
                    "login": "ana.wiki",
                    "groups_id": [(6, 0, [cls.env.ref("base.group_user").id])],
                }
            )
        )
        cls.question = cls.env["assistant.ai.question"].create(
            {"user_id": user.id, "text": "¿Cómo importo un BC3?"}
        )

    @classmethod
    def _write(cls, path, text):
        with open(os.path.join(cls.tmp, path), "w", encoding="utf-8") as handle:
            handle.write(text)

    def _open(self, ruta):
        return self.question._tool_wiki_page(self.env, ruta=ruta)

    def test_only_listed_pages_open(self):
        self.assertIn("Importar BC3", self._open("ventas/importar-bc3.md")["texto"])
        self.assertIn("Importar BC3", self._open("./ventas/importar-bc3.md")["texto"])
        for ruta in (
            "../secreto.md",
            "ventas/../../secreto.md",
            "../../config/odoo.conf",
            os.path.join(self.tmp, "secreto.md"),
            "/etc/passwd",
            "enlace.md",
            "ventas/notas.txt",
            ".git/oculto.md",
            "",
            None,
        ):
            result = self._open(ruta)
            self.assertIn("error", result, ruta)
            self.assertNotIn("CLAVE-SECRETA", str(result))

    def test_system_prompt_carries_the_index(self):
        system = self.question._system()
        self.assertIn("ventas/importar-bc3.md", system)
        self.assertIn("# Wiki", system)
        self.assertNotIn("enlace.md", system)
        self.assertNotIn("oculto", system)

    def test_no_wiki_folder_means_no_tool(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "incoespacio_assistant_ai.wiki_path", os.path.join(self.tmp, "no-existe")
        )
        self.assertNotIn("wiki_pagina", self.question._tools())
        self.assertNotIn("Índice de la wiki", self.question._system())

    def test_model_reads_the_page_and_answers(self):
        sent = []
        call = {
            "functionCall": {
                "name": "wiki_pagina",
                "args": {"ruta": "ventas/importar-bc3.md"},
            }
        }
        answers = [
            {"candidates": [{"content": {"role": "model", "parts": [call]}}]},
            {
                "candidates": [
                    {"content": {"role": "model", "parts": [{"text": "Ventas → BC3"}]}}
                ]
            },
        ]

        def fake(system, contents, tools):
            sent.append(copy.deepcopy(contents))
            return answers.pop(0)

        Question = type(self.question)
        with patch.object(Question, "_gemini_call", side_effect=fake):
            text, _usage = self.question._ask()
        self.assertEqual(text, "Ventas → BC3")
        reply = sent[1][-1]["parts"][0]["functionResponse"]["response"]
        self.assertIn("Importar BC3", reply["result"]["texto"])
