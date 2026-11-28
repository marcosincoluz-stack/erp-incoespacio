import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)
_MADRID = ZoneInfo("Europe/Madrid")
_CAP = 10
_OPEN = ("new", "open")
# Interruptor general (Ajustes > IncoBot). Sin el parámetro, apagado: así arranca
# al instalar, y desmarcarlo en Ajustes borra el parámetro.
ON = "incoespacio_assistant.enabled"
_STATES = [
    ("new", "Nuevo"),
    ("open", "Abierto"),
    ("snoozed", "Pospuesto"),
    ("resolved", "Resuelto"),
]


class AssistantAlert(models.Model):
    _name = "assistant.alert"
    _description = "Aviso"

    type_id = fields.Many2one(
        "assistant.alert.type", required=True, ondelete="cascade", index=True
    )
    user_id = fields.Many2one(
        "res.users", required=True, ondelete="cascade", index=True
    )
    res_model = fields.Char(required=True, index=True)
    res_id = fields.Integer(required=True, index=True)
    message = fields.Char(required=True)
    responsible_id = fields.Many2one("res.users", ondelete="set null")
    state = fields.Selection(_STATES, default="new", required=True, index=True)
    first_seen = fields.Date(required=True)
    # Desde cuándo está pendiente el asunto (lo da el colector). first_seen es
    # cuándo lo vio el asistente por primera vez para este usuario.
    pending_since = fields.Date()
    last_seen = fields.Date(required=True)
    snooze_until = fields.Date()
    resolved_date = fields.Date()
    _sql_constraints = [
        ("alert_uniq", "unique(type_id,user_id,res_model,res_id)", "Duplicado"),
    ]

    def write(self, vals):
        if not self.env.su and (
            set(vals) - {"state", "snooze_until"} or vals.get("state") != "snoozed"
        ):
            raise AccessError(_("Solo puedes posponer tus avisos."))
        return super().write(vals)

    def action_open(self):
        self.ensure_one()
        return self.env[self.res_model].browse(self.res_id).get_formview_action()

    def action_snooze_day(self):
        return self._snooze(1)

    def action_snooze_week(self):
        return self._snooze(7)

    def _snooze(self, days):
        until = self._madrid_today() + timedelta(days=days)
        self.write({"state": "snoozed", "snooze_until": until})
        return True

    @api.model
    def _madrid_today(self):
        forced = self.env.context.get("assistant_today")
        if forced:
            return fields.Date.to_date(forced)
        return datetime.now(_MADRID).date()

    @api.model
    def _next_call(self):
        # ponytail: cron en UTC (OdooBot sin tz); se corre 1 h al cambiar la hora.
        now = datetime.now(_MADRID)
        target = now.replace(hour=8, minute=0, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        return target.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

    @api.model
    def _cron_run(self):
        self = self.sudo()
        today = self._madrid_today()
        if today.weekday() >= 5 or not self._assistant_on():
            return True
        seen, failed = self.browse(), set()
        types = self.env["assistant.alert.type"].search([("active", "=", True)])
        for atype in types:
            # Savepoint: un fallo SQL no aborta la transacción de los demás tipos.
            try:
                with self.env.cr.savepoint():
                    seen |= self._collect_type(atype, today)
            except Exception:
                _logger.exception("Asistente: falló el colector %s", atype.code)
                failed.add(atype.id)
        self._close_gone(seen, failed, today)
        self._notify(today)
        self._summary(today)
        return True

    def _collect_type(self, atype, today):
        seen = self.browse()
        for row in atype._collect() or []:
            # (registro, responsable, mensaje[, pendiente desde])
            record, responsible, message, *rest = row
            since = rest[0] if rest else None
            if not record or not record.exists():
                continue
            for user in atype._recipients(record, responsible):
                seen |= self._touch(
                    atype, user, record, message, responsible, today, since
                )
        return seen

    def _touch(self, atype, user, record, message, responsible, today, since=None):
        responsible = responsible[:1] if responsible else self.env["res.users"]
        alert = self.search(
            [
                ("type_id", "=", atype.id),
                ("user_id", "=", user.id),
                ("res_model", "=", record._name),
                ("res_id", "=", record.id),
            ],
            limit=1,
        )
        vals = {
            "message": message,
            "last_seen": today,
            "responsible_id": responsible.id,
        }
        if since:
            vals["pending_since"] = since
        if not alert:
            vals.update(
                type_id=atype.id,
                user_id=user.id,
                res_model=record._name,
                res_id=record.id,
                state="new",
                first_seen=today,
                pending_since=since or today,
            )
            return self.create(vals)
        if alert.state == "resolved":
            vals.update(state="new", resolved_date=False)
        alert.write(vals)
        return alert

    def _still_matching(self):
        """Los avisos de self cuya regla se sigue cumpliendo ahora mismo.

        Solo lee: la usan la pantalla y la IA (que corre en solo lectura).
        sudo: las reglas son las del aviso diario, que corre como administrador;
        el resultado solo sirve para quitar avisos de self, nunca añade nada.
        Si una regla falla, sus avisos se quedan: mejor de más que esconderlos.
        """
        keep = self.browse()
        for atype in self.type_id:
            own = self.filtered(lambda alert, atype=atype: alert.type_id == atype)
            try:
                with self.env.cr.savepoint(flush=False):
                    rows = atype.sudo()._collect() or []
            except Exception:
                _logger.exception("Asistente: falló el colector %s", atype.code)
                keep |= own
                continue
            live = {(row[0]._name, row[0].id) for row in rows if row and row[0]}
            keep |= own.filtered(
                lambda alert, live=live: (alert.res_model, alert.res_id) in live
            )
        return keep

    def _resolve_fixed(self):
        # Lo ya arreglado se resuelve para todos los que tenían ese aviso.
        gone = self - self._still_matching()
        today = self._madrid_today()
        for alert in gone.sudo():
            same = self.sudo().search(
                [
                    ("type_id", "=", alert.type_id.id),
                    ("res_model", "=", alert.res_model),
                    ("res_id", "=", alert.res_id),
                    ("state", "in", _OPEN),
                ]
            )
            same.write({"state": "resolved", "resolved_date": today})
        return gone

    @api.model
    def _open_checked(self, xmlid, domain):
        """Abre una lista de avisos tras comprobar en el momento los abiertos.

        Sin crons: si alguien ha hecho la tarea durante el día, al mirar la
        lista ya no le sale.
        """
        self.search(domain + [("state", "in", _OPEN)])._resolve_fixed()
        return self.env["ir.actions.act_window"]._for_xml_id(xmlid)

    @api.model
    def action_open_my_alerts(self):
        return self._open_checked(
            "incoespacio_assistant.action_my_alerts", [("user_id", "=", self.env.uid)]
        )

    def _close_gone(self, seen, failed, today):
        domain = [("id", "not in", seen.ids)]
        if failed:
            domain.append(("type_id", "not in", list(failed)))
        gone = self.search(domain + [("state", "in", _OPEN)])
        due = self.search(
            domain + [("state", "=", "snoozed"), ("snooze_until", "<=", today)]
        )
        (gone | due).write({"state": "resolved", "resolved_date": today})
        back = seen.filtered(
            lambda alert: (
                alert.state == "snoozed"
                and alert.snooze_until
                and alert.snooze_until <= today
            )
        )
        # Lo que vuelve de posponer cuenta como novedad: hay que recordarlo.
        back.write({"state": "new", "snooze_until": False})
        return True

    def _notify(self, today):
        by_user = {}
        for alert in self.search([("state", "in", _OPEN)]):
            user = alert.user_id
            muted = alert.type_id in user.assistant_muted_type_ids
            if not user.active or user.share or muted:
                continue
            by_user.setdefault(user, self.browse())
            by_user[user] |= alert
        # Solo se escribe si hay algo nuevo; los lunes, repaso completo.
        monday = today.weekday() == 0
        sent = self.browse()
        for user, alerts in by_user.items():
            if not monday and "new" not in alerts.mapped("state"):
                continue
            message = self._post_safe(user, self._body(user, alerts, today))
            if message:
                sent |= alerts
                self._link_message(self._shown(alerts, today), message)
        sent.filtered(lambda alert: alert.state == "new").write({"state": "open"})
        return True

    def _chunks(self, alerts, today):
        for atype in alerts.type_id.sorted("sequence"):
            chunk = alerts.filtered(lambda alert, atype=atype: alert.type_id == atype)
            # Nuevos primero; dentro, lo más antiguo arriba.
            yield (
                atype,
                chunk.sorted(
                    key=lambda alert: (alert.first_seen != today, self._since(alert))
                ),
            )

    def _shown(self, alerts, today):
        # Los que salen con su línea en el mensaje (como mucho _CAP por tipo).
        shown = self.browse()
        for _atype, chunk in self._chunks(alerts, today):
            shown |= chunk[:_CAP]
        return shown

    def _link_message(self, alerts, message):
        # Lo usa incoespacio_assistant_done para tachar luego en el mensaje.
        return True

    def _body(self, user, alerts, today):
        groups = []
        for atype, chunk in self._chunks(alerts, today):
            groups.append(
                {
                    "name": atype.name,
                    "hint": atype.hint or "",
                    "count": len(chunk),
                    "lines": [self._line(alert, today) for alert in chunk[:_CAP]],
                    "extra": max(len(chunk) - _CAP, 0),
                }
            )
        return self.env["ir.qweb"]._render(
            "incoespacio_assistant.message_alerts",
            {
                "hello": self._hello(user, alerts, today),
                "groups": groups,
                "url": self._list_url("incoespacio_assistant.action_my_alerts_checked"),
                "footer": self._chat_footer(),
            },
        )

    def _assistant_on(self):
        return self.env["ir.config_parameter"].sudo().get_param(ON) == "True"

    def _chat_footer(self):
        return _("Este chat solo envía avisos; no responde mensajes.")

    def _hello(self, user, alerts, today):
        total = len(alerts)
        word = _("aviso") if total == 1 else _("avisos")
        if today.weekday() == 0:
            return _("Buenos días, %s. Repaso de los lunes: tienes %s %s.") % (
                user.name,
                total,
                word,
            )
        new = len(alerts.filtered(lambda alert: alert.state == "new"))
        news = _("1 nuevo") if new == 1 else _("%s nuevos") % new
        return _("Buenos días, %s. Tienes %s %s (%s).") % (user.name, total, word, news)

    def _since(self, alert):
        return alert.pending_since or alert.first_seen

    def _days(self, alert, today):
        return max((today - self._since(alert)).days, 0)

    def _line(self, alert, today):
        days = self._days(alert, today)
        suffix = ""
        if days == 1:
            suffix = _(" · pendiente desde hace 1 día")
        elif days > 1:
            suffix = _(" · pendiente desde hace %s días") % days
        return {
            "alert_id": alert.id,
            "fresh": alert.first_seen == today,
            "href": self._record_url(alert),
            "model": alert.res_model,
            "id": alert.res_id,
            "text": alert.message or "",
            "suffix": suffix,
            **self._split_label(alert.message),
        }

    @staticmethod
    def _split_label(message):
        # «CERT/2026/0040 · Nave · 13.151,70 €»: el enlace (la chapa) va solo en
        # el número o nombre del registro; el resto queda como texto normal.
        label, sep, rest = (message or "").partition(" · ")
        return {"label": label, "rest": sep + rest}

    def _record_url(self, alert):
        return "/web#id=%s&model=%s&view_type=form" % (alert.res_id, alert.res_model)

    def _list_url(self, xmlid):
        action = self.env.ref(xmlid)
        return "/web#action=%s&model=assistant.alert&view_type=list" % action.id

    def _post_safe(self, user, body):
        # Devuelve el mensaje publicado, o False si no se pudo.
        try:
            with self.env.cr.savepoint():
                return self._post(user, body)
        except Exception:
            _logger.exception("Asistente: no se pudo escribir a %s", user.login)
            return False

    def _post(self, user, body):
        bot = self.env.ref("incoespacio_assistant.partner_incobot_assistant")
        # Como el usuario: channel_get no mete a OdooBot de tercero.
        channel = self.env["discuss.channel"].with_user(user).channel_get([bot.id])
        return channel.sudo().message_post(
            body=body,
            author_id=bot.id,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )

    def _summary(self, today):
        # Lo amplía incoespacio_assistant_summary.
        return False
