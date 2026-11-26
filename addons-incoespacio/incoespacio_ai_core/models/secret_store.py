import logging
import os

from cryptography.fernet import Fernet, InvalidToken

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

MASTER_ENV = "ODOO_SECRETS_KEY"
PREFIX = "enc:v1:"
GEMINI_KEY = "incoespacio_invoice_ocr.gemini_api_key"


class IncoespacioSecret(models.AbstractModel):
    """Claves de API cifradas en ir.config_parameter.

    La llave maestra vive en la variable de entorno ODOO_SECRETS_KEY (el .env del
    servidor), fuera de la base y de los backups. En la base solo queda el texto
    cifrado. Nunca se guarda en claro ni se escribe el valor en el log.

    Todos los métodos son privados (_): Odoo no deja llamarlos por RPC, así que
    ningún usuario puede pedir una clave desde el navegador.
    """

    _name = "incoespacio.secret"
    _description = "Claves de API cifradas"

    @api.model
    def _fernet(self):
        master = (os.environ.get(MASTER_ENV) or "").strip()
        if not master:
            return None
        try:
            return Fernet(master.encode())
        except (ValueError, TypeError):
            _logger.error("Secretos: %s no es una llave Fernet válida.", MASTER_ENV)
            return None

    @api.model
    def _params(self):
        # sudo justificado: los secretos son de admin; nunca se exponen por ACL.
        return self.env["ir.config_parameter"].sudo()

    @api.model
    def _set_secret(self, name, value):
        value = (value or "").strip()
        if not value:
            return self._clear_secret(name)
        fernet = self._fernet()
        if not fernet:
            raise UserError(
                _(
                    "Falta la llave maestra %s en el servidor. "
                    "La clave no se ha guardado: nunca se guarda en claro."
                )
                % MASTER_ENV
            )
        token = fernet.encrypt(value.encode()).decode()
        params = self._params()
        params.set_param(name, PREFIX + token)
        params.set_param(name + ".hint", value[-4:])
        params.set_param(
            name + ".updated", fields.Datetime.to_string(fields.Datetime.now())
        )
        _logger.info("Secretos: %s actualizado por %s.", name, self.env.user.login)
        return True

    @api.model
    def _clear_secret(self, name):
        params = self._params()
        for key in (name, name + ".hint", name + ".updated"):
            params.search([("key", "=", key)]).unlink()
        _logger.info("Secretos: %s borrado por %s.", name, self.env.user.login)
        return True

    @api.model
    def _get_secret(self, name):
        raw = (self._params().get_param(name) or "").strip()
        if not raw:
            return ""
        if not raw.startswith(PREFIX):
            return self._legacy(name, raw)
        fernet = self._fernet()
        if not fernet:
            _logger.error("Secretos: %s cifrado pero falta %s.", name, MASTER_ENV)
            return ""
        try:
            return fernet.decrypt(raw[len(PREFIX) :].encode()).decode()
        except InvalidToken:
            _logger.error("Secretos: %s no se descifra con la llave actual.", name)
            return ""

    @api.model
    def _legacy(self, name, plain):
        # Clave antigua en claro: se cifra en cuanto hay llave maestra.
        if self._fernet():
            self._set_secret(name, plain)
            _logger.info("Secretos: %s estaba en claro y se ha cifrado.", name)
        else:
            _logger.warning(
                "Secretos: %s sigue en claro en la base; define %s.", name, MASTER_ENV
            )
        return plain

    @api.model
    def _secret_status(self, name):
        raw = (self._params().get_param(name) or "").strip()
        if not raw:
            return _("Sin configurar")
        if not raw.startswith(PREFIX):
            return _("En claro en la base: falta la llave maestra en el servidor")
        if not self._fernet():
            return _("Falta la llave maestra en el servidor")
        if not self._get_secret(name):
            return _("No se puede descifrar: vuelve a pegar la clave")
        hint = self._params().get_param(name + ".hint") or ""
        updated = self._params().get_param(name + ".updated") or ""
        return _("Configurada · termina en …%s · cambiada %s") % (hint, updated[:10])
