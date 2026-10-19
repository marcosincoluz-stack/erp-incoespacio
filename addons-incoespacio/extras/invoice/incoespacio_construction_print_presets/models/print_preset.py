from odoo import _, api, fields, models
from odoo.exceptions import UserError

_PRINT_SKIP = frozenset(
    {
        "print_preset_id",
        "print_chapter_first_id",
        "print_chapter_last_id",
    }
)
# The certification dialog stores its measure sheet under this name.
_PRINT_EXTRA = frozenset({"show_measure_sheet"})
_PRINT_TYPES = frozenset({"boolean", "float", "integer", "monetary"})


def _print_option_fields(record):
    for name, field in record._fields.items():
        if name in _PRINT_SKIP:
            continue
        if not (name.startswith("print_") or name in _PRINT_EXTRA):
            continue
        if field.type in _PRINT_TYPES:
            yield name


class ConstructionPrintPreset(models.Model):
    _name = "construction.print.preset"
    _description = "Perfil de impresión"
    _order = "name"

    name = fields.Char(string="Nombre", required=True)
    res_model = fields.Selection(
        [
            ("sale.order", "Presupuesto"),
            ("construction.certification", "Certificación"),
        ],
        string="Documento",
        required=True,
    )
    values = fields.Json(string="Opciones")


class PrintPresetMixin(models.AbstractModel):
    _name = "construction.print.preset.mixin"
    _description = "Opciones de impresión con perfil"

    print_preset_id = fields.Many2one(
        "construction.print.preset", string="Perfil", ondelete="set null"
    )

    @api.onchange("print_preset_id")
    def _onchange_print_preset_id(self):
        for record in self:
            preset = record.print_preset_id
            if not preset or preset.res_model != record._name:
                continue
            stored = preset.values or {}
            for name in _print_option_fields(record):
                if name in stored:
                    record[name] = stored[name]

    def action_save_print_preset(self):
        self.ensure_one()
        preset = self.print_preset_id
        if not preset:
            raise UserError(_("Elige o crea un perfil antes de guardar."))
        if preset.res_model != self._name:
            raise UserError(_("Ese perfil es de otro documento."))
        preset.values = {name: self[name] for name in _print_option_fields(self)}
        return self.action_print_custom()


class SaleOrder(models.Model):
    _name = "sale.order"
    _inherit = ["sale.order", "construction.print.preset.mixin"]


class ConstructionCertification(models.Model):
    _name = "construction.certification"
    _inherit = ["construction.certification", "construction.print.preset.mixin"]
