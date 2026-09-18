{
    "name": "Incoespacio: Asistente de certificación",
    "summary": "Medir partidas a partir de las facturas de proveedor pendientes",
    "version": "17.0.2.1.0",
    "category": "Accounting/Sales",
    "author": "Incoespacio",
    "license": "LGPL-3",
    "depends": [
        "incoespacio_construction_certification_pending_bills",
        "incoespacio_invoice_ocr_obra_partida",
        "incoespacio_bc3_planned_cost",
    ],
    "data": ["views/construction_certification_views.xml"],
    "installable": True,
    "application": False,
}
