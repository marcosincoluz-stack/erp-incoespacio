import uuid

from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"
    bc3 = fields.Boolean("BC3 sale order")
    bc3_file_property = fields.Char("File property")
    bc3_version_format = fields.Char("Version / Format")
    bc3_version_date = fields.Date("Version date")
    bc3_program = fields.Char("Program")
    bc3_header = fields.Char("Header")
    bc3_identifying_label = fields.Char("Identifying label")
    bc3_character_set = fields.Char("Character set")
    bc3_comment = fields.Text("Comment")
    bc3_information_type = fields.Char("Information Type")
    bc3_certification_number = fields.Char("Certification number")
    bc3_certification_date = fields.Date("Certification date")
    bc3_base_url = fields.Char("Base url")


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"
    bc3_code = fields.Char("Code")
    bc3_level = fields.Integer("Tree level", default=0)
    bc3_text = fields.Text("BC3 description")
    bc3_measures = fields.Json("BC3 measurements")

    def _with_measure_keys(self, rows):
        if not rows:
            return rows
        keyed = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            row = dict(row)
            if not row.get("key"):
                row["key"] = uuid.uuid4().hex[:8]
            keyed.append(row)
        return keyed or False

    def _ensure_measure_keys(self):
        for line in self:
            rows = line.bc3_measures or []
            if any(isinstance(row, dict) and not row.get("key") for row in rows):
                line.write({"bc3_measures": rows})

    @api.model_create_multi
    def create(self, vals_list):
        cleaned = []
        for vals in vals_list:
            vals = dict(vals)
            if vals.get("bc3_measures"):
                vals["bc3_measures"] = self._with_measure_keys(vals["bc3_measures"])
            cleaned.append(vals)
        return super().create(cleaned)

    def write(self, vals):
        vals = dict(vals)
        if (
            len(self) == 1
            and "product_uom_qty" in vals
            and "bc3_measures" not in vals
        ):
            rows = self.bc3_measures or []
            plain = len(rows) <= 1 and not (
                rows and any(rows[0].get(key) for key in ("length", "width", "height"))
            )
            if plain:
                qty = vals["product_uom_qty"] or 0
                comment = (rows[0].get("comment") if rows else "") or ""
                old_key = rows[0].get("key") if rows else None
                vals["bc3_measures"] = (
                    [
                        {
                            "comment": comment,
                            "units": qty,
                            "length": None,
                            "width": None,
                            "height": None,
                            "partial": qty,
                            "key": old_key,
                        }
                    ]
                    if qty
                    else False
                )
        if vals.get("bc3_measures"):
            vals["bc3_measures"] = self._with_measure_keys(vals["bc3_measures"])
        return super().write(vals)
