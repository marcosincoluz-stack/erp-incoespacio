def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    env["incoespacio_support.ticket"]._fix_seed_mojibake()
