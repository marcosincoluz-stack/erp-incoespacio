from odoo import fields, models
from odoo.exceptions import AccessError

MAX_JOBS = 5
# Coste y margen salen de las facturas de proveedor: con menos permiso se
# calcularían solo con las que ve cada uno y el número engañaría.
FULL_COST = "account.group_account_invoice"
COST_FIELDS = ("amount_job_cost", "amount_job_margin")
JOB_FIELDS = [
    "name",
    "partner_id",
    "project_id",
    "state",
    "amount_untaxed",
    "amount_certified_origin",
    "amount_job_cost",
    "amount_job_margin",
    "amount_job_po",
    "certification_count",
]

# Entrada del catálogo (incoespacio_assistant_ai_catalog).
CATALOG = {
    "model": "sale.order",
    "help": "Obras: cada presupuesto de obra con su proyecto (sin las canceladas).",
    "domain": [("project_id", "!=", False), ("state", "!=", "cancel")],
    "order": "id desc",
    "labels": ["name", "project_id"],
    "fields": {
        "presupuesto": ("name", "Número del presupuesto."),
        "obra": ("project_id", "Nombre de la obra."),
        "cliente": ("partner_id", "El cliente."),
        "estado": ("state", "Estado del presupuesto (confirmado = obra en marcha)."),
        "fecha": ("date_order", "Fecha del presupuesto."),
        "importe": ("amount_untaxed", "Presupuesto sin IVA."),
        "certificado": (
            "amount_certified_origin",
            "Certificado y facturado a origen: es «lo facturado» de la obra.",
        ),
        "coste": (
            "amount_job_cost",
            "Facturas de proveedor imputadas a la obra.",
            FULL_COST,
        ),
        "margen": (
            "amount_job_margin",
            "Certificado menos coste. No es beneficio neto: no incluye mano de obra "
            "propia ni gastos generales. Dilo así al contestar.",
            FULL_COST,
        ),
        "comprometido": ("amount_job_po", "Pedidos de compra de la obra."),
        "certificaciones": ("certification_count", "Cuántas certificaciones tiene."),
    },
}

CERTIFICATIONS = {
    "model": "construction.certification",
    "help": "Certificaciones de obra: lo ejecutado en cada periodo, para facturarlo.",
    "domain": [],
    "order": "date desc, id desc",
    "labels": ["name"],
    "fields": {
        "numero": ("name", "Número de la certificación."),
        "obra": ("project_id", "La obra."),
        "presupuesto": ("order_id", "El presupuesto de la obra."),
        "cliente": ("partner_id", "El cliente."),
        "fecha": ("date", "Fecha de la certificación."),
        "estado": ("state", "Borrador, aprobada, facturada o cancelada."),
        "base_periodo": (
            "amount_period_untaxed",
            "Certificado en el periodo, sin IVA.",
        ),
        "retencion": ("amount_retention", "Retención de garantía del periodo."),
        "total_periodo": (
            "amount_period_total",
            "A cobrar del periodo: líquido más IVA.",
        ),
        "origen": (
            "amount_total_origin",
            "Ejecutado a origen hasta esta certificación.",
        ),
        "factura": ("invoice_id", "La factura que se hizo con ella."),
    },
}
PURCHASES = {
    "model": "purchase.order",
    "help": "Pedidos de compra a proveedores (sin los cancelados).",
    "domain": [("state", "!=", "cancel")],
    "order": "date_order desc, id desc",
    "labels": ["name"],
    "fields": {
        "numero": ("name", "Número del pedido."),
        "proveedor": ("partner_id", "El proveedor."),
        "obra": ("project_id", "La obra a la que va."),
        "fecha": ("date_order", "Fecha del pedido."),
        "estado": ("state", "Petición, confirmado (pedido), bloqueado…"),
        "base": ("amount_untaxed", "Importe sin IVA."),
        "total": ("amount_total", "Importe con IVA."),
        "facturacion": ("invoice_status", "Si el proveedor ya lo ha facturado."),
        "entrega_prevista": ("date_planned", "Cuándo se espera recibirlo."),
    },
}
PROJECTS = {
    "model": "project.project",
    "help": "Proyectos de obra (los activos): quién la lleva y fechas.",
    "domain": [],
    "order": "name",
    "labels": ["name"],
    "fields": {
        "nombre": ("name", "Nombre de la obra."),
        "jefe_de_obra": ("user_id", "Quién la lleva."),
        "cliente": ("partner_id", "El cliente."),
        "inicio": ("date_start", "Fecha de inicio."),
        "fin": ("date", "Fecha de fin prevista."),
    },
}

