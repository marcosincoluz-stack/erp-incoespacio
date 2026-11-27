from odoo import fields, models
from odoo.exceptions import AccessError

_PREFIX = "_collect_"


class AssistantAlertType(models.Model):
    _name = "assistant.alert.type"
    _description = "Tipo de aviso"
    _order = "sequence, id"

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    collector = fields.Char(required=True, string="Colector")
    threshold_days = fields.Integer(string="Días de margen", default=0)
    since_date = fields.Date(
        string="Solo registros desde",
        help="Vacío: todo el histórico. Cada colector decide qué fecha mira.",
    )
    role_ids = fields.Many2many("res.users.role", string="Roles que lo reciben")
    notify_responsible = fields.Boolean(string="También al responsable del registro")
    hint = fields.Char(string="Qué hacer", help="Se muestra bajo el título en el chat.")

    _sql_constraints = [
        ("code_uniq", "unique(code)", "El código de aviso ya existe."),
    ]

    def _collect(self):
        self.ensure_one()
        name = self.collector or ""
        method = getattr(self, name, None) if name.startswith(_PREFIX) else None
        if not callable(method):
            raise RuntimeError(self.code)
        return method()

    def _recipients(self, record, responsible):
        self.ensure_one()
        users = self.role_ids.line_ids.filtered(
            lambda line: (
                line.is_enabled and line.user_id.active and not line.user_id.share
            )
        ).user_id
        responsible = responsible[:1] if responsible else self.env["res.users"]
        if (
            self.notify_responsible
            and responsible
            and responsible.active
            and not responsible.share
        ):
            users |= responsible
        # ponytail: un check por usuario; lote si un tipo llega a cientos.
        allowed = self.env["res.users"]
        for user in users:
            if self._can_read(user, record):
                allowed |= user
        return allowed

    def _can_read(self, user, record):
        try:
            record.with_user(user).check_access_rights("read")
            record.with_user(user).check_access_rule("read")
        except AccessError:
            return False
        return True
