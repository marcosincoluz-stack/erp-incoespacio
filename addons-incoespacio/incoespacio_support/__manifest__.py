# -*- coding: utf-8 -*-
{
    'name': "Incoespacio: Soporte e Incidencias",
    'version': '17.0.1.0.1',
    'author': 'Incoespacio',
    'category': 'Services/Helpdesk',
    'website': 'https://incoespacio.com',
    'license': 'LGPL-3',
    'summary': """Gestión de tickets, soporte al cliente e incidencias internas""",
    'description': """
        Módulo de gestión de incidencias y soporte adaptado para Incoespacio (basado en incoluz_support):
        - Flujo de tickets: Pendiente -> En revisión -> Resuelto -> Cerrado.
        - Notificaciones automáticas por Chatter.
        - Obligatoriedad de resolución antes del cierre.
        - Categorías por áreas de negocio y tipos de incidencia.
        - Blindaje de seguridad y reglas de registro para técnicos y administradores.
    """,
    'depends': ['base', 'mail', 'incoespacio_security'],
    'data': [
        'data/ticket_sequence.xml',
        'data/ticket_data.xml',
        'security/ir.model.access.csv',
        'security/ticket_rules.xml',
        'views/ticket_views.xml',
        'views/ticket_category_views.xml',
        'views/ticket_type_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
