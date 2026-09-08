# -*- coding: utf-8 -*-
{
    'name': "INCOESPACIO: Alertas de Compra IncoBot",
    'version': '17.0.1.0.0',
    'author': 'Incoespacio',
    'category': 'Incoespacio/Purchases',
    'website': 'https://incoespacio.com',
    'license': 'LGPL-3',
    'summary': "Notificaciones y actividades automáticas cuando IncoBot genera pedidos de compra",
    'description': """
        Módulo IncoBot para INCOESPACIO ERP (adaptado de Incoluz para Odoo 17):
        - Detecta pedidos de compra generados por el bot del sistema (ID 1 / procesos automáticos / crons / reposición de stock).
        - Notifica al grupo de compras mediante mensaje directo en el chatter de la orden.
        - Crea automáticamente una actividad 'Por hacer' (To-Do) en Odoo 17 asignada a los responsables de compras.
        - Configura el nombre corporativo IncoBot para el usuario de sistema.
    """,
    'depends': ['base', 'purchase', 'mail'],
    'data': [
        'security/groups.xml',
        'data/bot_data.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
