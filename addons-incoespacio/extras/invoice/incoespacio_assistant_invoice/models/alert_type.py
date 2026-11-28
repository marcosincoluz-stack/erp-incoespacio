from datetime import timedelta
from zoneinfo import ZoneInfo

from odoo import _, fields, models
from odoo.tools import formatLang

_MADRID = ZoneInfo("Europe/Madrid")
_UTC = ZoneInfo("UTC")


class AssistantAlertType(models.Model):
    _inherit = "assistant.alert.type"

    def _collect_bill_draft_no_obra(self):
        self.ensure_one()
        moves = self._drafts_without_obra()
        return [
            (
                move,
                move.ocr_obra_suggested_id.user_id,
                self._draft_text(move),
                self._created(move),
            )
            for move in moves
        ]

    def _collect_bill_no_partida(self):
        self.ensure_one()
        domain = [
            ("move_type", "in", ("in_invoice", "in_refund")),
            ("state", "=", "posted"),
            ("project_id", "!=", False),
            ("has_unassigned_partida", "=", True),
        ]
        # Sin corte saldría todo lo publicado antes de que existieran partidas.
        if self.since_date:
            domain.append(("create_date", ">=", self.since_date))
        moves = self.env["account.move"].search(domain)
        return [
            (
                move,
                move.project_id.user_id,
                self._partida_text(move),
                self._created(move),
            )
            for move in moves
        ]

    def _collect_bill_ocr_failed(self):
        # ponytail: el buzón IMAP no es un registro; el cron de correo ya avisa
        # de Odoo-Errores. Aquí solo entra la factura cuyo OCR quedó en error.
        # Solo borradores: nadie limpia ocr_status al publicar o cancelar a mano.
        self.ensure_one()
        moves = self.env["account.move"].search(
            [
                ("move_type", "in", ("in_invoice", "in_refund")),
                ("state", "=", "draft"),
                ("ocr_status", "=", "error"),
            ]
        )
        empty = self.env["res.users"]
        return [
            (move, empty, self._ocr_text(move), self._created(move)) for move in moves
        ]

    def _collect_bill_draft_empty(self):
        # Borrador a medias: ni proveedor ni importe. Fuera los que siguen en la
        # cola del OCR o fallaron (esos van en «Cola OCR con error»).
        self.ensure_one()
        margin = self.threshold_days or 0
        moves = self.env["account.move"].search(
            [
                ("move_type", "in", ("in_invoice", "in_refund")),
                ("state", "=", "draft"),
                ("partner_id", "=", False),
                ("amount_total", "=", 0),
                ("ocr_status", "not in", ("pending", "processing", "error")),
            ]
        )
        empty = self.env["res.users"]
        return [
            (move, empty, self._empty_text(move), self._created(move))
            for move in moves
            if self._age(move) >= margin
        ]

    def _collect_invoice_overdue(self):
        # Cliente que no paga: cuenta desde el vencimiento. «En pago» ya está
        # registrado y espera al banco, no es deuda.
        self.ensure_one()
        today = self.env["assistant.alert"]._madrid_today()
        limit = today - timedelta(days=self.threshold_days or 0)
        moves = self.env["account.move"].search(
            [
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("payment_state", "in", ("not_paid", "partial")),
                ("invoice_date_due", "<", limit),
            ]
        )
        empty = self.env["res.users"]
        return [
            (move, empty, self._overdue_text(move), move.invoice_date_due)
            for move in moves
        ]

    def _overdue_text(self, move):
        amount = formatLang(
            self.env, move.amount_residual, currency_obj=move.currency_id
        )
        return _("%s · %s · %s sin cobrar") % (
            move.name,
            move.partner_id.name or "",
            amount,
        )

    def _drafts_without_obra(self):
        margin = self.threshold_days or 0
        domain = [
            ("move_type", "in", ("in_invoice", "in_refund")),
            ("state", "=", "draft"),
            ("project_id", "=", False),
            ("construction_not_job", "=", False),
            # Los vacíos (sin proveedor y a 0 €) tienen su propio aviso.
            "|",
            ("partner_id", "!=", False),
            ("amount_total", "!=", 0),
        ]
        if margin:
            limit = fields.Datetime.now() - timedelta(days=margin - 1)
            domain.append(("create_date", "<=", fields.Datetime.to_string(limit)))
        moves = self.env["account.move"].search(domain)
        return moves.filtered(lambda move: self._age(move) >= margin)

    def _draft_text(self, move):
        amount = formatLang(self.env, move.amount_total, currency_obj=move.currency_id)
        bits = [self._bill_name(move)]
        if move.partner_id.name:
            bits.append(move.partner_id.name)
        bits.append(amount)
        return " · ".join(bits)

    def _partida_text(self, move):
        return "%s · %s" % (self._bill_name(move), move.project_id.display_name)

    def _ocr_text(self, move):
        detail = (move.ocr_error_message or _("Error OCR")).strip().split("\n", 1)[0]
        return "%s · %s" % (self._bill_name(move), detail[:120])

    def _empty_text(self, move):
        return _("%s · creado por %s") % (self._bill_name(move), move.create_uid.name)

    def _bill_name(self, move):
        if move.name and move.name != "/":
            return move.name
        return move.ref or _("Borrador %s") % move.id

    def _created(self, move):
        # Fecha de entrada en el ERP, en hora de Madrid.
        moment = fields.Datetime.to_datetime(move.create_date)
        if not moment:
            return None
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=_UTC)
        return moment.astimezone(_MADRID).date()

    def _age(self, move):
        created = self._created(move)
        if not created:
            return 0
        return (self.env["assistant.alert"]._madrid_today() - created).days
