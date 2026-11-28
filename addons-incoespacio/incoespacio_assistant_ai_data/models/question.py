import re

from markupsafe import Markup, escape

from odoo import fields, models
from odoo.exceptions import AccessError

MAX_ROWS = 20
# Nunca se consultan, aunque una herramienta lo pidiera por error (2.13).
BLOCKED_MODELS = {
    "ir.config_parameter",
    "incoespacio.secret",
    "res.users",
    "res.users.apikeys",
    "res.partner.bank",
    "mail.message",
    "mail.mail",
    "discuss.channel",
    "assistant.ai.question",
}
BLOCKED_WORDS = ("password", "token", "secret", "api_key", "iban", "acc_number")
BLOCKED_FIELDS = {"vat", "bank_ids", "message_ids", "signature"}

LINK = '<a href="/web#id={id}&amp;model={model}&amp;view_type=form" data-oe-model="{model}" data-oe-id="{id}" class="o_incobot_link{extra}">{text}</a>'
MIN_LABEL = 3

ALERTS_SPEC = {
    "name": "mis_avisos",
    "description": "Los avisos abiertos de quien pregunta: tipo, texto y días.",
    "parameters": {"type": "object", "properties": {}},
}


def blocked_field(name):
    return name in BLOCKED_FIELDS or any(word in name for word in BLOCKED_WORDS)


class AssistantAIQuestion(models.Model):
    _inherit = "assistant.ai.question"

    # Enlaces que dieron las herramientas en esta respuesta: si la siguiente se
    # contesta con lo ya hablado, sin consultar, se reutilizan.
    link_data = fields.Json(readonly=True)

    def _rows(
        self, env, model, domain, fieldnames, order=None, limit=MAX_ROWS, cap=MAX_ROWS
    ):
        """Lectura para las herramientas: como el usuario, nunca con sudo.

        Aplica sus permisos y reglas de registro, quita los campos que no puede
        ver y los de la lista negra, y devuelve como mucho MAX_ROWS filas, con
        los nombres en vez de ids y las etiquetas de las selecciones. «cap» lo
        sube el catálogo (50 filas).
        """
        if env.su or model in BLOCKED_MODELS:
            raise AccessError("Consulta no permitida.")
        records = env[model]
        records.check_access_rights("read")
        readable = set(records.check_field_access_rights("read", None))
        names = [
            name
            for name in fieldnames
            if name in readable and name in records._fields and not blocked_field(name)
        ]
        found = records.search(domain, order=order, limit=min(limit, cap))
        rows = []
        for record in found:
            row = {name: self._cell(record, name, env) for name in names}
            # «_link» no llega a Gemini: _take_links lo quita y lo guarda.
            row.update(id=record.id, _link=[model, record.id, [row.get("name")]])
            rows.append(row)
        return {"total": records.search_count(domain), "filas": rows}

    def _take_links(self, reply):
        links = super()._take_links(reply)
        stack = [reply]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                link = item.pop("_link", None)
                if link:
                    links.append(link)
                stack.extend(item.values())
            elif isinstance(item, list):
                stack.extend(item)
        return links

    def _linkify(self, body, links):
        """Enlaza en la respuesta los nombres de los registros consultados.

        Los enlaces los construye este código con lo que han devuelto las
        herramientas (que ya respetan los permisos), nunca la IA. El texto de
        la IA llega escapado; solo se envuelve en <a> lo que coincide.
        """
        targets = {}
        for model, rec_id, labels, *alert in links:
            # Los avisos llevan su id: así se tachan aquí cuando se hagan.
            extra = " o_incobot_alert_%d" % int(alert[0]) if alert else ""
            for label in labels:
                label = str(label or "").strip()
                if len(label) >= MIN_LABEL and label != "sin permiso":
                    targets.setdefault(str(escape(label)), (model, int(rec_id), extra))
        if not targets:
            return body
        names = sorted(targets, key=len, reverse=True)
        # Las etiquetas y entidades HTML se saltan: un registro llamado «amp» o
        # «br/» no puede romper el mensaje metiendo un enlace dentro de ellas.
        pattern = re.compile(
            "|".join(re.escape(name) for name in names) + r"|(<[^>]*>|&#?\w+;)"
        )

        def link(match):
            if match.group(1):
                return match.group(0)
            model, rec_id, extra = targets[match.group(0)]
            return LINK.format(
                id=rec_id, model=escape(model), extra=extra, text=match.group(0)
            )

        return Markup(pattern.sub(link, str(body)))

    def _recent_links(self):
        # Las 3 últimas respuestas de esta persona en este chat: registros que ya
        # consultó con sus permisos (al abrirlos, Odoo los vuelve a comprobar).
        previous = self.sudo().search(
            [
                ("user_id", "=", self.user_id.id),
                ("channel_id", "=", self.channel_id.id),
                ("id", "<", self.id),
                ("state", "=", "done"),
            ],
            order="id desc",
            limit=3,
        )
        return [link for question in previous for link in question.link_data or []]

    def _reply(self, text, links=None):
        own = list(links or [])
        if own:
            self.link_data = own
        # Primero los de esta respuesta: mandan si un nombre sale en los dos.
        links = own + self._recent_links()
        result = super()._reply(text, links)
        # Los avisos que salen enlazados en la respuesta se apuntan en el
        # mensaje, para tacharlos ahí también (incoespacio_assistant_done).
        message = self.reply_message_id.sudo()
        body = str(message.body or "")
        ids = {int(link[3]) for link in links or [] if len(link) > 3}
        shown = [i for i in ids if 'o_incobot_alert_%d"' % i in body]
        if shown:
            alerts = self.env["assistant.alert"].sudo().browse(shown).exists()
            alerts._link_message(alerts, message)
        return result

    def _cell(self, record, name, env):
        # Un campo calculado puede tirar de otro modelo que el usuario no ve
        # (p. ej. el comprometido en compras): ese dato sale «sin permiso».
        try:
            value = record.read([name])[0][name]
        except AccessError:
            return "sin permiso"
        return self._plain(record._fields[name], value, env)

    @staticmethod
    def _plain(field, value, env):
        if field.type == "many2one":
            return value[1] if value else ""
        if field.type == "selection" and value:
            return dict(field._description_selection(env)).get(value, value)
        if field.type in ("one2many", "many2many"):
            return len(value or [])
        return value

    def _tools(self):
        tools = super()._tools()
        tools[ALERTS_SPEC["name"]] = (ALERTS_SPEC, self._tool_my_alerts)
        return tools

    def _tool_my_alerts(self, env):
        today = env["assistant.alert"]._madrid_today()
        mine = env["assistant.alert"].search(
            [("user_id", "=", env.uid), ("state", "in", ("new", "open"))]
        )
        result = self._rows(
            env,
            "assistant.alert",
            # Comprobados en el momento: lo ya arreglado no sale (solo lee).
            [("id", "in", mine._still_matching().ids)],
            [
                "type_id",
                "message",
                "pending_since",
                "first_seen",
                "res_model",
                "res_id",
            ],
            order="pending_since, id",
        )
        for row in result["filas"]:
            # El enlace va al registro del aviso (la factura, la obra…).
            label = (row["message"] or "").split(" · ", 1)[0]
            row["_link"] = [row.pop("res_model"), row.pop("res_id"), [label], row["id"]]
            since = row.pop("pending_since") or row["first_seen"]
            row.pop("first_seen")
            row["dias"] = (today - since).days if since else None
        return result
