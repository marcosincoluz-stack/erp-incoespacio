# Datos de muestra del asistente IncoBot. SOLO LOCAL, en una base desechable.
#
# Se lanza con `odoo shell` sobre una base cuyo nombre empiece por "demo"
# (por ejemplo demo_asistente). Se niega a correr sobre cualquier otra.
#
#   Crear (o recrear) los datos y lanzar el cron de hoy:
#     docker exec -i incoespacio_web odoo shell -d demo_asistente \
#       --db-filter=demo_asistente --no-http --workers=0 --http-port=8097 \
#       < scripts/assistant_demo_data.py
#
#   Simular una semana (cron día a día, corrigiendo facturas entre medias):
#     docker exec -i -e DEMO_MODE=simular incoespacio_web odoo shell ... < scripts/...
#
# Crea 5 usuarios (1 dirección, 2 administración, 2 jefes de obra) con roles,
# 10 obras con sus certificaciones, unos 80 gastos de un mes normal, facturas
# de cliente y los casos que vigila el asistente.
# Las contraseñas se generan al crear cada usuario la primera vez y se imprimen.
# ruff: noqa: F821  (env lo pone odoo shell)
import os
import random
import secrets
from datetime import timedelta

from odoo import fields

PREFIX = "DEMO-"
MODE = os.environ.get("DEMO_MODE", "crear")
rng = random.Random(20261126)

if not env.cr.dbname.startswith("demo"):
    raise SystemExit(
        f"Base «{env.cr.dbname}»: este script solo corre en bases que empiezan por "
        "«demo». No se ha tocado nada."
    )

env = env(context=dict(env.context, tracking_disable=True, mail_create_nolog=True))
Alert = env["assistant.alert"]


def ref(xmlid):
    return env.ref(xmlid, raise_if_not_found=False)


def madrid_today():
    return Alert._madrid_today()


# --------------------------------------------------------------------------- #
# Limpieza de la pasada anterior
# --------------------------------------------------------------------------- #
def cleanup():
    moves = env["account.move"].search([("ref", "=like", PREFIX + "%")])
    moves.filtered(lambda m: m.state != "draft").button_draft()
    moves.with_context(force_delete=True).unlink()
    orders = env["sale.order"].search([("client_order_ref", "=like", PREFIX + "%")])
    projects = orders.project_id
    certs = env["construction.certification"].search([("order_id", "in", orders.ids)])
    certs.write({"state": "draft"})
    certs.unlink()
    orders.filtered(lambda o: o.state != "cancel")._action_cancel()
    orders.unlink()
    projects.unlink()
    Alert.search([]).unlink()
    bot = ref("incoespacio_assistant.partner_incobot_assistant")
    env["discuss.channel"].search(
        [("channel_type", "=", "chat"), ("channel_member_ids.partner_id", "=", bot.id)]
    ).unlink()


# --------------------------------------------------------------------------- #
# Roles y usuarios
# --------------------------------------------------------------------------- #
ROLE_GROUPS = {
    "Administración": [
        "base.group_user",
        "account.group_account_manager",
        "purchase.group_purchase_user",
        "sales_team.group_sale_salesman_all_leads",
        "project.group_project_user",
    ],
    "Jefe de obra": [
        "base.group_user",
        "account.group_account_invoice",
        "purchase.group_purchase_user",
        # Ve todas las obras, no solo las suyas como comercial.
        "sales_team.group_sale_salesman_all_leads",
        "project.group_project_user",
    ],
    "Dirección": [
        "base.group_user",
        "account.group_account_manager",
        "purchase.group_purchase_manager",
        "sales_team.group_sale_manager",
        "project.group_project_manager",
    ],
}

USERS = [
    ("demo.direccion", "Elena Dirección", "Dirección"),
    ("demo.admin1", "Ana Administración", "Administración"),
    ("demo.admin2", "Luis Administración", "Administración"),
    ("demo.jefe1", "Pedro Jefe de obra", "Jefe de obra"),
    ("demo.jefe2", "Marta Jefe de obra", "Jefe de obra"),
]


