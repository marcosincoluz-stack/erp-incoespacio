import logging

from odoo import api, models

from odoo.addons.incoespacio_assistant.models.alert import _OPEN

_logger = logging.getLogger(__name__)

PENDING = "incoespacio_assistant_done.recheck"


class AssistantAlert(models.Model):
    _inherit = "assistant.alert"

    @api.model
    def _recheck_later(self, records):
        """Apunta registros guardados para comprobar sus avisos al confirmar.

        Lo llaman los ganchos de los módulos de avisos (facturas, obra) en cada
        guardado. Aquí solo se apuntan los ids: la comprobación de verdad se hace
        una vez, justo antes del commit, cuando el ORM ya ha guardado también
        los campos calculados (p. ej. «tiene líneas sin partida»).
        """
        if not records or not self._assistant_on():
            return
        cr = self.env.cr
        if PENDING not in cr.precommit.data:
            cr.precommit.data[PENDING] = {}
            # Ligado al env de quien guarda: es quien lo ha hecho.
            cr.precommit.add(self._recheck_pending)
        cr.precommit.data[PENDING].setdefault(records._name, set()).update(records.ids)

    def _recheck_pending(self):
        pending = self.env.cr.precommit.data.pop(PENDING, {})
        domain = []
        for model, ids in pending.items():
            domain = (["|"] if domain else []) + domain
            domain += ["&", ("res_model", "=", model), ("res_id", "in", list(ids))]
        if not domain:
            return
        try:
            # Savepoint: un fallo aquí nunca impide guardar la factura; lo
            # recogen después la comprobación al mirar o la revisión diaria.
            with self.env.cr.savepoint():
                self._resolve_by_saver(domain)
                self.env.flush_all()
        except Exception:
            _logger.exception("Asistente: falló la comprobación al guardar")

    def _resolve_by_saver(self, domain):
        # sudo: los avisos son de varias personas; quien guarda no ve los ajenos.
        alerts = self.sudo().search(domain + [("state", "in", _OPEN)])
        if not alerts:
            return
        gone = alerts - alerts._still_matching()
        if not gone:
            return
        user = self.env.user
        # El nombre solo si lo ha hecho una persona (no el OCR ni un cron).
        named = user._is_internal() and not user._is_superuser()
        gone.write(
            {
                "state": "resolved",
                "resolved_date": self._madrid_today(),
                "resolved_by_id": user.id if named else False,
            }
        )
