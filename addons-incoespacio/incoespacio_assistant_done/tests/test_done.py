from markupsafe import Markup

from odoo.addons.incoespacio_assistant.tests.test_assistant import AssistantCase


class TestDone(AssistantCase):
    def _last_message(self, user):
        return self._bodies(user)[:1]

    def test_digest_remembers_where_each_alert_was_shown(self):
        atype = self._type("hecho")
        self._role(atype, self.ana | self.luis)
        partners = [self._partner("Obra %02d" % n) for n in range(12)]
        self._run([self._row(partner) for partner in partners])
        for user in (self.ana, self.luis):
            message = self._last_message(user)
            alerts = self._alerts(user)
            linked = alerts.filtered("message_ids")
            # Como mucho 10 líneas por tipo: solo esas quedan ligadas al mensaje.
            self.assertEqual(len(linked), 10)
            self.assertEqual(linked.message_ids, message)
            self.assertFalse((alerts - linked).message_ids)

    def test_resolved_by_only_when_someone_is_named(self):
        atype = self._type("quien")
        self._role(atype, self.ana)
        partner = self._partner("Quién")
        self._run([self._row(partner)])
        alert = self._alerts(self.ana)
        alert.write({"state": "resolved", "resolved_by_id": self.luis.id})
        self.assertEqual(alert.resolved_by_id, self.luis)
        # Vuelve a cumplirse: se reabre y se olvida quién lo resolvió.
        self._run([self._row(partner)])
        self.assertIn(alert.state, ("new", "open"))
        self.assertFalse(alert.resolved_by_id)
        # La revisión diaria lo resuelve sin nombre.
        self._run([])
        self.assertEqual(alert.state, "resolved")
        self.assertFalse(alert.resolved_by_id)

    def _line(self, body, alert):
        # El <li> de ese aviso dentro del mensaje.
        start = body.index("o_incobot_alert_%s" % alert.id)
        return body[body.rindex("<li", 0, start) : body.index("</li>", start)]

    def _shared(self):
        atype = self._type("tachar")
        self._role(atype, self.ana | self.luis)
        fixed, other = self._partner("Arreglada"), self._partner("Otra")
        self._run([self._row(fixed), self._row(other)])
        alerts = self._alerts()
        return (
            alerts.filtered(lambda a: a.res_id == fixed.id),
            alerts.filtered(lambda a: a.res_id == other.id),
        )

    def test_fixed_alert_is_struck_in_every_message(self):
        fixed, other = self._shared()
        fixed.write({"state": "resolved", "resolved_by_id": self.pedro.id})
        for user in (self.ana, self.luis):
            body = self._last_message(user).body
            mine = fixed.filtered(lambda a, user=user: a.user_id == user)
            line = self._line(body, mine)
            self.assertIn("o_incobot_done", line)
            # Lo tenían dos personas: dice quién lo hizo.
            self.assertIn("✓ Hecho por Pedro", line)
            rest = other.filtered(lambda a, user=user: a.user_id == user)
            self.assertNotIn("o_incobot_done", self._line(body, rest))
            self.assertIn(" · 1 hecho", body)
        # Todo hecho y luego reabierto: vuelve a la normalidad.
        other.write({"state": "resolved"})
        self.assertIn(" · todo hecho", self._last_message(self.ana).body)
        fixed.write({"state": "open"})
        body = self._last_message(self.ana).body
        line = self._line(body, fixed.filtered(lambda a: a.user_id == self.ana))
        self.assertNotIn("o_incobot_done", line)
        self.assertNotIn("Hecho", line)
        self.assertIn(" · 1 hecho", body)

    def test_daily_review_strikes_without_a_name(self):
        fixed, other = self._shared()
        fixed.write({"resolved_by_id": self.pedro.id})
        self._run([self._row(self.env["res.partner"].browse(other[:1].res_id))])
        line = self._line(
            self._bodies(self.ana)[-1:].body,
            fixed.filtered(lambda a: a.user_id == self.ana),
        )
        self.assertIn("✓ Hecho<", line)
        self.assertNotIn("por", line)

    def test_own_alert_never_shows_a_name(self):
        atype = self._type("solo")
        self._role(atype, self.ana)
        partner = self._partner("Solo")
        self._run([self._row(partner)])
        alert = self._alerts(self.ana)
        alert.write({"state": "resolved", "resolved_by_id": self.pedro.id})
        line = self._line(self._last_message(self.ana).body, alert)
        self.assertIn("✓ Hecho<", line)
        self.assertNotIn("Pedro", line)

    # Redes de seguridad: lo que no pasa por los ganchos también tacha y reabre.
    def test_opening_the_list_strikes_in_every_message(self):
        fixed, other = self._shared()
        live = [self._row(self.env["res.partner"].browse(other[:1].res_id))]
        alerts = self.env["assistant.alert"].with_context(assistant_rows=live)
        alerts.with_user(self.ana).action_open_my_alerts()
        for user in (self.ana, self.luis):
            body = self._last_message(user).body
            mine = fixed.filtered(lambda a, user=user: a.user_id == user)
            line = self._line(body, mine)
            # Comprobado al mirar: no se sabe quién lo arregló.
            self.assertIn("✓ Hecho<", line)
            self.assertIn(" · 1 hecho", body)

    def test_undoing_the_fix_reopens_and_unstrikes(self):
        fixed, other = self._shared()
        first = self._last_message(self.ana)
        mine = fixed.filtered(lambda a: a.user_id == self.ana)
        partner = self.env["res.partner"]
        rows = [self._row(partner.browse(alert[:1].res_id)) for alert in (fixed, other)]
        # Arreglado: la revisión diaria lo tacha en el primer mensaje.
        self._run(rows[1:])
        self.assertIn("o_incobot_done", self._line(first.body, mine))
        # Se deshace el arreglo: vuelve a salir y el primer mensaje se destacha.
        self._run(rows)
        self.assertIn(mine.state, ("new", "open"))
        line = self._line(first.body, mine)
        self.assertNotIn("o_incobot_done", line)
        self.assertNotIn("Hecho", line)
        self.assertNotIn("hecho", first.body)

    def test_alert_in_an_ai_answer_strikes_its_whole_line(self):
        fixed, other = self._shared()
        mine = fixed.filtered(lambda a: a.user_id == self.ana)
        rest = other.filtered(lambda a: a.user_id == self.ana)
        bot = self.env.ref("incoespacio_assistant.partner_incobot_assistant")
        channel = self.env["discuss.channel"].with_user(self.ana).channel_get([bot.id])
        chip = '<a href="#" class="o_incobot_link o_incobot_alert_%s">%s</a>'
        answer = channel.sudo().message_post(
            body=Markup(
                "<p>Tienes:<br>1. [Tipo] %s · pendiente<br>2. %s · otra</p>"
                % (chip % (mine.id, "Arreglada"), chip % (rest.id, "Otra"))
            ),
            author_id=bot.id,
            message_type="comment",
        )
        mine._link_message(mine | rest, answer)
        before = str(answer.body)
        mine.write({"state": "resolved"})
        body = str(answer.body)
        # Solo la línea de ese aviso, de un salto de línea al siguiente, con
        # el enlace tachado y el sello al final.
        line = body[body.index('<span class="o_incobot_done_line">') :]
        line = line[: line.index("<br>")]
        self.assertIn("1. [Tipo] <a", line)
        self.assertIn(
            'o_incobot_alert_%s o_incobot_done">Arreglada</a>' % mine.id, line
        )
        self.assertIn(
            ' · pendiente<span class="o_incobot_done_mark">✓ Hecho</span>', line
        )
        self.assertNotIn("Otra", line)
        self.assertEqual(body.count("o_incobot_done_line"), 1)
        # Sin cabecera de resumen: no se le pone contador.
        self.assertNotIn("o_incobot_count", body)
        # Se hace también el otro y luego se reabre el primero.
        rest.write({"state": "resolved"})
        self.assertEqual(str(answer.body).count("o_incobot_done_line"), 2)
        mine.write({"state": "open"})
        rest.write({"state": "open"})
        self.assertEqual(str(answer.body), before)