def ensure_roles():
    roles = {}
    for name, xmlids in ROLE_GROUPS.items():
        role = env["res.users.role"].search([("name", "=", "Demo · " + name)], limit=1)
        groups = [g.id for g in map(ref, xmlids) if g]
        vals = {"name": "Demo · " + name, "implied_ids": [(6, 0, groups)]}
        role = role.write(vals) and role if role else env["res.users.role"].create(vals)
        roles[name] = role
    return roles


def ensure_users(roles):
    users, passwords = {}, {}
    for login, name, role_name in USERS:
        user = (
            env["res.users"]
            .with_context(active_test=False)
            .search([("login", "=", login)], limit=1)
        )
        vals = {
            "name": name,
            "login": login,
            "email": f"{login}@demo.invalid",
            "active": True,
            "notification_type": "inbox",
            "tz": "Europe/Madrid",
            "assistant_muted_type_ids": [(5, 0, 0)],
        }
        # La contraseña solo se pone al crear: repetir la demo no la cambia.
        password = None
        if user:
            user.write(vals)
        else:
            password = secrets.token_urlsafe(9)
            vals["password"] = password
            user = env["res.users"].with_context(no_reset_password=True).create(vals)
        role = roles[role_name]
        env["res.users.role.line"].search([("user_id", "=", user.id)]).unlink()
        env["res.users.role.line"].create({"role_id": role.id, "user_id": user.id})
        user.set_groups_from_roles(force=True)
        users[login] = user
        passwords[login] = password
    return users, passwords


# Qué roles reciben cada aviso, además del responsable si el tipo lo pide.
ALERT_ROLES = {
    "bill_draft_no_obra": ["Administración"],
    "bill_no_partida": ["Administración"],
    "bill_ocr_failed": ["Administración"],
    "bill_draft_empty": ["Administración"],
    "invoice_overdue": ["Administración", "Dirección"],
    "cert_to_invoice": ["Administración"],
    "cert_draft": [],
    "obra_no_cert": [],
}


def configure_assistant(roles):
    for code, names in ALERT_ROLES.items():
        atype = env["assistant.alert.type"].search([("code", "=", code)], limit=1)
        if atype:
            # Sin fecha de corte: en la demo las facturas tienen fechas pasadas.
            ids = [roles[name].id for name in names]
            atype.write(
                {"role_ids": [(6, 0, ids)], "active": True, "since_date": False}
            )
    env["ir.config_parameter"].set_param(
        "incoespacio_assistant.summary_role_ids", str(roles["Dirección"].id)
    )
    # En la demo, las preguntas a la IA encendidas (en producción se encienden a mano).
    env["ir.config_parameter"].set_param("incoespacio_assistant_ai.enabled", "True")


# --------------------------------------------------------------------------- #
# Obras, proveedores y facturas
# --------------------------------------------------------------------------- #
OBRAS = [
    "Calle Mayor 12",
    "Reforma oficinas Gran Vía",
    "Nave industrial Polígono Sur",
    "Chalet Los Pinos",
    "Local comercial Plaza España",
    "Rehabilitación fachada Avenida",
    "Viviendas Residencial El Prado",
    "Clínica dental Centro",
    "Restaurante La Marina",
    "Colegio Santa Ana (ampliación)",
]
PARTIDAS = ["Demoliciones", "Albañilería", "Fontanería", "Electricidad", "Pintura"]
PROVEEDORES = [
    "Saltoki Demo",
    "Hormigones del Norte",
    "Ferretería López",
    "Pinturas Prueba",
    "Fontanería Rápida",
    "Electricidad Voltio",
    "Maderas El Roble",
    "Cerámicas Levante",
    "Alquiler Andamios Sur",
    "Transportes Gómez",
    "Áridos y Gravas",
    "Climatización Frío",
    "Vidrios Cristal",
    "Aislamientos Térmicos",
]


def ensure_partner(name):
    name = "[DEMO] " + name
    partner = env["res.partner"].search([("name", "=", name)], limit=1)
    return partner or env["res.partner"].create({"name": name, "is_company": True})


