def migrate(cr, version):
    cr.execute(
        """
        UPDATE sale_order_line
           SET qty_planned = product_uom_qty
         WHERE qty_planned = 0
           AND product_uom_qty <> 0
           AND COALESCE(display_type, '') = ''
        """
    )
