def migrate(cr, version):
    cr.execute(
        """
        UPDATE sale_order_line
           SET qty_planned = product_uom_qty
         WHERE qty_planned IS NULL
           AND COALESCE(display_type, '') = ''
        """
    )
    cr.execute(
        """
        UPDATE sale_order_line
           SET amount_planned = COALESCE(price_planned, 0) * COALESCE(qty_planned, 0)
         WHERE COALESCE(display_type, '') = ''
        """
    )
    cr.execute(
        """
        UPDATE sale_order so
           SET amount_planned = COALESCE((
                SELECT SUM(sol.amount_planned)
                  FROM sale_order_line sol
                 WHERE sol.order_id = so.id
           ), 0)
        """
    )
