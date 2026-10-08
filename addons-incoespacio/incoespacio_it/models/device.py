# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class Device(models.Model):
    _name = "incoespacio_it.device"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Equipo IT"
    _order = "ip_address desc"

    name = fields.Char(string="Referencia", readonly=True, copy=False, default="Nuevo")
    hostname = fields.Char(copy=False)
    alias = fields.Char(required=True)
    mac_address = fields.Char(string="Dirección MAC")
    ip_address = fields.Char(string="Dirección IP")
    switch_port = fields.Char(string="Puerto del switch")
    floor_port = fields.Char(string="Toma de suelo")
    dns_name = fields.Char(string="Nombre DNS")
    update_server = fields.Char(string="Servidor de actualización")
    so = fields.Char(string="Sistema operativo")
    wol = fields.Boolean(string="WOL")
    serial_number = fields.Char(string="Número de serie")
    manufacturer = fields.Char(string="Fabricante")
    model = fields.Char(string="Modelo")
    purchase_date = fields.Date(string="Fecha de compra")
    warranty_expiry_date = fields.Date(string="Fin de garantía")
    assigned_to = fields.Many2one("res.users", string="Asignado a")
    location = fields.Char(string="Ubicación")
    notes = fields.Text(string="Notas")
    vlan = fields.Char(string="VLAN")
    active = fields.Boolean(default=True)
    tag_ids = fields.Many2many("incoespacio_it.device_tag", string="Etiquetas")

    _sql_constraints = [
        ("hostname_unique", "unique(hostname)", "El hostname debe ser único."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("Nuevo")) == _("Nuevo"):
                vals["name"] = self.env["ir.sequence"].next_by_code("seq.device.id") or _("Nuevo")
        return super().create(vals_list)
