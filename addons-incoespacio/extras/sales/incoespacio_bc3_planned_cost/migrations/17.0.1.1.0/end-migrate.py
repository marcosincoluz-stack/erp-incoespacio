def migrate(cr, version):
    cr.execute(
        """
        UPDATE sale_order
           SET planned_percent = 100.0 - planned_percent
         WHERE planned_percent IS NOT NULL
           AND planned_percent != 0
        """
    )
    cr.execute(
        """
        UPDATE sale_order_line sol
           SET price_planned = sol.price_unit
                              * (100.0 - so.planned_percent) / 100.0,
               amount_planned = sol.price_unit
                              * (100.0 - so.planned_percent) / 100.0
                              * sol.qty_planned
          FROM sale_order so
         WHERE sol.order_id = so.id
           AND COALESCE(sol.display_type, '') = ''
           AND so.planned_percent != 0
        """
    )
    cr.execute(
        """
        UPDATE sale_order_line
           SET price_planned = 0,
               amount_planned = 0
         WHERE COALESCE(display_type, '') <> ''
            OR order_id IN (
                SELECT id FROM sale_order WHERE COALESCE(planned_percent, 0) = 0
            )
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
