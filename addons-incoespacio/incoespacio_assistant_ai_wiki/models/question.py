import logging
import os

from odoo import models

_logger = logging.getLogger(__name__)

PATH_PARAM = "incoespacio_assistant_ai.wiki_path"
DEFAULT_PATH = "/mnt/wiki"
INDEX = "README.md"
MAX_PAGE = 20000
MAX_INDEX = 8000

SPEC = {
    "name": "wiki_pagina",
    "description": (
        "Abre una página de la wiki de uso del ERP y devuelve su texto. "
        "La ruta tiene que ser exactamente una de la lista de páginas."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "ruta": {
                "type": "string",
                "description": "Ruta de la lista, por ejemplo ventas/importar-bc3.md",
            }
        },
        "required": ["ruta"],
    },
}


def wiki_pages(root):
    """Las páginas .md de dentro de la wiki, con su ruta desde la raíz.

    Es la lista cerrada que puede abrir la IA: se salta enlaces simbólicos y
    todo lo que, una vez resuelto, quede fuera de la carpeta.
    """
    if not root or not os.path.isdir(root):
        return {}
    real_root = os.path.realpath(root)
    pages = {}
    for folder, dirs, files in os.walk(real_root, followlinks=False):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in files:
            full = os.path.join(folder, name)
            if not name.endswith(".md") or os.path.islink(full):
                continue
            real = os.path.realpath(full)
            if os.path.commonpath([real_root, real]) != real_root:
                continue
            pages[os.path.relpath(real, real_root).replace(os.sep, "/")] = real
    return pages


def read_page(path, limit):
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read(limit)


class AssistantAIQuestion(models.Model):
    _inherit = "assistant.ai.question"

    def _wiki_root(self):
        return (self._param("wiki_path") or DEFAULT_PATH).strip()

    def _tools(self):
        tools = super()._tools()
        if wiki_pages(self._wiki_root()):
            tools[SPEC["name"]] = (SPEC, self._tool_wiki_page)
        return tools

    def _tool_wiki_page(self, env, ruta=""):
        ruta = str(ruta or "").strip().removeprefix("./")
        pages = wiki_pages(self._wiki_root())
        if ruta not in pages:
            return {"error": "Esa página no existe. Usa una ruta de la lista."}
        return {"ruta": ruta, "texto": read_page(pages[ruta], MAX_PAGE)}

    def _system(self):
        system = super()._system()
        pages = wiki_pages(self._wiki_root())
        if not pages:
            return system
        index = read_page(pages[INDEX], MAX_INDEX) if INDEX in pages else ""
        listing = "\n".join("- " + path for path in sorted(pages))
        return (
            system
            + "\nWiki de uso. Para «cómo se hace algo», abre la página que toque "
            "con wiki_pagina antes de contestar y explícalo con sus pasos.\n"
            + "\nÍndice de la wiki:\n"
            + index
            + "\n\nPáginas que puedes abrir:\n"
            + listing
            + "\n"
        )
