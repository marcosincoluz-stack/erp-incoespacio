def migrate(cr, version):
    # El compute de bc3_code/bc3_text pasa al submódulo. El xmlid del campo
    # apunta al mismo ir.model.fields que bc3_importer: se reasigna, no se borra,
    # para que esta actualización no tire la columna.
    cr.execute(
        """
        UPDATE ir_model_data
           SET module = 'incoespacio_bc3_price_db_suggest'
         WHERE module = 'incoespacio_bc3_price_db'
           AND model = 'ir.model.fields'
           AND name IN (
                'field_sale_order_line__bc3_code',
                'field_sale_order_line__bc3_text'
           )
        """
    )