def ensure_products():
    expense = env["account.account"].search(
        [("account_type", "=", "expense"), ("company_id", "=", env.company.id)], limit=1
    )
    income = env["account.account"].search(
        [("account_type", "=", "income"), ("company_id", "=", env.company.id)], limit=1
    )
    Product = env["product.product"]
    material = Product.search([("default_code", "=", "DEMO-MAT")], limit=1)
    partida = Product.search([("default_code", "=", "DEMO-PART")], limit=1)
    common = {
        "type": "service",
        "taxes_id": [(5, 0, 0)],
        "supplier_taxes_id": [(5, 0, 0)],
        "property_account_expense_id": expense.id,
        "property_account_income_id": income.id,
    }
    if not material:
        material = Product.create(
            dict(common, name="Material de obra (demo)", default_code="DEMO-MAT")
        )
    if not partida:
        partida = Product.create(
            dict(common, name="Partida de obra (demo)", default_code="DEMO-PART")
        )
    return material, partida


def create_obras(users, partida_product):
    jefes = [users["demo.jefe1"], users["demo.jefe2"]]
    client = ensure_partner("Cliente obras")
    obras = []
    for index, name in enumerate(OBRAS):
        jefe = jefes[index % 2]
        order = env["sale.order"].create(
            {
                "partner_id": client.id,
                "client_order_ref": f"{PREFIX}{index + 1:02d} {name}",
                "bc3": True,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": partida_product.id,
                            "name": partida,
                            "product_uom_qty": 1,
                            "price_unit": rng.randint(2000, 15000),
                        },
                    )
                    for partida in PARTIDAS
                ],
            }
        )
        # Confirma el jefe: la obra nace con él de responsable.
        order.with_user(jefe).sudo().action_confirm()
        order.project_id.name = name
        obras.append(order)
    # Una obra sin responsable (las antiguas, antes del cambio).
    obras[-1].project_id.user_id = False
    return obras


def certify(order, days, state, share=0.3):
    order.action_create_certification()
    cert = order.certification_ids.sorted("id")[-1]
    for line in cert.line_ids.filtered(lambda line: not line.display_type):
        line.qty_origin = line.qty_previous + line.qty_budget * share
    cert.write({"date": madrid_today() - timedelta(days=days), "state": state})
    env.cr.execute(
        "UPDATE construction_certification SET create_date = %s WHERE id = %s",
        (
            fields.Datetime.to_string(fields.Datetime.now() - timedelta(days=days)),
            cert.id,
        ),
    )
    cert.invalidate_recordset(["create_date"])
    return cert


def create_certifications(obras):
    # Todas empezaron hace 2-4 meses y casi todas certifican cada mes.
    for index, order in enumerate(obras):
        order.date_order = fields.Datetime.now() - timedelta(days=60 + index * 3)
    cases = {}
    for order in obras[:5] + obras[7:]:
        certify(order, 33, "invoiced")
        certify(order, 6, "invoiced")
    cases["certificación aprobada sin facturar"] = certify(obras[0], 5, "confirmed")
    cases["certificación aprobada ayer"] = certify(obras[1], 1, "confirmed")
    cases["certificación en borrador 10 días"] = certify(obras[2], 10, "draft")
    cases["certificación en borrador 2 días"] = certify(obras[3], 2, "draft")
    # Obras paradas: una nunca certificada y otra con la última hace 40 días.
    certify(obras[6], 40, "invoiced")
    cases["obra sin certificar"] = obras[5]
    cases["obra parada 40 días"] = obras[6]
    return cases


def create_sales(client, product):
    cases = {}
    for days, label in (
        (25, "vencida 25 días"),
        (6, "vencida 6 días"),
        (-10, "aún no vence"),
    ):
        day = fields.Date.today() - timedelta(days=days)
        move = env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": client.id,
                "ref": f"{PREFIX}V{days + 100}",
                "invoice_date": min(day, fields.Date.today()),
                "invoice_date_due": day,
                "invoice_payment_term_id": False,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "price_unit": 4800 + days * 10,
                            "tax_ids": [(6, 0, [])],
                        },
                    )
                ],
            }
        )
        move.action_post()
        cases[f"cliente {label}"] = move
    return cases


def backdate(moves, days):
    moment = fields.Datetime.now() - timedelta(days=days, hours=rng.randint(0, 6))
    env.cr.execute(
        "UPDATE account_move SET create_date = %s WHERE id IN %s",
        (fields.Datetime.to_string(moment), tuple(moves.ids)),
    )
    moves.invalidate_recordset(["create_date"])


