# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class Ticket(models.Model):
    _name = 'incoespacio_support.ticket'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Ticket de Soporte e Incidencias'
    _order = 'pinned desc, priority desc, id desc'

    name = fields.Char(string='Referencia', readonly=True, index=True, default=lambda self: _('Nuevo'))
    title = fields.Char(string='Título', required=True, tracking=True, index=True)
    user_id = fields.Many2one(
        'res.users', string='Creado por', default=lambda self: self.env.user, tracking=True, index=True)
    assigned_user_id = fields.Many2one(
        'res.users', string='Asignado a', tracking=True, index=True)
    state = fields.Selection([
        ('draft', 'Pendiente'),
        ('working', 'En revisión'),
        ('soon', 'Resuelto'),
        ('done', 'Cerrado')
    ], string='Estado', default='draft', tracking=True, index=True)
    type_id = fields.Many2one(
        'incoespacio_support.ticket_type', string='Tipo', required=True, tracking=True)
    category_id = fields.Many2one(
        'incoespacio_support.ticket_category', string='Área / Departamento', tracking=True)
    priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'Alta'),
    ], string='Prioridad', default='0', tracking=True)
    pinned = fields.Boolean(string='Fijado', default=False)
    description = fields.Text(string='Descripción')
    error_log = fields.Text(string='Registro de error (Log)')
    closed_date = fields.Datetime(string='Fecha de cierre', readonly=True)
    resolution = fields.Text(string='Resolución')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nuevo')) == _('Nuevo'):
                vals['name'] = self.env['ir.sequence'].next_by_code('seq.ticket.id') or _('Nuevo')
        tickets = super(Ticket, self).create(vals_list)

        for ticket in tickets:
            # Notificar al administrador de soporte si existe el grupo
            group = self.env.ref('incoespacio_security.support_group_admin', raise_if_not_found=False)
            if group and group.users:
                partners = [u.partner_id.id for u in group.users if u.partner_id]
                ticket.message_post(
                    body=_("Se ha creado el ticket: <b>[%s] %s</b>") % (ticket.name, ticket.title),
                    partner_ids=partners,
                    subtype_xmlid='mail.mt_comment',
                )

            # Notificar al técnico asignado
            if ticket.assigned_user_id and ticket.assigned_user_id != self.env.user:
                ticket.message_post(
                    body=_("Ticket <b>[%s] %s</b> asignado a %s") % (ticket.name, ticket.title, ticket.assigned_user_id.name),
                    partner_ids=[ticket.assigned_user_id.partner_id.id],
                    subtype_xmlid='mail.mt_comment',
                )

        return tickets

    def write(self, vals):
        if 'assigned_user_id' in vals and vals['assigned_user_id']:
            new_user = self.env['res.users'].browse(vals['assigned_user_id'])
            for rec in self:
                if rec.assigned_user_id != new_user:
                    rec.message_post(
                        body=_("Ticket reasignado a: <b>%s</b>") % new_user.name,
                        partner_ids=[new_user.partner_id.id],
                        subtype_xmlid='mail.mt_comment',
                    )
        return super(Ticket, self).write(vals)

    def _check_ticket_permission(self):
        """Verifica que el usuario tenga permisos para cambiar de fase"""
        user = self.env.user
        if user.has_group('incoespacio_security.support_group_admin'):
            return True
        if user.has_group('incoespacio_security.support_group_manager'):
            for rec in self:
                if rec.assigned_user_id and rec.assigned_user_id != user:
                    raise UserError(_("Solo puedes cambiar el estado de los tickets que tienes asignados."))
            return True
        return True

    def _transition(self, state, msg_fn, require_resolution=False):
        self._check_ticket_permission()
        for rec in self:
            if require_resolution and not (rec.resolution or '').strip():
                raise UserError(_("Debes redactar la 'Resolución' antes de poder cerrar el ticket."))
            vals = {'state': state}
            if state == 'done':
                vals['closed_date'] = fields.Datetime.now()
            rec.write(vals)
            partners = [rec.user_id.partner_id.id] if rec.user_id else []
            if rec.assigned_user_id and rec.assigned_user_id != rec.user_id:
                partners.append(rec.assigned_user_id.partner_id.id)
            rec.message_post(
                body=msg_fn(rec),
                partner_ids=partners,
                subtype_xmlid='mail.mt_comment',
            )

    def button_working(self):
        self._transition('working', lambda r: _("El ticket <b>[%s]</b> ha pasado a estado: <b>En revisión</b>") % r.name)

    def button_soon(self):
        self._transition('soon', lambda r: _("El ticket <b>[%s]</b> ha sido marcado como: <b>Resuelto</b>") % r.name)

    def button_done(self):
        self._transition(
            'done',
            lambda r: _("El ticket <b>[%s]</b> ha sido <b>Cerrado</b>.<br/><b>Resolución:</b> %s") % (r.name, r.resolution),
            require_resolution=True,
        )

    def button_reset(self):
        user = self.env.user
        if not user.has_group('incoespacio_security.support_group_admin'):
            raise UserError(_("Solo un Administrador de soporte puede reiniciar un ticket."))
        self.write({'state': 'draft'})
