# -*- coding: utf-8 -*-
from odoo import models, fields

class TicketType(models.Model):
    _name = 'incoespacio_support.ticket_type'
    _description = 'Tipo de Ticket de Soporte'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    name = fields.Char(string='Nombre', required=True)

    _sql_constraints = [
        ('name_ticket_type_unique', 'UNIQUE(name)', "El nombre del tipo de ticket debe ser único."),
    ]
