# -*- coding: utf-8 -*-
{
    'name': "INCOESPACIO: Informes PDF Corporativos",
    'version': '17.0.1.0.0',
    'author': 'Incoespacio',
    'category': 'Customizations/Reports',
    'website': 'https://incoespacio.com',
    'license': 'LGPL-3',
    'summary': 'Informes PDF corporativos de Facturas y Presupuestos con diseño profesional Incoluz',
    'description': """
        Módulo de Informes PDF Corporativos para INCOESPACIO:
        - Cabecera y pie de página corporativos con franja roja #e72228.
        - Facturas de venta y rectificativas con desglose de emisor/receptor, impuestos y datos bancarios de cobro.
        - Presupuestos y pedidos de venta con validez de oferta y bloque de firma/aceptación de cliente.
        - Datos de empresa 100% dinámicos procedentes de la ficha de compañía.
    """,
    'depends': ['base', 'web', 'account', 'sale_management'],
    'data': [
        'data/paperformat_data.xml',
        'data/sequence_data.xml',
        'report/layout_templates.xml',
        'report/report_invoice.xml',
        'report/report_sale_order.xml',
    ],
    'assets': {
        'web.report_assets_common': [
            'incoespacio_reports/static/src/css/report_styles.css',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
