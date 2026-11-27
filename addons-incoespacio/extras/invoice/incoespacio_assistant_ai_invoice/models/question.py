from odoo import models

# Entrada del catálogo (incoespacio_assistant_ai_catalog).
CATALOG = {
    "model": "account.move",
    "help": (
        "Facturas de cliente y de proveedor, y sus rectificativas (tipo aparte: "
        "cuéntalas por separado). Un borrador aún no se debe ni se cobra: para "
        "deudas filtra estado = posted. Vencida: posted, pendiente > 0 y "
        "vencimiento anterior a hoy. Sin obra: obra vacía y excluida_de_obra = no."
    ),
    "domain": [
        ("move_type", "in", ("out_invoice", "out_refund", "in_invoice", "in_refund"))
    ],
    "order": "invoice_date desc, id desc",
    # Un borrador se llama «/»: se enlaza también por su referencia.
    "labels": ["name", "ref"],
    "fields": {
        "numero": ("name", "Número de la factura («/» si es borrador)."),
        "referencia": ("ref", "El número que pone el proveedor en su factura."),
        "tipo": ("move_type", "De cliente o de proveedor, o rectificativa."),
        "empresa": ("partner_id", "El cliente o el proveedor."),
        "fecha": ("invoice_date", "Fecha de la factura."),
        "vencimiento": ("invoice_date_due", "Cuándo vence el cobro o el pago."),
        "base": (
            "amount_untaxed",
            "Importe sin IVA. Las rectificativas también salen en positivo: réstalas.",
        ),
        "total": ("amount_total", "Importe con IVA."),
        "pendiente": ("amount_residual", "Lo que queda por cobrar o por pagar."),
        "estado": ("state", "Borrador, publicada o cancelada."),
        "estado_pago": ("payment_state", "Si está pagada, en parte o sin pagar."),
        "obra": ("project_id", "La obra a la que va imputada."),
        "excluida_de_obra": (
            "construction_not_job",
            "Marcada como que no va a ninguna obra (gastos generales).",
        ),
        "lineas_sin_partida": (
            "has_unassigned_partida",
            "Tiene líneas sin partida de obra asignada.",
        ),
    },
}

FULL = "account.group_account_invoice"
PAYMENTS = {
    "model": "account.payment",
    "help": "Cobros a clientes y pagos a proveedores ya registrados.",
    "domain": [],
    "order": "date desc, id desc",
    "labels": ["name"],
    "fields": {
        "numero": ("name", "Número del cobro o pago."),
        "tipo": ("payment_type", "inbound = cobro de un cliente; outbound = pago."),
        "empresa": ("partner_id", "El cliente o el proveedor."),
        "fecha": ("date", "Fecha del cobro o pago."),
        "importe": ("amount", "Importe."),
        "estado": ("state", "Borrador, publicado o cancelado."),
        "conciliado": ("is_reconciled", "Si ya está casado con su factura."),
        "concepto": ("ref", "Concepto o referencia."),
    },
}
# Sin NIF, cuentas, correo, teléfono ni dirección: solo lo necesario.
PARTNERS = {
    "model": "res.partner",
    "help": "Clientes y proveedores (empresas o personas con las que hay tratos).",
    "domain": ["|", ("customer_rank", ">", 0), ("supplier_rank", ">", 0)],
    "order": "name",
    "labels": ["name"],
    "fields": {
        "nombre": ("name", "Nombre."),
        "ciudad": ("city", "Ciudad."),
        "provincia": ("state_id", "Provincia."),
        "es_empresa": ("is_company", "Si es una empresa (si no, una persona)."),
        "veces_cliente": ("customer_rank", "Mayor que 0: es cliente."),
        "veces_proveedor": ("supplier_rank", "Mayor que 0: es proveedor."),
        "por_cobrar": ("credit", "Lo que nos debe ahora.", FULL),
        "por_pagar": ("debit", "Lo que le debemos ahora.", FULL),
    },
}


class AssistantAIQuestion(models.Model):
    _inherit = "assistant.ai.question"

    def _catalog(self):
        return dict(
            super()._catalog(), facturas=CATALOG, pagos=PAYMENTS, contactos=PARTNERS
        )
