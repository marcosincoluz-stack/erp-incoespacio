from odoo import fields, models

from odoo.addons.incoespacio_construction_print_options.models.print_options import (
    _chapter_label,
    _is_root_chapter,
)

_UOM_SHORT = {
    "unidades": "ud",
    "unidad": "ud",
    "units": "ud",
    "unit": "ud",
    "metro lineal": "m",
    "metros lineales": "m",
    "metros": "m",
}


class SaleOrder(models.Model):
    _inherit = "sale.order"

    print_full_text = fields.Boolean(string="Con texto completo")
    print_measures = fields.Boolean(string="Con líneas de medición")
    print_prices = fields.Boolean(string="Con precios", default=True)
    print_subtotals = fields.Boolean(string="Valorar subtotales", default=True)
    print_summary = fields.Boolean(string="Resumen por capítulos", default=True)
    print_show_code = fields.Boolean(string="Columna de código", default=True)
    print_page_break = fields.Boolean(string="Salto de página por capítulo")
    print_only_chapters = fields.Boolean(string="Solo capítulos")
    print_cover = fields.Boolean(string="Portada")
    print_signature = fields.Boolean(string="Condiciones y firma", default=True)
    print_gg_bi = fields.Boolean(string="Gastos generales y beneficio industrial")
    print_gg_pct = fields.Float(string="Gastos generales %", default=13.0)
    print_bi_pct = fields.Float(string="Beneficio industrial %", default=6.0)
    print_amount_words = fields.Boolean(string="Total en letra")

    def _print_title(self):
        self.ensure_one()
        if self.print_only_chapters:
            return "RESUMEN DE PRESUPUESTO"
        if self.print_measures and not self.print_prices:
            return "MEDICIONES"
        if self.print_measures and self.print_prices:
            return "PRESUPUESTO Y MEDICIONES"
        return "PRESUPUESTO"

    def _get_print_blocks(self):
        """Root chapters, in order, each with the lines printed under it."""
        self.ensure_one()
        blocks = []
        current = None
        for line in self._get_custom_report_lines():
            if _is_root_chapter(line):
                current = {"chapter": line, "lines": []}
                blocks.append(current)
            else:
                if current is None:
                    current = {"chapter": self.env["sale.order.line"], "lines": []}
                    blocks.append(current)
                current["lines"].append(line)
        return blocks

    def _get_print_totals(self, chapters):
        currency = self.currency_id
        material = currency.round(sum(chapter["amount"] for chapter in chapters))
        gg = currency.round(material * (self.print_gg_pct or 0.0) / 100.0)
        bi = currency.round(material * (self.print_bi_pct or 0.0) / 100.0)
        contract = currency.round(material + gg + bi)
        base = self.amount_untaxed or 0.0
        # ponytail: one effective VAT rate. Split by tax group if a quote mixes rates.
        rate = (self.amount_tax or 0.0) / base if base else 0.0
        tax = currency.round(contract * rate)
        return {
            "material": material,
            "gg": gg,
            "bi": bi,
            "contract": contract,
            "tax": tax,
            "total": currency.round(contract + tax),
            "rate": rate * 100.0,
        }

    def _print_words_amount(self, chapters):
        self.ensure_one()
        if self.print_gg_bi:
            amount = self._get_print_totals(chapters)["total"]
        elif self.print_chapter_first_id or self.print_chapter_last_id:
            amount = sum(chapter["amount"] for chapter in chapters)
        else:
            amount = self.amount_total or 0.0
        lang = self.partner_id.lang or self.env.lang
        return self.currency_id.with_context(lang=lang).amount_to_text(amount)

    def action_print_custom_pdf(self):
        self.ensure_one()
        return self.env.ref(
            "incoespacio_construction_print_layout.action_report_saleorder_custom"
        ).report_action(self)


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _print_label(self):
        self.ensure_one()
        return _chapter_label(self)

    def _print_uom(self):
        self.ensure_one()
        name = (self.product_uom.name or "").strip() if self.product_uom else ""
        return _UOM_SHORT.get(name.casefold(), name)

    def _print_bc3_text(self):
        self.ensure_one()
        return (self.bc3_text or "").strip().removesuffix("|").strip()

    def _report_measure_rows(self):
        """Skip the single quantity row Odoo stores for a hand-made line."""
        self.ensure_one()
        rows = [row for row in (self.bc3_measures or []) if isinstance(row, dict)]
        if len(rows) == 1 and not rows[0].get("comment") and not any(
            rows[0].get(key) for key in ("length", "width", "height")
        ):
            return []
        return rows
