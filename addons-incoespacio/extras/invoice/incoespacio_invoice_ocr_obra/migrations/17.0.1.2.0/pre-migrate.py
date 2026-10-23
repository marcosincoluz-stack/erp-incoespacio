def migrate(cr, version):
    names = (
        "field_account_move_line__construction_section_id",
        "field_sale_order__chapter_cost_text",
        "field_sale_order__amount_cost_in_chapter",
        "field_sale_order__amount_cost_no_chapter",
    )
    for name in names:
        cr.execute(
            """
            UPDATE ir_model_data
               SET module = 'incoespacio_construction_cost'
             WHERE module = 'incoespacio_invoice_ocr_obra'
               AND name = %s
               AND model = 'ir.model.fields'
            """,
            (name,),
        )