def bill(partner, product, amount, days, number, **extra):
    vals = {
        "move_type": extra.pop("move_type", "in_invoice"),
        "partner_id": partner.id if partner else False,
        "ref": f"{PREFIX}{number}",
        "invoice_date": fields.Date.today() - timedelta(days=days),
        "invoice_line_ids": [
            (
                0,
                0,
                {
                    "product_id": product.id,
                    "name": product.name,
                    "quantity": 1,
                    "price_unit": amount,
                    "tax_ids": [(6, 0, [])],
                },
            )
        ]
        if amount
        else [],
    }
    creator = extra.pop("creator", None)
    vals.update(extra)
    Move = env["account.move"]
    move = (Move.with_user(creator).sudo() if creator else Move).create(vals)
    backdate(move, days)
    return move


def post(moves, poster):
    for move in moves:
        move.with_user(poster).sudo().action_post()


def create_bills(users, obras, material):
    poster = users["demo.admin1"]
    partners = [ensure_partner(name) for name in PROVEEDORES]
    count = 0

    def next_number():
        nonlocal count
        count += 1
        return f"{count:03d}"

    # Mes normal: unas 7 facturas bien imputadas por obra.
    for order in obras:
        lines = order.order_line.filtered(lambda line: not line.display_type)
        for _ in range(7):
            move = bill(
                rng.choice(partners),
                material,
                rng.randint(80, 4000),
                rng.randint(1, 30),
                next_number(),
                project_id=order.project_id.id,
            )
            move.invoice_line_ids.construction_line_id = rng.choice(lines)
            post(move, poster)

    cases = {}
    # Borradores sin obra, escalonados (avisan desde 4 días).
    for days in (1, 3, 4, 5, 10, 30):
        cases[f"sin obra {days} días"] = bill(
            rng.choice(partners), material, rng.randint(100, 3000), days, next_number()
        )
    # Sin obra, pero el OCR sugiere una: avisa también al jefe.
    cases["sin obra, OCR sugiere obra"] = bill(
        rng.choice(partners),
        material,
        1840,
        6,
        next_number(),
        ocr_obra_suggested_id=obras[0].project_id.id,
    )
    # Marcada «No es de obra»: no avisa.
    cases["no es de obra"] = bill(
        rng.choice(partners), material, 95, 8, next_number(), construction_not_job=True
    )
    # Borradores vacíos (sin proveedor y a 0 €), creados por administración.
    cases["vacío 3 días"] = bill(
        None, material, 0, 3, next_number(), creator=users["demo.admin2"]
    )
    cases["vacío 1 día"] = bill(
        None, material, 0, 1, next_number(), creator=users["demo.admin1"]
    )
    # Publicadas con obra y líneas sin partida (una de la obra sin jefe).
    for days, order in ((2, obras[1]), (7, obras[2]), (15, obras[-1])):
        move = bill(
            rng.choice(partners),
            material,
            rng.randint(200, 2500),
            days,
            next_number(),
            project_id=order.project_id.id,
        )
        post(move, poster)
        cases[f"sin partida {days} días"] = move
    # OCR con error: en borrador avisa; ya publicada, no.
    cases["OCR error borrador"] = bill(
        rng.choice(partners),
        material,
        0,
        2,
        next_number(),
        ocr_status="error",
        ocr_error_message="No se ha podido leer el total de la factura.",
    )
    published = bill(
        rng.choice(partners),
        material,
        310,
        6,
        next_number(),
        project_id=obras[3].project_id.id,
        ocr_status="error",
        ocr_error_message="Error antiguo, corregida a mano.",
    )
    published.invoice_line_ids.construction_line_id = obras[3].order_line[:1]
    post(published, poster)
    cases["OCR error ya publicada"] = published
    # Abonos.
    cases["abono sin obra"] = bill(
        rng.choice(partners), material, 150, 5, next_number(), move_type="in_refund"
    )
    refund = bill(
        rng.choice(partners),
        material,
        220,
        9,
        next_number(),
        move_type="in_refund",
        project_id=obras[4].project_id.id,
    )
    post(refund, poster)
    cases["abono sin partida"] = refund
    return count, cases


