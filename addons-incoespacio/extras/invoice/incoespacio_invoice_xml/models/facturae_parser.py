# -*- coding: utf-8 -*-
"""Facturae 3.2.x -> el mismo dict que devuelve Gemini.

ponytail: un lote con varias Invoice solo devuelve la primera y el recuento
en facturas_en_lote. Partir el lote cuando aparezca uno real.
"""

from lxml import etree

_REFUND = {"OR", "CR"}


def _local(node):
    return etree.QName(node).localname if node is not None else ""


def _child(node, name):
    if node is None:
        return None
    for item in node:
        if _local(item) == name:
            return item
    return None


def _first(node, name):
    if node is None:
        return None
    for item in node.iter():
        if _local(item) == name:
            return item
    return None


def _text(node, *path):
    cur = node
    for name in path:
        cur = _child(cur, name)
        if cur is None:
            return ""
    return (cur.text or "").strip()


def _amount(value):
    raw = (value or "").strip().replace(",", ".")
    if not raw:
        return 0.0
    try:
        return float(raw)
    except ValueError:
        return 0.0


def _is_facturae(root):
    if _local(root) == "Facturae":
        return True
    ns = etree.QName(root).namespace or ""
    return "facturae" in ns.lower()


def _nodes(node, name):
    if node is None:
        return []
    return [item for item in node if _local(item) == name]


def _party(root, role):
    parties = _child(root, "Parties")
    if parties is None:
        parties = root
    found = _child(parties, role)
    if found is not None:
        return found
    return _first(root, role)


def _party_name(party):
    legal = _text(party, "LegalEntity", "CorporateName")
    if legal:
        return legal
    given = _text(party, "Individual", "Name")
    surname = _text(party, "Individual", "FirstSurname")
    return " ".join(part for part in (given, surname) if part)


def _party_dict(party):
    return {
        "cif": _text(party, "TaxIdentification", "TaxIdentificationNumber"),
        "nombre": _party_name(party),
    }


def _line(node):
    tax = _child(_child(node, "TaxesOutputs"), "Tax")
    qty = _amount(_text(node, "Quantity")) or 1.0
    price = _amount(_text(node, "UnitPriceWithoutTax"))
    gross = _amount(_text(node, "GrossAmount")) or round(qty * price, 2)
    return {
        "descripcion": _text(node, "ItemDescription") or "Servicio / Mercancía",
        "cantidad": qty,
        "precio_unitario": price,
        "porcentaje_iva": _amount(_text(tax, "TaxRate")),
        "subtotal": gross,
    }


def _invoice(node):
    header = _child(node, "InvoiceHeader")
    issue = _child(node, "InvoiceIssueData")
    totals = _child(node, "InvoiceTotals")
    number = _text(header, "InvoiceNumber")
    series = _text(header, "InvoiceSeriesCode")
    withheld = _child(_child(node, "TaxesWithheld"), "Tax")
    lines = [_line(line) for line in _nodes(_child(node, "Items"), "InvoiceLine")]
    payment = _child(_child(node, "PaymentDetails"), "Installment")
    iban = _text(payment, "AccountToBeCredited", "IBAN") or _text(
        payment, "AccountToBeDebited", "IBAN"
    )
    return {
        "numero": "%s-%s" % (series, number) if series and number else number,
        "fecha_emision": _text(issue, "IssueDate"),
        "fecha_vencimiento": _text(payment, "InstallmentDueDate") or None,
        "moneda": _text(issue, "InvoiceCurrencyCode") or "EUR",
        "base_imponible_total": _amount(_text(totals, "TotalGrossAmountBeforeTaxes")),
        "iva_total": _amount(_text(totals, "TotalTaxOutputs")),
        "retencion_irpf_porcentaje": _amount(_text(withheld, "TaxRate")),
        "retencion_irpf_cuota": _amount(_text(totals, "TotalTaxesWithheld")),
        "total": _amount(_text(totals, "InvoiceTotal")),
        "clase": _text(header, "InvoiceClass"),
        "lineas": lines,
        "iban": "".join((iban or "").split()).upper(),
    }


def parse(xml_bytes):
    """Devuelve el dict de Gemini o None si no es un Facturae legible."""
    if isinstance(xml_bytes, str):
        xml_bytes = xml_bytes.encode()
    if not xml_bytes:
        return None
    try:
        root = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError:
        return None
    if not _is_facturae(root):
        return None
    nodes = _nodes(_child(root, "Invoices"), "Invoice")
    if not nodes:
        return None
    invoice = _invoice(nodes[0])
    if not invoice["numero"]:
        return None
    return {
        "es_factura_valida": True,
        "es_multifactura": False,
        "es_rectificativa": invoice["clase"] in _REFUND,
        "facturas_en_lote": len(nodes),
        "motivo": "",
        "emisor": _party_dict(_party(root, "SellerParty")),
        "receptor": _party_dict(_party(root, "BuyerParty")),
        "factura": {
            key: invoice[key]
            for key in (
                "numero",
                "fecha_emision",
                "fecha_vencimiento",
                "moneda",
                "base_imponible_total",
                "iva_total",
                "retencion_irpf_porcentaje",
                "retencion_irpf_cuota",
                "total",
            )
        },
        "lineas": invoice["lineas"],
        "pago": {"iban": invoice["iban"], "banco": ""},
    }
