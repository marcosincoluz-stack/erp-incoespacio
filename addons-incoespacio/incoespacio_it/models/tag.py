from odoo import fields, models


class DeviceTag(models.Model):
    _name = "incoespacio_it.device_tag"
    _description = "Etiqueta de equipo IT"

    name = fields.Char(required=True)
    color = fields.Integer()
