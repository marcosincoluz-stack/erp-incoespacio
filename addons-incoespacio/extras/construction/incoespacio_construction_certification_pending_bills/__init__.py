from . import models


def post_init_hook(env):
    latest = {}
    for cert in env["construction.certification"].search([("state", "=", "invoiced")]):
        prev = latest.get(cert.order_id.id)
        if not prev or cert.number > prev.number:
            latest[cert.order_id.id] = cert
    Move = env["account.move"]
    for cert in latest.values():
        if not cert.project_id:
            continue
        Move.search(
            [
                ("project_id", "=", cert.project_id.id),
                ("company_id", "=", cert.company_id.id),
                ("move_type", "in", ("in_invoice", "in_refund")),
                ("state", "=", "posted"),
                ("certification_id", "=", False),
                ("invoice_date", "<", cert.date),
            ]
        ).write({"certification_id": cert.id})
