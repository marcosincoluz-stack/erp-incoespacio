# Batería de preguntas reales contra Gemini en la demo (sprint 4 del catálogo,
# docs/asistente-ia-catalogo.md), con la respuesta esperada calculada aquí
# mismo. Todo en una transacción deshecha. Gasta unos 0,04 € de Gemini.
#
#   docker exec -i demo_asistente_web odoo shell -d demo_asistente --no-http #       < scripts/assistant_eval.py
import json, re, unicodedata
from datetime import date

E = env(su=True)
AM, SO, CC = E["account.move"], E["sale.order"], E["construction.certification"]
today = date(2026, 11, 27)
elena = E["res.users"].search([("login", "=", "demo.direccion")])
pedro = E["res.users"].search([("login", "=", "demo.jefe1")])
obras = SO.search([("project_id", "!=", False), ("state", "!=", "cancel")])
posted_bills = AM.search([("move_type", "=", "in_invoice"), ("state", "=", "posted")])
unpaid_bills = posted_bills.filtered(lambda m: m.payment_state in ("not_paid", "partial"))
year_bills = posted_bills.filtered(lambda m: m.invoice_date and m.invoice_date.year == 2026)
by_vendor = {}
for m in year_bills:
    by_vendor[m.partner_id.name] = by_vendor.get(m.partner_id.name, 0) + m.amount_untaxed
nov = posted_bills.filtered(lambda m: m.invoice_date and m.invoice_date.month == 11)
sales = AM.search([("move_type", "=", "out_invoice"), ("state", "=", "posted")])
overdue = sales.filtered(lambda m: m.payment_state in ("not_paid", "partial") and m.invoice_date_due < today)
prado = obras.filtered(lambda o: o.project_id.name == "Viviendas Residencial El Prado")
nave = obras.filtered(lambda o: o.project_id.name == "Nave industrial Polígono Sur")

pav = E["sale.order.line"].search([("order_id.project_id.name", "=", "Vivienda Mayor"), ("name", "ilike", "Pavimento porcelanico")], limit=1)
pavimento_vendor = (pav.vendor_cost_line_ids[:1].partner_id.name or "?").replace("[DEMO] ", "")
N = lambda *v: ("num", list(v))
T = lambda *v: ("txt", list(v))
NO = lambda *v: ("not", list(v))
CASES = [
    (elena, "¿Qué obra tiene más beneficio?", [T(max(obras, key=lambda o: o.amount_job_margin).project_id.name)]),
    (elena, "Dime la obra que más se ha facturado", [N(max(obras.mapped("amount_certified_origin")))]),
    (elena, "¿Qué obras están perdiendo dinero?", [T(*[o.project_id.name for o in obras if o.amount_job_margin < 0])]),
    (elena, "¿Cuántas obras tenemos en marcha?", [N(len(obras.filtered(lambda o: o.state == "sale")))]),
    (elena, "¿Cuál es el margen de Viviendas Residencial El Prado?", [N(prado.amount_job_margin)]),
    (elena, "¿Cuánto hemos gastado en la obra Nave industrial Polígono Sur?", [N(nave.amount_job_cost)]),
    (elena, "¿Qué obras lleva Marta?", [T(*[o.project_id.name for o in obras if o.project_id.user_id.name == "Marta Jefe de obra"])]),
    (elena, "¿Cuántas facturas de proveedor tenemos sin pagar?", [N(len(unpaid_bills))]),
    (elena, "¿Cuánto debemos en total a proveedores?", [N(sum(unpaid_bills.mapped("amount_residual")))]),
    (elena, "¿Qué proveedor nos ha facturado más este año?", [T(max(by_vendor, key=by_vendor.get))]),
    (elena, "¿Cuántas facturas de proveedor hay en borrador?", [N(AM.search_count([("move_type", "=", "in_invoice"), ("state", "=", "draft")]))]),
    (elena, "¿Cuál es la factura de proveedor más cara de noviembre?", [T(max(nov, key=lambda m: m.amount_total).name)]),
    (elena, "¿Qué facturas de cliente están vencidas?", [T(*overdue.mapped("name"))]),
    (elena, "¿Cuánto nos debe el cliente [DEMO] Cliente obras?", [N(sum(sales.filtered(lambda m: m.payment_state != "paid").mapped("amount_residual")))]),
    (elena, "¿Cuánto hemos facturado a clientes este año, sin IVA?", [N(sum(sales.mapped("amount_untaxed")))]),
    (elena, "¿Cuántas certificaciones hay en borrador?", [N(CC.search_count([("state", "=", "draft")]))]),
    (elena, "¿Cuál es la última certificación de Calle Mayor 12?", [T(CC.search([("project_id.name", "=", "Calle Mayor 12")], order="date desc, id desc", limit=1).name)]),
    (elena, "¿Hay pedidos de compra de la obra Calle Mayor 12?", [NO("PO0")]),
    (elena, "¿Cuántas facturas de proveedor no tienen obra?", [N(AM.search_count([("move_type", "=", "in_invoice"), ("state", "!=", "cancel"), ("project_id", "=", False), ("construction_not_job", "=", False)]))]),
    (pedro, "¿Qué avisos tengo?", [T(*[a.message.split(" · ")[0] for a in E["assistant.alert"].search([("user_id", "=", pedro.id), ("state", "in", ("new", "open"))])._still_matching()])]),
    (elena, "¿Cómo importo un BC3 de Presto?", [T("BC3"), NO("no lo puedo consultar")]),
    # «¿Por qué?» sobre las obras de scripts/assistant_demo_margins.py: la IA tiene
    # que encontrar sola cada causa preparada.
    (elena, "¿Por qué va mal la obra Vivienda Mayor?", [T("pavimento"), N(1450), N(1200)]),
    (elena, "¿Por qué el pavimento de Vivienda Mayor tiene sobrecoste?", [T(pavimento_vendor)]),
    (elena, "¿Por qué la Oficina diáfana tiene tan poco margen?", [T("particiones")]),
    (elena, "¿Qué riesgo ves en la Cafetería Plaza?", [T("comprometid")]),
    (elena, "¿Por qué va mal Albañilería en Clínica dental Centro?", [T("objetivo"), N(4490)]),
]