# --------------------------------------------------------------------------- #
# Informe
# --------------------------------------------------------------------------- #
def report(users, title):
    print(f"\n=== {title} ===")
    for login, user in users.items():
        alerts = Alert.search([("user_id", "=", user.id)])
        open_alerts = alerts.filtered(lambda a: a.state in ("new", "open"))
        by_type = {}
        for alert in open_alerts:
            by_type[alert.type_id.name] = by_type.get(alert.type_id.name, 0) + 1
        detail = ", ".join(f"{name}: {n}" for name, n in sorted(by_type.items())) or "—"
        other = len(alerts) - len(open_alerts)
        print(
            f"  {user.name:<22} {len(open_alerts):>3} abiertos ({detail}); otros {other}"
        )


def run_cron(day):
    Alert.with_context(assistant_today=fields.Date.to_string(day))._cron_run()


# --------------------------------------------------------------------------- #
# Modos
# --------------------------------------------------------------------------- #
def crear():
    cleanup()
    roles = ensure_roles()
    users, passwords = ensure_users(roles)
    configure_assistant(roles)
    material, partida = ensure_products()
    obras = create_obras(users, partida)
    count, cases = create_bills(users, obras, material)
    cases.update(create_certifications(obras))
    cases.update(create_sales(ensure_partner("Cliente obras"), partida))
    today = madrid_today()
    while today.weekday() >= 5:  # el cron no corre en fin de semana
        today -= timedelta(days=1)
    run_cron(today)
    env.cr.commit()
    print(f"\nObras: {len(obras)}  ·  Facturas y abonos de proveedor: {count}")
    print("Casos del asistente:")
    for name, record in cases.items():
        label = getattr(record, "ref", None) or record.display_name
        print(f"  - {name:<36} {label}  ({record.state})")
    report(users, f"Avisos tras el cron del {today}")
    print("\nUsuarios (la contraseña solo se crea la primera vez):")
    for login, password in passwords.items():
        print(f"  {login:<16} {password or '(sin cambios)'}")


def simular():
    users = {
        login: env["res.users"].search([("login", "=", login)], limit=1)
        for login, _name, _role in USERS
    }
    if not all(users.values()):
        raise SystemExit("Primero crea los datos (sin DEMO_MODE).")
    poster = users["demo.admin1"]
    day = madrid_today()
    days = []
    while len(days) < 6:
        day += timedelta(days=1)
        if day.weekday() < 5:
            days.append(day)
    for number, current in enumerate(days, start=1):
        run_cron(current)
        report(users, f"Día {number}: {current} ({current.strftime('%A')})")
        if number == 1:
            # Entre el día 1 y el 2: se corrigen cosas y alguien pospone.
            draft = env["account.move"].search(
                [
                    ("ref", "=like", PREFIX + "%"),
                    ("state", "=", "draft"),
                    ("partner_id", "!=", False),
                    ("project_id", "=", False),
                    ("construction_not_job", "=", False),
                    ("ocr_status", "!=", "error"),
                ],
                order="create_date asc",
                limit=1,
            )
            obra = env["sale.order"].search(
                [("client_order_ref", "=like", PREFIX + "%")], limit=1
            )
            if draft and obra:
                draft.project_id = obra.project_id
                draft.invoice_line_ids.construction_line_id = obra.order_line[:1]
                post(draft, poster)
                print(f"  → {draft.ref}: asignada a obra y publicada (debe resolverse)")
            no_partida = env["account.move"].search(
                [
                    ("ref", "=like", PREFIX + "%"),
                    ("state", "=", "posted"),
                    ("has_unassigned_partida", "=", True),
                ],
                limit=1,
            )
            if no_partida:
                lines = (
                    no_partida.project_id
                    and env["sale.order"]
                    .search([("project_id", "=", no_partida.project_id.id)], limit=1)
                    .order_line[:1]
                )
                no_partida.invoice_line_ids.construction_line_id = lines
                print(f"  → {no_partida.ref}: partida asignada (debe resolverse)")
            alert = Alert.search(
                [("user_id", "=", poster.id), ("state", "in", ("new", "open"))], limit=1
            )
            if alert:
                alert.with_user(poster).with_context(
                    assistant_today=fields.Date.to_string(current)
                ).action_snooze_day()
                print(f"  → {poster.name} pospone 1 día: {alert.message}")
    env.cr.commit()
    print("\nAbre el chat de IncoBot Asistente con cada usuario para ver los mensajes.")


if MODE == "simular":
    simular()
else:
    crear()