# Partidas de obra (sprint 2 de docs/asistente-ia-margenes.md). Los costes y
# márgenes, solo con Facturación (FULL_COST), como en las obras.
PARTIDAS = {
    "model": "sale.order.line",
    "help": (
        "Partidas de las obras (líneas del presupuesto BC3), con su avance, coste y "
        "margen. Filtra siempre por obra (o por código o descripción para comparar "
        "entre obras). Para «por capítulo», agrupa por capitulo; para un capítulo "
        "concreto, filtra por código (p. ej. «02.»). Desviación = "
        "objetivo ejecutado − coste (negativo = sobrecoste). Adelantado = gastado "
        "en partidas aún sin certificar (no entra en la desviación). Si objetivo = 0 "
        "la obra no tiene coste objetivo: no hay desviación (sale 0) y hay que "
        "decirlo; el margen real sí vale. Para explicar por qué va bien o mal una "
        "partida, investiga: precio_real frente a precio_objetivo, avance frente a "
        "coste, sus gastos (quién, cuándo, a qué precio), sus compras y lo "
        "certificado por periodo, y la misma partida (código o descripción) en "
        "otras obras. Saca tus conclusiones con cifras."
    ),
    "domain": [
        ("display_type", "=", False),
        ("order_id.project_id", "!=", False),
        ("order_id.state", "!=", "cancel"),
    ],
    "order": "order_id, sequence, id",
    "labels": ["name"],
    "requires": ["obra", "presupuesto", "codigo", "descripcion"],
    "scan": 3000,
    "fields": {
        "obra": ("assistant_project_id", "La obra."),
        "presupuesto": ("order_id", "El presupuesto de la obra."),
        "capitulo": ("assistant_chapter", "Capítulo de primer nivel (para agrupar)."),
        "subcapitulo": ("assistant_subchapter", "Subcapítulo (o capítulo, si no hay)."),
        "codigo": ("bc3_code", "Código BC3."),
        "descripcion": ("name", "Descripción de la partida."),
        "unidad": ("product_uom", "Unidad de medida."),
        "medicion": ("product_uom_qty", "Medición presupuestada."),
        "precio": ("price_unit", "Precio unitario de venta."),
        "venta": ("price_subtotal", "Importe de venta sin IVA."),
        "precio_objetivo": ("price_planned", "Precio unitario objetivo (coste)."),
        "objetivo": ("amount_planned", "Coste objetivo de la partida entera."),
        "avance": ("progress_percent", "% certificado a origen."),
        "certificado": ("amount_cert_origin", "Certificado a origen."),
        "objetivo_ejecutado": ("amount_planned_done", "Coste objetivo de lo hecho."),
        "coste": ("amount_vendor_cost", "Coste imputado (facturas).", FULL_COST),
        "desviacion": (
            "amount_cost_deviation",
            "Objetivo ejecutado − coste.",
            FULL_COST,
        ),
        "adelantado": ("amount_cost_ahead", "Coste sin avance.", FULL_COST),
        "margen": ("amount_margin", "Certificado − coste.", FULL_COST),
        "margen_pct": ("margin_percent", "% de margen real.", FULL_COST),
        "precio_real": ("price_unit_real", "Coste real por unidad.", FULL_COST),
        "comprometido": ("amount_po_cost", "Pedidos de compra pendientes.", FULL_COST),
        "coste_previsto": (
            "amount_cost_forecast",
            "Previsión a fin de obra.",
            FULL_COST,
        ),
        "margen_previsto": (
            "amount_margin_forecast",
            "Margen previsto a fin de obra.",
            FULL_COST,
        ),
    },
}

