"""Falla si un módulo propio pasa el tope de líneas de Python + JS.

No cuentan tests, migraciones, XML, CSS ni SCSS. Las excepciones están en
CONTRIBUTING.md. incoespacio_construction_certification_assistant está en el
techo actual: puede seguir así, no crecer.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from custom_modules import ROOT  # noqa: E402

CAP = 500
EXCEPTIONS = {
    "bc3_importer",
    "incoespacio_construction_certification",
    "incoespacio_invoice_ocr",
    "incoespacio_invoice_ocr_async",
    "incoespacio_invoice_ocr_obra",
    "incoespacio_invoice_ocr_ui",
    "incoespacio_reports",
    "incoespacio_theme",
}
# Techo medido. Subirlo es una decisión, no un efecto secundario.
CEILING = {
    "incoespacio_construction_certification_assistant": 503,
}
SKIP_DIRS = {"tests", "migrations", "__pycache__"}


def line_count(module_dir):
    total = 0
    for dp, dns, fns in os.walk(module_dir):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for name in fns:
            if name.endswith((".py", ".js")):
                path = os.path.join(dp, name)
                with open(path, encoding="utf-8", errors="ignore") as handle:
                    total += sum(1 for _ in handle)
    return total


def main():
    bad = []
    for dp, _dns, fns in os.walk(ROOT):
        if "__manifest__.py" not in fns:
            continue
        name = os.path.basename(dp)
        if name in EXCEPTIONS:
            continue
        count = line_count(dp)
        cap = CEILING.get(name, CAP)
        if count > cap:
            bad.append(f"{name}: {count} lineas de Python+JS (tope {cap})")
    if bad:
        print("Tope de modulo superado:")
        print("\n".join(sorted(bad)))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
