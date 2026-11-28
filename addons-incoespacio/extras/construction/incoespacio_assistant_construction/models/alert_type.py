from datetime import timedelta
from zoneinfo import ZoneInfo

from odoo import _, fields, models
from odoo.tools import formatLang

_MADRID = ZoneInfo("Europe/Madrid")
_UTC = ZoneInfo("UTC")


class AssistantAlertType(models.Model):
    _inherit = "assistant.alert.type"

    def _collect_cert_to_invoice(self):
        # Sin fecha de aprobación guardada: cuenta desde la fecha de la
        # certificación, que es cuando se cerró la medición.
        self.ensure_one()
        limit = self._today() - timedelta(days=self.threshold_days or 0)
        certs = self.env["construction.certification"].search(
            [("state", "=", "confirmed"), ("date", "<=", limit)]
        )
        return [
            (cert, cert.project_id.user_id, self._cert_text(cert), cert.date)
            for cert in certs
        ]

    def _collect_cert_draft(self):
        self.ensure_one()
        margin = self.threshold_days or 0
        certs = self.env["construction.certification"].search([("state", "=", "draft")])
        rows = []
        for cert in certs:
            created = self._madrid_date(cert.create_date)
            if created and (self._today() - created).days >= margin:
                rows.append(
                    (cert, cert.project_id.user_id, self._cert_text(cert), created)
                )
        return rows

    def _collect_obra_no_cert(self):
        # Obra en marcha: BC3 confirmado, con obra activa y sin certificar al
        # 100 %. Cuenta desde la última certificación o desde que se confirmó.
        self.ensure_one()
        margin = self.threshold_days or 0
        orders = self.env["sale.order"].search(
            [
                ("state", "=", "sale"),
                ("bc3", "=", True),
                ("project_id", "!=", False),
                ("project_id.active", "=", True),
            ]
        )
        rows = []
        for order in orders:
            if order.amount_untaxed and (
                order.amount_certified_origin >= order.amount_untaxed
            ):
                continue
            certs = order.certification_ids.filtered(lambda c: c.state != "cancel")
            last = max(certs.mapped("date")) if certs else None
            since = last or self._madrid_date(order.date_order)
            if since and (self._today() - since).days >= margin:
                rows.append(
                    (
                        order,
                        order.project_id.user_id,
                        self._obra_text(order, last),
                        since,
                    )
                )
        return rows

    def _cert_text(self, cert):
        amount = formatLang(
            self.env, cert.amount_period_total, currency_obj=cert.currency_id
        )
        return "%s · %s · %s" % (cert.name, cert.project_id.display_name, amount)

    def _obra_text(self, order, last):
        if last:
            when = _("última certificación el %s") % last.strftime("%d/%m/%Y")
        else:
            when = _("sin certificaciones")
        return "%s · %s" % (order.project_id.display_name, when)

    def _today(self):
        return self.env["assistant.alert"]._madrid_today()

    def _madrid_date(self, value):
        moment = fields.Datetime.to_datetime(value)
        if not moment:
            return None
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=_UTC)
        return moment.astimezone(_MADRID).date()