# Detalle para que la IA investigue el porqué por sí misma (sprint 3 de
# docs/asistente-ia-margenes.md): de qué facturas, pedidos y certificaciones
# salen los totales de cada partida. Mismas barreras que el resto del catálogo.
GASTOS = {
    "model": "account.move.line",
    "help": (
        "Gastos de las obras: cada línea de factura de proveedor publicada, con su "
        "partida (vacía si aún no se ha imputado). De aquí sale el coste de cada "
        "partida: sirve para ver quién facturó, cuándo, a qué precio y qué está sin "
        "imputar. Las rectificativas (tipo in_refund) restan."
    ),
    "domain": [
        ("parent_state", "=", "posted"),
        ("move_id.move_type", "in", ("in_invoice", "in_refund")),
        ("display_type", "=", "product"),
        ("move_id.project_id", "!=", False),
    ],
    "order": "date desc, id desc",
    "labels": ["name"],
    "requires": ["obra", "partida", "factura", "proveedor"],
    "scan": 5000,
    "fields": {
        "obra": ("assistant_project_id", "La obra."),
        "partida": ("construction_line_id", "Partida imputada (vacía = sin imputar)."),
        "subcapitulo": ("construction_section_id", "Capítulo o subcapítulo imputado."),
        "proveedor": ("partner_id", "El proveedor."),
        "factura": ("move_id", "La factura."),
        "tipo": ("move_type", "in_invoice = factura; in_refund = rectificativa."),
        "fecha": ("date", "Fecha contable."),
        "concepto": ("name", "Concepto de la línea."),
        "cantidad": ("quantity", "Cantidad facturada."),
        "precio": ("price_unit", "Precio unitario del proveedor.", FULL_COST),
        "importe": ("price_subtotal", "Importe sin IVA.", FULL_COST),
    },
}
COMPRAS_PARTIDAS = {
    "model": "purchase.order.line",
    "help": (
        "Líneas de los pedidos de compra confirmados de las obras, con su partida: "
        "lo pedido, lo recibido y lo ya facturado. Lo pedido y no facturado es el "
        "comprometido."
    ),
    "domain": [
        ("order_id.state", "in", ("purchase", "done")),
        ("order_id.project_id", "!=", False),
    ],
    "order": "id desc",
    "labels": ["name"],
    "requires": ["obra", "partida", "pedido", "proveedor"],
    "scan": 5000,
    "fields": {
        "obra": ("assistant_project_id", "La obra."),
        "partida": ("construction_line_id", "Partida a la que va."),
        "pedido": ("order_id", "El pedido de compra."),
        "proveedor": ("partner_id", "El proveedor."),
        "fecha": ("date_order", "Fecha del pedido."),
        "concepto": ("name", "Concepto."),
        "cantidad": ("product_qty", "Cantidad pedida."),
        "recibido": ("qty_received", "Cantidad recibida."),
        "facturado": ("qty_invoiced", "Cantidad ya facturada."),
        "precio": ("price_unit", "Precio unitario pedido.", FULL_COST),
        "importe": ("price_subtotal", "Importe pedido sin IVA.", FULL_COST),
    },
}
CERT_PARTIDAS = {
    "model": "construction.certification.line",
    "help": (
        "Lo certificado de cada partida en cada certificación (periodo): sirve para "
        "ver la evolución del avance mes a mes y compararla con los gastos."
    ),
    "domain": [
        ("display_type", "=", False),
        ("certification_id.state", "!=", "cancel"),
    ],
    "order": "id desc",
    "labels": ["name"],
    "requires": ["obra", "certificacion", "partida"],
    "scan": 5000,
    "fields": {
        "obra": ("assistant_project_id", "La obra."),
        "certificacion": ("certification_id", "La certificación."),
        "fecha": ("assistant_cert_date", "Fecha de la certificación."),
        "estado": ("assistant_cert_state", "Borrador, aprobada, facturada…"),
        "partida": ("sale_order_line_id", "La partida del presupuesto."),
        "codigo": ("code", "Código BC3."),
        "medicion_presupuesto": ("qty_budget", "Medición presupuestada."),
        "medicion_anterior": ("qty_previous", "Certificado antes de este periodo."),
        "medicion_periodo": ("qty_period", "Certificado en este periodo."),
        "medicion_origen": ("qty_origin", "Certificado a origen."),
        "avance": ("percentage_origin", "% a origen."),
        "importe_periodo": ("amount_period", "Importe certificado en el periodo."),
        "importe_origen": ("amount_origin", "Importe certificado a origen."),
    },
}

