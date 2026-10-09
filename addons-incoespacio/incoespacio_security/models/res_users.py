# -*- coding: utf-8 -*-
from odoo import api, models


class ResUsers(models.Model):
    _inherit = "res.users"

    @api.model
    def _get_signup_invitation_scope(self):
        return "b2b"

    def _action_reset_password(self):
        # Programa interno: el administrador fija la contraseña en el usuario.
        return