def plain(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if not unicodedata.combining(c))

def numbers(text):
    out = []
    for raw in re.findall(r"-?\d[\d.]*(?:,\d+)?", text):
        s = raw.replace(".", "").replace(",", ".") if ("," in raw or raw.count(".") > 1 or re.search(r"\.\d{3}$", raw)) else raw
        try:
            out.append(float(s))
        except ValueError:
            pass
    return out

def check(answer, checks):
    nums, low = numbers(answer), plain(answer)
    for kind, values in checks:
        for v in values:
            if kind == "num" and not any(abs(n - v) < 0.02 for n in nums):
                return False
            if kind == "txt" and plain(str(v)) not in low:
                return False
            if kind == "not" and plain(str(v)) in low:
                return False
    return True

Q = type(E["assistant.ai.question"])
orig = Q._run_tool
calls = []
def spy(self, tools, name, args):
    r = orig(self, tools, name, args)
    calls.append((name, "error" in r))
    return r
Q._run_tool = spy

ok = total_cost = total_in = 0
for user, text, checks in CASES:
    calls.clear()
    q = E["assistant.ai.question"].create({"user_id": user.id, "text": text})
    try:
        answer, usage = q._ask()
    except Exception as error:
        answer, usage = "FALLO: %s" % error, {"tokens_in": 0, "tokens_out": 0, "cost": 0}
    good = check(answer, checks)
    ok += good
    total_cost += usage["cost"]; total_in += usage["tokens_in"]
    tools = ",".join("%s%s" % (n, "!" if e else "") for n, e in calls)
    print("%s | %s | %s | %d/%d | %.4f €" % ("OK " if good else "MAL", text, tools, usage["tokens_in"], usage["tokens_out"], usage["cost"]))
    if not good:
        print("     esperado:", checks)
        print("     respuesta:", answer.replace("\n", " ")[:400])
print("RESULTADO %d/%d | coste total %.4f € | media %.4f € | entrada media %d tokens" % (ok, len(CASES), total_cost, total_cost / len(CASES), total_in / len(CASES)))
env.cr.rollback()
