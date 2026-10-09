import werkzeug

from odoo import http
from odoo.addons.auth_signup.controllers.main import AuthSignupHome


class AuthSignupHomeInternal(AuthSignupHome):

    def get_auth_signup_config(self):
        config = super().get_auth_signup_config()
        config["signup_enabled"] = False
        config["reset_password_enabled"] = False
        return config

    @http.route()
    def web_auth_signup(self, *args, **kw):
        raise werkzeug.exceptions.NotFound()

    @http.route()
    def web_auth_reset_password(self, *args, **kw):
        raise werkzeug.exceptions.NotFound()

    @http.route()
    def well_known_change_password(self):
        raise werkzeug.exceptions.NotFound()
