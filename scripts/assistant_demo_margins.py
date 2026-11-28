# Obras de muestra para los márgenes por partida (docs/asistente-ia-margenes.md,
# sprint 1). SOLO LOCAL, en una base cuyo nombre empiece por "demo".
#
#   docker exec -i demo_asistente_web odoo shell -d demo_asistente --no-http \
#       < scripts/assistant_demo_margins.py
#
#   Antes, copiar los BC3:  docker exec demo_asistente_web mkdir -p /tmp/pruebas
#                           docker cp pruebas/obras demo_asistente_web:/tmp/pruebas/
#
# Importa los 4 BC3 de pruebas/obras/ (copiados al contenedor en /tmp/pruebas/obras con docker cp), les pone
# coste objetivo, dos certificaciones facturadas, facturas de proveedor
# imputadas a partida y pedidos de compra, con desviaciones preparadas a
# propósito para probar el análisis:
#
#   Consulta de fisioterapia  sana: todo un poco por debajo del objetivo
#   Oficina diáfana           un capítulo (particiones y techos) se come el margen
#   Vivienda Mayor            una partida con sobrecoste, coste sin avance y
#                             una factura sin imputar a partida
#   Cafetería Plaza           recién empezada: comprometido por encima del
#                             objetivo y una partida certificada por encima
#                             del 100 %
#
# Se puede relanzar: borra lo que creó la vez anterior (prefijo MARG-).
# ruff: noqa: F821  (env lo pone odoo shell)
import base64
import os
from datetime import date

PREFIX = "MARG-"
ROOT = os.environ.get("PRUEBAS_OBRAS", "/tmp/pruebas/obras")
TODAY = date(2026, 11, 27)

if not env.cr.dbname.startswith("demo"):
    raise SystemExit("Solo en bases que empiezan por «demo». No se ha tocado nada.")

env = env(context=dict(env.context, tracking_disable=True, mail_create_nolog=True))

OBRAS = [
    # carpeta, nombre, jefe, margen objetivo %, avance cert. 1 y 2, escenario
    ("01-consulta-fisioterapia", "Consulta de fisioterapia", "demo.jefe1", 20, 0.4, 0.75, "sana"),
    ("02-oficina-diaphana", "Oficina diáfana", "demo.jefe2", 18, 0.45, 0.8, "capitulo"),
    ("03-vivienda-mayor", "Vivienda Mayor", "demo.jefe1", 22, 0.35, 0.6, "partida"),
    ("04-cafeteria-plaza", "Cafetería Plaza", "demo.jefe2", 20, 0.2, 0.0, "empezada"),
]
VENDORS = ["Saltoki Demo", "Hormigones del Norte", "Cerámicas Levante", "Fontanería Rápida"]


def partner(name):
    name = "[DEMO] " + name
    found = env["res.partner"].search([("name", "=", name)], limit=1)
    return found or env["res.partner"].create({"name": name, "is_company": True})


def material():
    product = env["product.product"].search([("default_code", "=", "DEMO-MAT")], limit=1)
    if not product:
        raise SystemExit("Falta el producto DEMO-MAT: lanza antes assistant_demo_data.py")
    # Comprometido = lo que queda por facturar de lo pedido (no de lo recibido).
    product.write({"purchase_ok": True, "purchase_method": "purchase"})
    return product


def cleanup():
    orders = env["sale.order"].search([("client_order_ref", "=like", PREFIX + "%")])
    moves = env["account.move"].search([("ref", "=like", PREFIX + "%")])
    moves |= orders.certification_ids.invoice_id
    moves.filtered(lambda m: m.state != "draft").button_draft()
    moves.with_context(force_delete=True).unlink()
    pos = env["purchase.order"].search([("partner_ref", "=like", PREFIX + "%")])
    pos.button_cancel()
    pos.unlink()
    certs = orders.certification_ids
    certs.write({"state": "draft", "invoice_id": False})
    certs.unlink()
    projects = orders.project_id
    orders.filtered(lambda o: o.state != "cancel")._action_cancel()
    orders.unlink()
    projects.unlink()
    print("Limpieza: %d obras, %d facturas, %d pedidos" % (len(orders), len(moves), len(pos)))


def import_bc3(folder, name, jefe, margin):
    with open(os.path.join(ROOT, folder, "presupuesto.bc3"), "rb") as handle:
        raw = handle.read()
    wizard = env["bc3.import.wizard"].create(
        {
            "bc3_file": base64.b64encode(raw),
            "bc3_file_name": "presupuesto.bc3",
            "partner_id": partner("Cliente obras").id,
            "create_products": False,
        }
    )
    wizard.do_action()
    order = wizard.sale_id
    order.write({"client_order_ref": PREFIX + folder, "planned_percent": margin})
    order.action_confirm()
    user = env["res.users"].search([("login", "=", jefe)], limit=1)
    order.project_id.write({"name": name, "user_id": user.id})
    return order


def partidas(order):
    return order.order_line.filtered(lambda l: not l.display_type)


