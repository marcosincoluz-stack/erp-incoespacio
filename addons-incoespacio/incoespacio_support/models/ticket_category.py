# -*- coding: utf-8 -*-
from odoo import models, fields

class TicketCategory(models.Model):
    _name = 'incoespacio_support.ticket_category'
    _description = 'Área o Categoría de Ticket'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    name = fields.Char(string='Nombre', required=True)

    _sql_constraints = [
        ('name_ticket_category_unique', 'UNIQUE(name)', "El nombre del área debe ser único."),
    ]