JOB_SPEC = {
    "name": "resumen_obra",
    "description": (
        "Cómo va una obra: cliente, presupuesto sin IVA, certificado a origen, "
        "coste, margen, comprometido en compras, última certificación y facturas "
        "de proveedor sin partida. Como mucho 5 obras que coincidan."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "obra": {
                "type": "string",
                "description": "Nombre de la obra, del presupuesto o del cliente.",
            }
        },
        "required": ["obra"],
    },
}


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    # Para el catálogo de IncoBot: la obra (para filtrar por su nombre) y el
    # capítulo y subcapítulo con su nombre limpio (el de pantalla lleva el
    # presupuesto y el cliente).
    assistant_project_id = fields.Many2one(
        "project.project", related="order_id.project_id", string="Obra"
    )
    assistant_subchapter = fields.Text(
        related="bc3_section_id.name", string="Subcapítulo"
    )
    assistant_chapter = fields.Char(
        compute="_compute_assistant_chapter", string="Capítulo"
    )

    def _compute_assistant_chapter(self):
        # El capítulo de primer nivel: la última sección del nivel más alto
        # (el menor bc3_level de la obra) antes de la partida.
        chapter = {}
        for order in self.order_id:
            sections = order.order_line.filtered(
                lambda l: l.display_type == "line_section"
            )
            top = min(sections.mapped("bc3_level") or [0])
            current = False
            for line in order.order_line.sorted(lambda l: (l.sequence, l.id)):
                if line.display_type == "line_section" and line.bc3_level == top:
                    current = line.name
                chapter[line.id] = current
        for line in self:
            line.assistant_chapter = chapter.get(line.id) or line.assistant_subchapter


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    assistant_project_id = fields.Many2one(
        "project.project", related="move_id.project_id", string="Obra"
    )


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    assistant_project_id = fields.Many2one(
        "project.project", related="order_id.project_id", string="Obra"
    )


class ConstructionCertificationLine(models.Model):
    _inherit = "construction.certification.line"

    assistant_project_id = fields.Many2one(
        "project.project", related="certification_id.project_id", string="Obra"
    )
    assistant_cert_date = fields.Date(related="certification_id.date")
    assistant_cert_state = fields.Selection(related="certification_id.state")


class AssistantAIQuestion(models.Model):
    _inherit = "assistant.ai.question"

    def _catalog(self):
        return dict(
            super()._catalog(),
            obras=CATALOG,
            certificaciones=CERTIFICATIONS,
            compras=PURCHASES,
            proyectos=PROJECTS,
            partidas=PARTIDAS,
            gastos=GASTOS,
            compras_partidas=COMPRAS_PARTIDAS,
            certificaciones_partidas=CERT_PARTIDAS,
        )

    def _tools(self):
        tools = super()._tools()
        tools[JOB_SPEC["name"]] = (JOB_SPEC, self._tool_job_summary)
        return tools

    def _tool_job_summary(self, env, obra=""):
        obra = str(obra or "").strip()[:100]
        if not obra:
            return {"error": "Dime qué obra."}
        domain = [
            ("project_id", "!=", False),
            ("state", "!=", "cancel"),
            "|",
            "|",
            ("name", "ilike", obra),
            ("project_id.name", "ilike", obra),
            ("partner_id.name", "ilike", obra),
        ]
        result = self._rows(
            env, "sale.order", domain, JOB_FIELDS, order="id desc", limit=MAX_JOBS
        )
        full = env.user.has_group(FULL_COST)
        for row in result["filas"]:
            row.update({f: "sin permiso" for f in COST_FIELDS if f in row and not full})
            row["_link"][2].append(row.get("project_id"))
            row["ultima_certificacion"] = self._last_cert(env, row["id"])
            row["facturas_sin_partida"] = self._bills_without_partida(env, row["id"])
        return result

    def _last_cert(self, env, order_id):
        certs = self._rows(
            env,
            "construction.certification",
            [("order_id", "=", order_id), ("state", "!=", "cancel")],
            ["name", "date", "state"],
            order="date desc, id desc",
            limit=1,
        )
        return certs["filas"][0] if certs["filas"] else None

    def _bills_without_partida(self, env, order_id):
        project = env["sale.order"].browse(order_id).project_id
        try:
            return env["account.move"].search_count(
                [
                    ("move_type", "in", ("in_invoice", "in_refund")),
                    ("state", "=", "posted"),
                    ("project_id", "=", project.id),
                    ("has_unassigned_partida", "=", True),
                ]
            )
        except AccessError:
            return "sin permiso"
