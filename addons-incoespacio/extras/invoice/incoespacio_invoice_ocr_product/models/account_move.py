# -*- coding: utf-8 -*-
import re
import unicodedata

from markupsafe import Markup

from odoo import _, fields, models

# ponytail: 200 líneas recientes por contacto. Subir el tope si un proveedor
# factura más conceptos de los que caben en ese historial.
_HISTORY = 200
_MIN = 0.75
_MIN_WORDS = 2
_MARGIN = 0.15
_TOTAL_GAP = 0.02
_MONTHS = {
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "setiembre",
    "octubre",
    "noviembre",
    "diciembre",
}


def _words(text):
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(char for char in raw if not unicodedata.combining(char))
    raw = re.sub(r"\bp\d+\b", " ", raw.lower())
    raw = re.sub(r"\d+", " ", raw)
    return {
        word
        for word in re.findall(r"[a-z]+", raw)
        if len(word) >= 3 and word not in _MONTHS
    }


def _score(left, right):
    if not left or not right:
        return 0.0
    return len(left & right) / min(len(left), len(right))


def _rates(taxes):
    return {round(tax.amount, 2) for tax in taxes if tax.amount > 0}


def _expected(raw):
    if raw in (None, "", False):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value or None


class AccountMove(models.Model):
    _inherit = "account.move"

    ocr_review_reason = fields.Selection(
        selection_add=[
            ("tax_mismatch", "IVA distinto al PDF"),
            ("total_mismatch", "El total no cuadra con el PDF"),
        ],
        ondelete={"tax_mismatch": "set null", "total_mismatch": "set null"},
    )

    def _apply_ai_extracted_data(self, data, force=False):
        result = super()._apply_ai_extracted_data(data, force=force)
        if result is False:
            return result
        self._ocr_lock_prices()
        self._ocr_assign_products()
        self._ocr_check_total(data)
        return result

    def _ocr_lock_prices(self):
        lines = self.invoice_line_ids.filtered(
            lambda item: item.display_type == "product" and not item.ocr_price_unit
        )
        for line in lines:
            if line.price_unit:
                line.ocr_price_unit = line.price_unit
        return True

    def _ocr_history(self):
        self.ensure_one()
        if self.move_type in ("out_invoice", "out_refund"):
            kinds = ("out_invoice", "out_refund")
        elif self.move_type in ("in_invoice", "in_refund"):
            kinds = ("in_invoice", "in_refund")
        else:
            return self.env["account.move.line"]
        if not self.commercial_partner_id:
            return self.env["account.move.line"]
        return self.env["account.move.line"].search(
            [
                ("display_type", "=", "product"),
                ("product_id", "!=", False),
                ("parent_state", "=", "posted"),
                (
                    "move_id.commercial_partner_id",
                    "=",
                    self.commercial_partner_id.id,
                ),
                ("move_id.move_type", "in", kinds),
                ("move_id", "!=", self.id),
            ],
            order="date desc, id desc",
            limit=_HISTORY,
        )

    def _ocr_sheet_taxes(self, line):
        product = line.product_id
        if line.move_id.is_sale_document(include_receipts=True):
            taxes = product.taxes_id
        else:
            taxes = product.supplier_taxes_id
        company = line.company_id or self.env.company
        taxes = taxes.filtered(
            lambda tax: not tax.company_id or tax.company_id == company
        )
        position = line.move_id.fiscal_position_id
        if position:
            taxes = position.map_tax(taxes)
        return taxes

    def _ocr_pick_product(self, line, history):
        words = _words(line.name)
        if len(words) < _MIN_WORDS:
            winners = []
            for cand in history:
                product_id = cand.product_id.id
                if words and words == _words(cand.name) and product_id not in winners:
                    winners.append(product_id)
            if len(winners) == 1:
                return self.env["product.product"].browse(winners[0])
            return self.env["product.product"]
        best = {}
        for cand in history:
            score = _score(words, _words(cand.name))
            product_id = cand.product_id.id
            if score > best.get(product_id, 0.0):
                best[product_id] = score
        ranked = sorted(best.items(), key=lambda item: item[1], reverse=True)
        if not ranked or ranked[0][1] <= _MIN:
            return self.env["product.product"]
        if len(ranked) > 1 and ranked[0][1] - ranked[1][1] < _MARGIN:
            return self.env["product.product"]
        return self.env["product.product"].browse(ranked[0][0])

    def _ocr_apply_taxes(self, line, pdf_taxes):
        sheet = self._ocr_sheet_taxes(line)
        if not sheet:
            line.tax_ids = pdf_taxes
            return False
        line.tax_ids = sheet
        withheld = pdf_taxes.filtered(lambda tax: tax.amount < 0)
        if withheld and not sheet.filtered(lambda tax: tax.amount < 0):
            line.tax_ids |= withheld
        pdf_rates = _rates(pdf_taxes)
        sheet_rates = _rates(sheet)
        if pdf_rates and sheet_rates and pdf_rates != sheet_rates:
            return (pdf_rates, sheet_rates)
        return False

    def _ocr_assign_products(self):
        self.ensure_one()
        history = self._ocr_history()
        mismatches = []
        pending = self.invoice_line_ids.filtered(
            lambda item: item.display_type == "product" and not item.product_id
        )
        for line in pending:
            product = self._ocr_pick_product(line, history)
            if not product:
                continue
            pdf_taxes = line.tax_ids
            line.product_id = product
            mismatch = self._ocr_apply_taxes(line, pdf_taxes)
            if mismatch:
                mismatches.append((product.display_name, mismatch[0], mismatch[1]))
        if not mismatches:
            return True
        self.write({"ocr_status": "review", "ocr_review_reason": "tax_mismatch"})
        bits = [
            _("%s: el PDF dice %s%% y la ficha %s%%.")
            % (
                name,
                ", ".join("%g" % rate for rate in sorted(pdf_rates)),
                ", ".join("%g" % rate for rate in sorted(sheet_rates)),
            )
            for name, pdf_rates, sheet_rates in mismatches
        ]
        self.message_post(
            body=Markup("<div class='alert alert-warning'><b>{}</b> {}</div>").format(
                _("IVA distinto al PDF."), " ".join(bits)
            ),
            subtype_xmlid="mail.mt_note",
        )
        return True

    def _ocr_check_total(self, data):
        self.ensure_one()
        if self.ocr_status == "review":
            return True
        if not self.invoice_line_ids.filtered(
            lambda item: item.display_type == "product"
        ):
            return True
        factura = data.get("factura") or {}
        expected_total = _expected(factura.get("total"))
        expected_base = _expected(factura.get("base_imponible_total"))
        total_off = (
            expected_total is not None
            and abs(self.amount_total - expected_total) > _TOTAL_GAP
        )
        base_off = (
            expected_base is not None
            and abs(self.amount_untaxed - expected_base) > _TOTAL_GAP
        )
        if not total_off and not base_off:
            return True
        self.write({"ocr_status": "review", "ocr_review_reason": "total_mismatch"})
        self.message_post(
            body=Markup("<div class='alert alert-warning'><b>{}</b> {}</div>").format(
                _("El total no cuadra con el PDF."),
                _("Base: PDF %s / Odoo %s. Total: PDF %s / Odoo %s.")
                % (
                    expected_base if expected_base is not None else "-",
                    self.amount_untaxed,
                    expected_total if expected_total is not None else "-",
                    self.amount_total,
                ),
            ),
            subtype_xmlid="mail.mt_note",
        )
        return True
