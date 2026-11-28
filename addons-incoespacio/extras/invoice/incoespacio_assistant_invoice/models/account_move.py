from odoo import api, models

# Ganchos: al guardar una factura (o una de sus líneas) se comprueban sus avisos
# abiertos justo antes del commit, y lo ya hecho se tacha en el chat con el
# nombre de quien guardó. Ver incoespacio_assistant_done.


def _recheck(moves):
    moves.env["assistant.alert"]._recheck_later(moves.exists())


class AccountMove(models.Model):
    _inherit = "account.move"

    def write(self, vals):
        result = super().write(vals)
        _recheck(self)
        return result

    def unlink(self):
        moves = self.browse(self.ids)
        result = super().unlink()
        # Borrada: el aviso ya no tiene registro y la comprobación lo resuelve.
        moves.env["assistant.alert"]._recheck_later(moves)
        return result


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    # Asignar la partida se hace en la línea, sin tocar la factura.
    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        _recheck(lines.move_id)
        return lines

    def write(self, vals):
        result = super().write(vals)
        _recheck(self.move_id)
        return result

    def unlink(self):
        moves = self.move_id
        result = super().unlink()
        _recheck(moves)
        return result
