from odoo import api, models

# Ganchos: al guardar una certificación o una obra se comprueban sus avisos
# abiertos justo antes del commit, y lo ya hecho se tacha en el chat con el
# nombre de quien guardó. Ver incoespacio_assistant_done.


def _recheck(records):
    records.env["assistant.alert"]._recheck_later(records.exists())


class ConstructionCertification(models.Model):
    _inherit = "construction.certification"

    # La obra va con la certificación: una nueva (o facturada) cambia la fecha
    # de la última certificación y lo certificado de «obras sin certificar».
    @api.model_create_multi
    def create(self, vals_list):
        certs = super().create(vals_list)
        _recheck(certs)
        _recheck(certs.order_id)
        return certs

    def write(self, vals):
        result = super().write(vals)
        _recheck(self)
        _recheck(self.order_id)
        return result

    def unlink(self):
        certs = self.browse(self.ids)
        orders = self.order_id
        result = super().unlink()
        # Borrada: el aviso ya no tiene registro y la comprobación lo resuelve.
        certs.env["assistant.alert"]._recheck_later(certs)
        _recheck(orders)
        return result


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def write(self, vals):
        result = super().write(vals)
        _recheck(self)
        return result
