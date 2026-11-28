import logging
import re

from lxml import etree, html
from markupsafe import Markup

from odoo import _, fields, models

_logger = logging.getLogger(__name__)

LINE = re.compile(r"\bo_incobot_alert_(\d+)\b")
DONE = "o_incobot_done"
MARK = "o_incobot_done_mark"
COUNT = "o_incobot_count"
WRAP = "o_incobot_done_line"


def _join_before(element, text):
    # Pega texto justo antes del elemento (en el texto del anterior o del padre).
    if not text:
        return
    previous = element.getprevious()
    if previous is not None:
        previous.tail = (previous.tail or "") + text
    else:
        parent = element.getparent()
        parent.text = (parent.text or "") + text


def _remove(element):
    # Quita el elemento y su texto, pero conserva el texto que va detrás.
    _join_before(element, element.tail)
    element.getparent().remove(element)


def _wrap_line(chip):
    """Mete en un <span> la línea del enlace: de un <br> al siguiente."""
    parent = chip.getparent()
    kids = list(parent)
    start = end = kids.index(chip)
    while start > 0 and kids[start - 1].tag != "br":
        start -= 1
    while end + 1 < len(kids) and kids[end + 1].tag != "br":
        end += 1
    span = etree.Element("span", {"class": WRAP})
    if start:
        span.text, kids[start - 1].tail = kids[start - 1].tail, None
    else:
        span.text, parent.text = parent.text, None
    parent.insert(start, span)
    for element in kids[start : end + 1]:
        span.append(element)  # cada uno se lleva su texto de detrás
    return span


def _unwrap(span):
    # Lo contrario de _wrap_line: deja la línea como estaba.
    parent, index, children = span.getparent(), span.getparent().index(span), list(span)
    _join_before(span, span.text)
    if children:
        children[-1].tail = (children[-1].tail or "") + (span.tail or "")
    else:
        _join_before(span, span.tail)
    parent.remove(span)
    for offset, child in enumerate(children):
        parent.insert(index + offset, child)


class AssistantAlert(models.Model):
    _inherit = "assistant.alert"

    # Quién lo arregló, si se sabe seguro (quien guardó el registro). Vacío si lo
    # resolvió la revisión diaria o la comprobación al mirar.
    resolved_by_id = fields.Many2one(
        "res.users", string="Resuelto por", ondelete="set null", readonly=True
    )
    # Mensajes del chat donde ha salido, para tacharlo ahí cuando se resuelva.
    message_ids = fields.Many2many(
        "mail.message",
        "assistant_alert_message_rel",
        "alert_id",
        "message_id",
        string="Mensajes",
        readonly=True,
    )

    def _link_message(self, alerts, message):
        # sudo: el mensaje lo publica el bot; el usuario no escribe esta relación.
        alerts.sudo().write({"message_ids": [(4, message.id)]})
        return super()._link_message(alerts, message)

    def write(self, vals):
        # Cualquier cambio de estado que no diga quién lo hizo (revisión diaria,
        # comprobación al mirar, reapertura) deja «resuelto por» vacío.
        if "state" in vals and "resolved_by_id" not in vals:
            vals = dict(vals, resolved_by_id=False)
        result = super().write(vals)
        if "state" in vals:
            self._repaint()
        return result

    # ------------------------------------------------------------------ #
    # Tachado en los mensajes
    # ------------------------------------------------------------------ #
    def _repaint(self):
        """Vuelve a pintar los mensajes donde salen estos avisos.

        Se toca el mensaje ya publicado, no se genera de nuevo: el resto (el
        saludo, los totales, «y N más») se queda como se mandó. Solo cambia cada
        línea (tachada o no) y el contador de hechos de la cabecera.
        """
        for message in self.sudo().message_ids:
            try:
                body = self._painted(message)
                if body and body != str(message.body):
                    channel = self.env["discuss.channel"].sudo().browse(message.res_id)
                    channel._message_update_content(message, Markup(body))
            except Exception:
                # Un mensaje que no se puede repintar no bloquea el cambio.
                _logger.exception(
                    "Asistente: no se pudo tachar el mensaje %s", message.id
                )

    def _painted(self, message):
        if message.model != "discuss.channel" or not message.body:
            return None
        root = html.fragment_fromstring(str(message.body), create_parent="div")
        lines = root.xpath("//li[contains(@class, 'o_incobot_alert_')]")
        done = 0
        for line in lines:
            alert, is_done = self._alert_of(line)
            done += is_done
            self._paint_line(line, alert, is_done)
        if lines:
            self._paint_count(root, done, len(lines))
        # Respuestas de la IA: el aviso va en el enlace, no en una línea.
        chips = root.xpath("//a[contains(@class, 'o_incobot_alert_')]")
        if chips:
            outside = "[not(ancestor::li[contains(@class, 'o_incobot_alert_')])]"
            for old in root.xpath("//span[contains(@class, '%s')]%s" % (MARK, outside)):
                _remove(old)
            for old in root.xpath("//span[contains(@class, '%s')]" % WRAP):
                _unwrap(old)
        for chip in chips:
            self._paint_chip(chip, *self._alert_of(chip))
        text = etree.tostring(root, encoding="unicode", method="html")
        return text[len("<div>") : -len("</div>")]

    def _paint_line(self, line, alert, is_done):
        classes = [c for c in line.get("class", "").split() if c != DONE]
        for old in line.xpath(".//span[contains(@class, '%s')]" % MARK):
            _remove(old)
        if is_done:
            classes.append(DONE)
            mark = etree.SubElement(line, "span", {"class": MARK})
            mark.text = self._done_text(alert)
        line.set("class", " ".join(classes))

    def _alert_of(self, element):
        match = LINE.search(element.get("class", ""))
        alert = self.sudo().browse(int(match.group(1))).exists() if match else None
        return alert, bool(alert) and alert.state == "resolved"

    def _paint_chip(self, chip, alert, is_done):
        classes = [c for c in chip.get("class", "").split() if c != DONE]
        if is_done:
            classes.append(DONE)
            # Se tacha la línea entera del aviso y el sello va al final.
            parent = chip.getparent()
            line = parent if WRAP in parent.get("class", "") else _wrap_line(chip)
            mark = etree.SubElement(line, "span", {"class": MARK})
            mark.text = self._done_text(alert)
        chip.set("class", " ".join(classes))

    def _done_text(self, alert):
        shared = self.sudo().search_count(
            [
                ("type_id", "=", alert.type_id.id),
                ("res_model", "=", alert.res_model),
                ("res_id", "=", alert.res_id),
            ]
        )
        # El nombre solo si el aviso lo tenían varias personas y se sabe quién fue.
        if shared > 1 and alert.resolved_by_id:
            return _("✓ Hecho por %s") % alert.resolved_by_id.name
        return _("✓ Hecho")

    def _paint_count(self, root, done, total):
        for old in root.xpath("//span[contains(@class, '%s')]" % COUNT):
            _remove(old)
        header = root.find(".//b")
        if header is None or not done:
            return
        span = etree.SubElement(header, "span", {"class": COUNT})
        if done == total:
            span.text = _(" · todo hecho")
        elif done == 1:
            span.text = _(" · 1 hecho")
        else:
            span.text = _(" · %s hechos") % done
