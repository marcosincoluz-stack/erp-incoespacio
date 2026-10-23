from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    # No se llama certification_id: ese nombre es el enlace guardado de
    # incoespacio_construction_certification_pending_bills (factura de
    # proveedor cubierta). Este es el camino inverso, factura de cliente.
    invoice_certification_id = fields.Many2one(
        "construction.certification",
        string="Certificación",
        compute="_compute_invoice_certification_id",
    )

    # ponytail: no se almacena; se calcula al abrir la factura. Si una factura
    # llegara a tener varias certificaciones, se muestra la última.
    def _compute_invoice_certification_id(self):
        certs = self.env["construction.certification"].search(
            [("invoice_id", "in", self.ids)]
        )
        by_move = {cert.invoice_id.id: cert for cert in certs}
        for move in self:
            move.invoice_certification_id = by_move.get(move.id, False)
