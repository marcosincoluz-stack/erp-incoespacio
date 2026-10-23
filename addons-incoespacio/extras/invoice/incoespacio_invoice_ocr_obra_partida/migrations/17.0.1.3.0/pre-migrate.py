def migrate(cr, version):
    names = (
        "field_account_move_line__construction_line_id",
        "field_sale_order_line__bc3_section_id",
        "field_sale_order_line__amount_vendor_cost",
        "field_account_move__has_unassigned_partida",
    )
    for name in names:
        cr.execute(
            """
            UPDATE ir_model_data
               SET module = 'incoespacio_construction_cost'
             WHERE module = 'incoespacio_invoice_ocr_obra_partida'
               AND name = %s
               AND model = 'ir.model.fields'
            """,
            (name,),
        )
