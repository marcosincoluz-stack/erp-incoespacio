import re
import unicodedata

from lxml import etree, html
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

# Las dos frases que la IA tiene que decir cuando no sabe (ver SYSTEM).
GAPS = {
    "data": "no lo puedo consultar",
    "wiki": "no esta en la wiki",
}
RATE = re.compile(r"\bo_incobot_rate_(up|down)\b")
QUESTION = "o_incobot_q_%d"
RATED = "o_incobot_rated"
ICONS = {"up": "fa-thumbs-o-up", "down": "fa-thumbs-o-down"}


def _plain(text):
    text = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def _gap(answer):
    plain = _plain(answer)
    for gap, phrase in GAPS.items():
        if phrase in plain:
            return gap
    return False


class AssistantAiQuestion(models.Model):
    _inherit = "assistant.ai.question"

    gap = fields.Selection(
        [("data", "No lo puede consultar"), ("wiki", "No está en la wiki")],
        string="Sin respuesta",
        readonly=True,
        index=True,
        help="Lo que el equipo pregunta y IncoBot aún no sabe: lo siguiente que hacer.",
    )
    rating = fields.Selection(
        [("up", "Útil"), ("down", "No útil")],
        string="Valoración",
        readonly=True,
        index=True,
    )

    def _answer_one(self):
        super()._answer_one()
        if self.state != "done" or not self.reply_message_id:
            return
        self.gap = _gap(self.answer)
        message = self.reply_message_id.sudo()
        body = Markup(str(message.body or "")) + self._rating_html()
        self.channel_id.sudo()._message_update_content(message, body)

    def _rating_html(self):
        button = (
            '<span class="o_incobot_rate o_incobot_rate_{0} {1}" title="{2}">'
            '<i class="fa {3}"></i></span>'
        )
        tag = QUESTION % self.id
        return Markup(
            '<p class="o_incobot_rating">%s%s</p>'
            % (
                button.format("up", tag, _("Útil"), ICONS["up"]),
                button.format("down", tag, _("No útil"), ICONS["down"]),
            )
        )

    @api.model
    def rate(self, question_id, value):
        """Valora una respuesta desde el chat. Solo quien preguntó.

        Pulsar otra vez la misma valoración la quita.
        """
        if value not in ICONS:
            raise UserError(_("Valoración no válida."))
        question = self.sudo().browse(int(question_id)).exists()
        if not question or question.user_id != self.env.user:
            raise AccessError(_("Solo puedes valorar tus propias respuestas."))
        question.rating = False if question.rating == value else value
        question._paint_rating()
        return question.rating

    def _paint_rating(self):
        message = self.reply_message_id.sudo()
        if not message.body:
            return
        root = html.fragment_fromstring(str(message.body), create_parent="div")
        for button in root.xpath("//span[contains(@class, 'o_incobot_rate_')]"):
            match = RATE.search(button.get("class", ""))
            if not match:
                continue
            value = match.group(1)
            chosen = value == self.rating
            classes = [c for c in button.get("class", "").split() if c != RATED]
            button.set("class", " ".join(classes + ([RATED] if chosen else [])))
            for icon in button.iter("i"):
                # Elegido: el icono relleno; si no, el de contorno.
                solid = ICONS[value].replace("-o-", "-")
                icon.set("class", "fa %s" % (solid if chosen else ICONS[value]))
        text = etree.tostring(root, encoding="unicode", method="html")
        body = Markup(text[len("<div>") : -len("</div>")])
        self.channel_id.sudo()._message_update_content(message, body)
