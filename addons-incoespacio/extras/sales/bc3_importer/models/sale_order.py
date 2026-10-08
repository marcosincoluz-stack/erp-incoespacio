from odoo import fields, models


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
                vals["bc3_measures"] = (
                    [
                        {
                            "comment": comment,
                            "units": qty,
                            "length": None,
                            "width": None,
                            "height": None,
                            "partial": qty,
                        }
                    ]
                    if qty
                    else False
                )
        return super().write(vals)