def certify(order, share, when, special=None):
    """Certifica a origen «share» de cada partida (special: {línea: proporción})."""
    order.action_create_certification()
    cert = order.certification_ids.sorted("number")[-1]
    cert.date = when
    special = special or {}
    for line in cert.line_ids.filtered(lambda l: not l.display_type):
        ratio = special.get(line.sale_order_line_id, share)
        line.qty_origin = round(line.sale_order_line_id.product_uom_qty * ratio, 2)
    cert.action_confirm()
    cert.action_create_invoice()
    cert.invoice_id.invoice_date = when
    cert.invoice_id.action_post()
    return cert


def bill(order, vendor, lines, when, number, imputed=True):
    """Factura de proveedor: lines = [(partida o None, importe)]."""
    product = material()
    move = env["account.move"].create(
        {
            "move_type": "in_invoice",
            "partner_id": partner(vendor).id,
            "ref": "%s%s" % (PREFIX, number),
            "invoice_date": when,
            "project_id": order.project_id.id,
            "invoice_line_ids": [
                (
                    0,
                    0,
                    {
                        "product_id": product.id,
                        "name": line.name[:60] if line else "Material sin partida",
                        "quantity": 1,
                        "price_unit": round(amount, 2),
                        "tax_ids": [(6, 0, [])],
                        "construction_line_id": line.id if (line and imputed) else False,
                    },
                )
                for line, amount in lines
            ],
        }
    )
    move.action_post()
    return move


def purchase(order, vendor, lines, number):
    product = material()
    po = env["purchase.order"].create(
        {
            "partner_id": partner(vendor).id,
            "partner_ref": "%s%s" % (PREFIX, number),
            "project_id": order.project_id.id,
            "order_line": [
                (
                    0,
                    0,
                    {
                        "product_id": product.id,
                        "name": line.name[:60],
                        "product_qty": 1,
                        "price_unit": round(amount, 2),
                        "taxes_id": [(6, 0, [])],
                        "construction_line_id": line.id,
                    },
                )
                for line, amount in lines
            ],
        }
    )
    po.button_confirm()
    return po


def costs(order, factor, chapter_factor=None):
    """Coste por partida = objetivo ejecutado × factor (o el de su capítulo,
    por el prefijo del código BC3: «02.» es el capítulo 02)."""
    out = []
    for line in partidas(order):
        done = line.amount_planned_done
        if not done:
            continue
        f = factor
        for prefix, value in (chapter_factor or {}).items():
            if (line.bc3_code or "").startswith(prefix):
                f = value
        out.append((line, done * f))
    return out


def load(folder, name, jefe, margin, share1, share2, scenario, number):
    order = import_bc3(folder, name, jefe, margin)
    lines = partidas(order)
    special = {}
    if scenario == "empezada":
        special[lines[0]] = 1.15  # certificada por encima del 100 %
    if scenario == "partida":
        special[lines[-1]] = 0.0  # sin certificar: luego le llega coste
    certify(order, share1, date(2026, 10, 20), special)
    if share2:
        certify(order, share2, date(2026, 11, 20), special)
    order.invalidate_recordset()
    lines.invalidate_recordset()
    if scenario == "sana":
        imputed = costs(order, 0.9)
    elif scenario == "capitulo":
        imputed = costs(order, 0.95, {"02.": 1.6})  # particiones y techos
    elif scenario == "partida":
        imputed = costs(order, 0.93)
        worst = max(imputed, key=lambda pair: pair[1])
        imputed = [(l, a * 2.1 if l == worst[0] else a) for l, a in imputed]
        imputed.append((lines[-1], 1450.0))  # coste sin avance
    else:
        imputed = costs(order, 0.97)
    # Repartido entre proveedores, una factura por proveedor.
    for index, vendor in enumerate(VENDORS):
        chunk = imputed[index :: len(VENDORS)]
        if chunk:
            bill(order, vendor, chunk, date(2026, 11, 10 + index), "%s-%d" % (number, index))
    if scenario == "partida":
        bill(order, VENDORS[0], [(None, 1200.0)], date(2026, 11, 22), "%s-SIN" % number, False)
    if scenario == "empezada":
        target = max(lines, key=lambda l: l.amount_planned)
        purchase(order, VENDORS[1], [(target, target.amount_planned * 1.35)], "%s-PO" % number)
        rest = [l for l in lines if l != target][:3]
        purchase(order, VENDORS[2], [(l, l.amount_planned * 0.9) for l in rest], "%s-PO2" % number)
    return order


cleanup()
orders = env["sale.order"]
for number, row in enumerate(OBRAS, start=1):
    orders |= load(*row, number=number)
env.flush_all()
env.invalidate_all()  # los calculados se leen de nuevo, con todo ya guardado
for order in orders:
    print(
        "%s · %s · venta %.2f · objetivo %.2f · certificado %.2f · coste %.2f · "
        "sin imputar %.2f · margen real %.2f · desviación %.2f · comprometido %.2f"
        % (
            order.name,
            order.project_id.name,
            order.amount_untaxed,
            order.amount_planned,
            order.amount_certified_origin,
            order.amount_job_cost,
            order.amount_cost_unassigned,
            order.amount_margin_real,
            order.amount_cost_deviation,
            sum(partidas(order).mapped("amount_po_cost")),
        )
    )
env.cr.commit()
print("Hecho.")
