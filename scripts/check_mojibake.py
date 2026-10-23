"""Falla si un fichero de addons-incoespacio tiene acentos doble-codificados.

Marca típica de regrabar UTF-8 con PowerShell 5.1 (Set-Content / Get-Content):
á se ve como Ã¡, y los guiones como â€.
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "addons-incoespacio"))
SKIP = {os.path.join(ROOT, "extras", "sales", "bc3_importer")}
EXTS = {".py", ".xml", ".js", ".scss", ".css", ".csv", ".md", ".rst", ".html", ".po", ".pot"}
NEEDLES = ("\u00c3", "\u00e2\u20ac")


def main():
    hits = []
    for dp, dns, fns in os.walk(ROOT):
        if any(dp == skip or dp.startswith(skip + os.sep) for skip in SKIP):
            dns[:] = []
            continue
        if "__pycache__" in dp:
            continue
        for name in fns:
            if os.path.splitext(name)[1] not in EXTS:
                continue
            path = os.path.join(dp, name)
            text = open(path, encoding="utf-8", errors="ignore").read()
            if any(needle in text for needle in NEEDLES):
                hits.append(os.path.relpath(path, ROOT))
    if hits:
        print("Mojibake UTF-8 (no regrabar con PowerShell 5.1):")
        print("\n".join(sorted(hits)))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
