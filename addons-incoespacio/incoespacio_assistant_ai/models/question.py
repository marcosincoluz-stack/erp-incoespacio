import logging
from datetime import datetime, time
from zoneinfo import ZoneInfo

from markupsafe import Markup

from odoo import _, fields, models
from odoo.tools import html2plaintext

_logger = logging.getLogger(__name__)
_MADRID = ZoneInfo("Europe/Madrid")
_UTC = ZoneInfo("UTC")

PARAM = "incoespacio_assistant_ai.%s"
DEFAULT_DAILY = 30
DEFAULT_BUDGET = 20.0
MAX_LENGTH = 1000
_COUNTED = ("pending", "done", "error")


class AssistantAIQuestion(models.Model):
    # Cola y registro a la vez: cada pregunta guarda su respuesta y su coste.
    _name = "assistant.ai.question"
    _description = "Pregunta al asistente"
    _order = "id desc"

    user_id = fields.Many2one("res.users", required=True, index=True, readonly=True)
    channel_id = fields.Many2one("discuss.channel", ondelete="cascade", readonly=True)
    reply_message_id = fields.Many2one(
        "mail.message", ondelete="set null", readonly=True
    )
    text = fields.Text(string="Pregunta", readonly=True)
    answer = fields.Text(string="Respuesta", readonly=True)
    state = fields.Selection(
        [
            ("pending", "En cola"),
            ("done", "Contestada"),
            ("refused", "Rechazada"),
            ("error", "Error"),
        ],
        default="pending",
        required=True,
        index=True,
        readonly=True,
    )
    tokens_in = fields.Integer(readonly=True)
    tokens_out = fields.Integer(readonly=True)
    cost = fields.Float(string="Coste (€)", digits=(10, 6), readonly=True)
    error = fields.Char(readonly=True)

    # ------------------------------------------------------------------ #
    # Entrada: llega un mensaje del usuario al chat del bot
    # ------------------------------------------------------------------ #
    def _receive(self, channel, message, user):
        text = html2plaintext(message.body or "").strip()
        if not text:
            return self.browse()
        refusal = self._refusal(user, text)
        vals = {"user_id": user.id, "channel_id": channel.id, "text": text[:MAX_LENGTH]}
        if refusal:
            self._post(channel, refusal)
            return self.create(dict(vals, state="refused", answer=refusal))
        question = self.create(vals)
        question.reply_message_id = self._post(channel, _("Pensando…"))
        self.env.ref("incoespacio_assistant_ai.ir_cron_assistant_ai")._trigger()
        return question

    def _refusal(self, user, text):
        if not self.env["assistant.alert"]._assistant_on():
            return _("IncoBot está desactivado ahora mismo.")
        if not self._param_bool("enabled"):
            return _("Las preguntas a la IA están desactivadas ahora mismo.")
        if len(text) > MAX_LENGTH:
            return _("La pregunta es demasiado larga: como mucho %s caracteres.") % (
                MAX_LENGTH
            )
        mine = self.search([("user_id", "=", user.id)])
        if mine.filtered(lambda q: q.state == "pending"):
            return _("Todavía estoy con tu pregunta anterior. Espera a que conteste.")
        today = self._day_start()
        used = mine.filtered(lambda q: q.state in _COUNTED and q.create_date >= today)
        if len(used) >= self._param_int("daily_limit", DEFAULT_DAILY):
            return _("Has llegado al límite de preguntas de hoy. Vuelve mañana.")
        if self._month_cost() >= self._param_float("monthly_budget", DEFAULT_BUDGET):
            return _("Se ha llegado al gasto máximo del mes. Vuelve el mes que viene.")
        return False

    # ------------------------------------------------------------------ #
    # Salida: el cron contesta lo que está en cola
    # ------------------------------------------------------------------ #
    def _cron_answer(self):
        for question in self.search([("state", "=", "pending")], order="id", limit=20):
            question._answer_one()

    def _answer_one(self):
        self.ensure_one()
        try:
            with self.env.cr.savepoint():
                text, usage = self._ask()
                self._reply(text, usage.get("links"))
                self.write(
                    {
                        "state": "done",
                        "answer": text,
                        "tokens_in": usage.get("tokens_in", 0),
                        "tokens_out": usage.get("tokens_out", 0),
                        "cost": usage.get("cost", 0.0),
                    }
                )
        except Exception as error:
            _logger.exception("Asistente IA: falló la pregunta %s", self.id)
            sorry = _("No he podido contestar ahora. Inténtalo en un rato.")
            self._reply(sorry)
            self.write({"state": "error", "answer": sorry, "error": str(error)[:200]})

    def _reply(self, text, links=None):
        body = self._linkify(self._to_html(text), links or [])
        channel = self.channel_id.sudo()
        if self.reply_message_id:
            channel._message_update_content(self.reply_message_id.sudo(), body)
        else:
            self.reply_message_id = self._post(channel, body)

    @staticmethod
    def _to_html(text):
        # Todo escapado y sin convertir URLs en enlaces (plaintext2html sí lo
        # hace): los únicos enlaces son los que pone _linkify.
        lines = (text or "").splitlines()
        return Markup("<p>%s</p>") % Markup("<br/>").join(lines)

    def _linkify(self, body, links):
        return body

    def _post(self, channel, text):
        bot = self.env.ref("incoespacio_assistant.partner_incobot_assistant")
        return channel.sudo().message_post(
            body=text if isinstance(text, Markup) else self._to_html(text),
            author_id=bot.id,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )

    # ------------------------------------------------------------------ #
    # Ajustes y cuentas
    # ------------------------------------------------------------------ #
    def _param(self, key):
        return self.env["ir.config_parameter"].sudo().get_param(PARAM % key)

    def _param_bool(self, key):
        return (self._param(key) or "").lower() in ("1", "true", "yes")

    def _param_int(self, key, default):
        try:
            return int(self._param(key) or default)
        except ValueError:
            return default

    def _param_float(self, key, default):
        try:
            return float(self._param(key) or default)
        except ValueError:
            return default

    def _day_start(self, day=None):
        day = day or self.env["assistant.alert"]._madrid_today()
        start = datetime.combine(day, time.min, tzinfo=_MADRID)
        return start.astimezone(_UTC).replace(tzinfo=None)

    def _month_cost(self):
        today = self.env["assistant.alert"]._madrid_today()
        start = self._day_start(today.replace(day=1))
        rows = self.search([("create_date", ">=", start), ("cost", ">", 0)])
        return sum(rows.mapped("cost"))
