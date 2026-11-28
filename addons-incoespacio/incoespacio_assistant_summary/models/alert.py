from datetime import timedelta

from odoo import _, api, models

_OPEN = ("new", "open")
_PARAM = "incoespacio_assistant.summary_role_ids"


class AssistantAlert(models.Model):
    _inherit = "assistant.alert"

    @api.model
    def _summary_roles(self):
        raw = self.env["ir.config_parameter"].sudo().get_param(_PARAM) or ""
        ids = [int(part) for part in raw.split(",") if part.strip().isdigit()]
        return self.env["res.users.role"].sudo().browse(ids).exists()

    @api.model
    def _summary_users(self):
        lines = self._summary_roles().line_ids.filtered(
            lambda line: (
                line.is_enabled and line.user_id.active and not line.user_id.share
            )
        )
        return lines.user_id

    def _summary(self, today):
        super()._summary(today)
        # Solo los lunes: el resumen es de totales y ya trae la semana.
        if today.weekday() != 0:
            return False
        users = self._summary_users()
        due = self.search_count([("state", "in", _OPEN)]) or self.search_count(
            self._week_domain(today)
        )
        if not users or not due:
            return False
        body, stuck = self._summary_body(today)
        for user in users:
            message = self._post_safe(user, body)
            if message:
                self._link_message(stuck, message)
        return True

    def _summary_body(self, today):
        types = self.env["assistant.alert.type"].search([("active", "=", True)])
        matters = list(self._matters(self.search([("state", "in", _OPEN)])).values())
        solved = self.search(self._week_domain(today))
        rows = []
        for atype in types:
            own = [alert for alert in matters if alert.type_id == atype]
            rows.append(
                {
                    "name": atype.name,
                    "open": len(own),
                    "fresh": sum(alert.first_seen == today for alert in own),
                    "old": sum(self._stuck_days(alert, today) > 7 for alert in own),
                }
            )
        stuck = sorted(
            matters, key=lambda alert: self._stuck_days(alert, today), reverse=True
        )
        stuck = stuck[:5]
        lines = [self._stuck_line(alert, today) for alert in stuck]
        week = self._week_rows(today, types) if today.weekday() == 0 else []
        body = self.env["ir.qweb"]._render(
            "incoespacio_assistant_summary.message_summary",
            {
                "title": _("Resumen del %s") % today.strftime("%d/%m/%Y"),
                "rows": rows,
                "stuck": lines,
                "solved": len(self._matters(solved)),
                "url": self._list_url(
                    "incoespacio_assistant_summary.action_all_alerts_checked"
                ),
                "week": week,
            },
        )
        # Los avisos de «Lo más atascado», para tacharlos luego en el mensaje.
        return body, self.browse([alert.id for alert in stuck])

    def _week_domain(self, today):
        # Lo resuelto lleva la fecha de la pasada que lo detecta. Desde el lunes
        # pasado (ya contado en su resumen) hasta hoy.
        start = today - timedelta(days=7)
        return [("resolved_date", ">", start), ("resolved_date", "<=", today)]

    def _stuck_line(self, alert, today):
        who = alert.responsible_id.name or ", ".join(
            alert.type_id.role_ids.mapped("name")
        )
        return {
            "alert_id": alert.id,
            "href": self._record_url(alert),
            "model": alert.res_model,
            "id": alert.res_id,
            "text": alert.message or "",
            "what": alert.type_id.name,
            "days": self._stuck_days(alert, today),
            "who": who or _("nadie asignado"),
            **self._split_label(alert.message),
        }

    def _week_rows(self, today, types):
        # ponytail: reabrir borra resolved_date; el lunes pasado falla si el
        # aviso volvió a abrirse. Histórico solo si eso es habitual.
        start = today - timedelta(days=7)
        alerts = self.search([])
        rows = []
        for atype in types:
            own = alerts.filtered(lambda alert, atype=atype: alert.type_id == atype)
            now_n = len(self._matters(own.filtered(lambda alert: alert.state in _OPEN)))
            then = own.filtered(lambda alert, start=start: self._was_open(alert, start))
            solved = self._matters(
                own.filtered(
                    lambda alert, start=start, today=today: self._solved(
                        alert, start, today
                    )
                )
            )
            spans = [
                (alert.resolved_date - self._since(alert)).days
                for alert in solved.values()
            ]
            rows.append(
                {
                    "name": atype.name,
                    "now": now_n,
                    "then": len(self._matters(then)),
                    "solved": len(solved),
                    "avg": round(sum(spans) / len(spans)) if spans else 0,
                }
            )
        return rows

    def _was_open(self, alert, start):
        if not alert.first_seen or alert.first_seen > start:
            return False
        return not alert.resolved_date or alert.resolved_date > start

    def _solved(self, alert, start, today):
        # Lo del lunes pasado ya contó en su resumen; lo de hoy, todavía no.
        return bool(alert.resolved_date and start < alert.resolved_date <= today)

    def _matters(self, alerts):
        found = {}
        for alert in alerts:
            key = (alert.type_id.id, alert.res_model, alert.res_id)
            if key not in found or alert.first_seen < found[key].first_seen:
                found[key] = alert
        return found

    def _stuck_days(self, alert, today):
        return self._days(alert, today)
