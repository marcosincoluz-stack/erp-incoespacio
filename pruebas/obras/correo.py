# -*- coding: utf-8 -*-
"""PDFs para mandar a facturas@ y probar el OCR.

Dos llevan un pedido real (P260285 y P260284) para que el OCR los enganche
a esa obra. Los otros dos no llevan codigo. CIF de emisor inventados.
"""
import os
from datetime import date

from generar import _pdf

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "correo")
RECEPTOR = "INGENIERIA CONSTRUCTIVA DEL ESPACIO S.L"
CIF = "B25962432"

DOCS = [
    {
        "file": "01-sin-obra-fontaneria.pdf",
        "proveedor": "Fontaneria Prueba SL",
        "cif": "B11111111",
        "numero": "PR-2026-101",
        "obra": "",
        "lineas": [
            ("Punto de agua de lavabo, toma y desague", 2, 85.00),
            ("Colector de PVC de 110 mm", 6, 18.50),
        ],
    },
    {
        "file": "02-obra-P260285-tabiques.pdf",
        "proveedor": "Tabiques Prueba SL",
        "cif": "B22222222",
        "numero": "PR-2026-102",
        "obra": "P260285",
        "lineas": [
            ("Tabique de pladur 13 mm. Pedido P260285", 24, 32.40),
            ("Lana mineral en tabique. Pedido P260285", 24, 6.20),
        ],
    },
    {
        "file": "03-obra-P260284-electricidad.pdf",
        "proveedor": "Electricidad Prueba SL",
        "cif": "B33333333",
        "numero": "PR-2026-103",
        "obra": "P260284",
        "lineas": [
            ("Punto de luz empotrado. Pedido P260284", 12, 42.00),
            ("Cuadro electrico de obra. Pedido P260284", 1, 310.00),
        ],
    },
    {
        "file": "04-sin-obra-pintura.pdf",
        "proveedor": "Pintura Prueba SL",
        "cif": "B44444444",
        "numero": "PR-2026-104",
        "obra": "",
        "lineas": [
            ("Pintura plastica en paramentos", 80, 7.40),
            ("Esmalte en carpinteria", 8, 22.00),
        ],
    },
]


def _doc(item):
    lineas = item["lineas"]
    base = round(sum(qty * price for _, qty, price in lineas), 2)
    iva = round(base * 0.21, 2)
    total = round(base + iva, 2)
    obra = item["obra"]
    rows = [
        (40, 800, 9, "DOCUMENTO DE PRUEBA. No es una factura real."),
        (40, 776, 14, item["proveedor"]),
        (40, 760, 10, "CIF %s" % item["cif"]),
        (360, 776, 14, "FACTURA"),
        (360, 758, 10, item["numero"]),
        (360, 744, 10, date(2026, 11, 16).strftime("%d/%m/%Y")),
        (40, 720, 11, "Cliente: %s" % RECEPTOR),
        (40, 704, 10, "CIF cliente: %s" % CIF),
        (40, 688, 10, "Presupuesto de subcontrata"),
        (
            40,
            672,
            11,
            "Pedido %s" % obra if obra else "Sin numero de pedido",
        ),
        (40, 640, 10, "Descripcion"),
        (400, 640, 10, "Cant."),
        (450, 640, 10, "Precio"),
        (510, 640, 10, "Importe"),
    ]
    y = 618
    for desc, qty, price in lineas:
        rows.append((40, y, 9, desc[:90]))
        rows.append((400, y, 9, "%.2f" % qty))
        rows.append((450, y, 9, "%.2f" % price))
        rows.append((510, y, 9, "%.2f" % round(qty * price, 2)))
        y -= 18
    y -= 12
    rows.append((400, y, 10, "Base imponible  %.2f EUR" % base))
    y -= 16
    rows.append((400, y, 10, "IVA 21%%  %.2f EUR" % iva))
    y -= 16
    rows.append((400, y, 11, "Total factura  %.2f EUR" % total))
    return _pdf([rows])


def main():
    os.makedirs(OUT, exist_ok=True)
    for item in DOCS:
        path = os.path.join(OUT, item["file"])
        with open(path, "wb") as handle:
            handle.write(_doc(item))
        print(item["file"], item["obra"] or "sin obra")


if __name__ == "__main__":
    main()
