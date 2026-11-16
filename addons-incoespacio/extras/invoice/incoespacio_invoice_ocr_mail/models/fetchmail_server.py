# -*- coding: utf-8 -*-
import email
import logging
import re

from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.tools import config

_logger = logging.getLogger(__name__)
_MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
_FOLDERS = ("Odoo-Procesadas", "Odoo-Ignorados", "Odoo-Errores")
# ponytail: tope 50 por pase; subir el tope si el buzón acumula más entre crons.
_LIMIT = 50


class FetchmailServer(models.Model):
    _inherit = "fetchmail.server"

    def fetch_mail(self):
        invoice = self.filtered(lambda server: server._ocr_mail_handles())
        others = self - invoice
        if others:
            super(FetchmailServer, others).fetch_mail()
        for server in invoice:
            server._ocr_mail_fetch()
        return True

    def _ocr_mail_handles(self):
        self.ensure_one()
        return (
            self._get_connection_type() == "imap"
            and self.object_id.model == "account.move"
        )

    def _ocr_mail_fetch(self):
        self.ensure_one()
        imap = None
        try:
            imap = self.connect()
            imap.select()
            self._ocr_mail_ensure_folders(imap)
            since = self._ocr_mail_since(self.create_date)
            _typ, data = imap.uid("SEARCH", "SINCE", since)
            uids = ((data or [b""])[0] or b"").split()[:_LIMIT]
            for uid in uids:
                self._ocr_mail_take(imap, uid)
        except Exception:
            _logger.exception("OCR mail: no se pudo leer el buzón %s", self.name)
        self._ocr_mail_logout(imap)
        self.write({"date": fields.Datetime.now()})
        return True

    def _ocr_mail_take(self, imap, uid):
        _typ, data = imap.uid("FETCH", uid, "(RFC822)")
        raw = next(
            (
                item[1]
                for item in data or []
                if isinstance(item, tuple) and len(item) > 1
            ),
            None,
        )
        if not raw:
            return False
        folder = "Odoo-Procesadas"
        if not self._ocr_mail_has_invoice_file(raw):
            folder = "Odoo-Ignorados"
        else:
            try:
                with self.env.cr.savepoint():
                    self.env["mail.thread"].with_context(
                        fetchmail_cron_running=True,
                        default_fetchmail_server_id=self.id,
                    ).message_process(
                        "account.move",
                        raw,
                        save_original=self.original,
                        strip_attachments=not self.attach,
                    )
            except Exception:
                _logger.exception(
                    "OCR mail: fallo al procesar el correo %s en %s", uid, self.name
                )
                folder = "Odoo-Errores"
            else:
                if not config["test_enable"]:
                    self.env.cr.commit()
        imap.uid("MOVE", uid, folder)
        return folder == "Odoo-Procesadas"

    def _ocr_mail_logout(self, imap):
        if not imap:
            return False
        try:
            imap.logout()
        except Exception:
            _logger.debug("OCR mail: logout falló en %s", self.name)
        return True

    @api.model
    def _ocr_mail_since(self, when):
        when = fields.Datetime.to_datetime(when) or fields.Datetime.now()
        return "%02d-%s-%d" % (when.day, _MONTHS[when.month - 1], when.year)

    @api.model
    def _ocr_mail_has_invoice_file(self, raw):
        if isinstance(raw, str):
            raw = raw.encode()
        for part in email.message_from_bytes(raw).walk():
            if part.get_content_maintype() == "multipart":
                continue
            name = (part.get_filename() or "").lower()
            ctype = (part.get_content_type() or "").lower()
            is_file = ctype == "application/pdf" or ctype.endswith("/xml")
            is_file = is_file or name.endswith((".pdf", ".xml"))
            if is_file and (part.get_payload(decode=True) or part.get_payload()):
                return True
        return False

    def _ocr_mail_ensure_folders(self, imap):
        for name in _FOLDERS:
            try:
                imap.create(name)
            except Exception:
                _logger.debug("OCR mail: carpeta %s no se creó (ya existe)", name)
        return True

    @api.model
    def _cron_ocr_mail_health(self):
        servers = self.search([("active", "=", True), ("state", "=", "done")])
        for server in servers.filtered(lambda item: item._ocr_mail_handles()):
            server._ocr_mail_health()
        return True

    def _ocr_mail_health(self):
        self.ensure_one()
        try:
            imap = self.connect()
        except Exception as err:
            _logger.exception("OCR mail: el buzón %s no conecta", self.name)
            return self._ocr_mail_notify(str(err))
        count = 0
        try:
            _typ, data = imap.status("Odoo-Errores", "(MESSAGES)")
            count = self._ocr_mail_status_count(data)
        except Exception:
            _logger.debug("OCR mail: Odoo-Errores no existe todavía en %s", self.name)
        self._ocr_mail_logout(imap)
        if count:
            return self._ocr_mail_notify(
                _("%s correos en la carpeta Odoo-Errores.") % count
            )
        return True

    @api.model
    def _ocr_mail_status_count(self, data):
        raw = (data or [b""])[0]
        raw = raw[0] if isinstance(raw, tuple) else raw
        if isinstance(raw, bytes):
            raw = raw.decode(errors="replace")
        match = re.search(r"MESSAGES\s+(\d+)", raw or "")
        return int(match.group(1)) if match else 0

    def _ocr_mail_notify(self, reason):
        self.ensure_one()
        partners = self.env.ref("account.group_account_manager").users.partner_id
        if not partners:
            return False
        self.env["mail.thread"].message_notify(
            partner_ids=partners.ids,
            subject=_("Buzón de facturas: %s") % self.name,
            body=Markup("<p><b>%s</b></p><p>%s</p>")
            % (escape(self.name or ""), escape(reason or "")),
        )
        return True
