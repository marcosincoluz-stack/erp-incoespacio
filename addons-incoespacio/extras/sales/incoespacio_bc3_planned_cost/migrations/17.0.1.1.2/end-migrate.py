def migrate(cr, version):
    cr.execute(
        """
        UPDATE sale_order
           SET planned_percent = 0
         WHERE planned_percent IS NOT NULL
           AND (planned_percent < 0 OR planned_percent >= 100)
        """
    )
    cr.execute(
        """
        UPDATE sale_order_line sol
           SET price_planned = CASE
                    WHEN so.planned_percent = 0 THEN 0
                    ELSE sol.price_unit
                         * (100.0 - so.planned_percent) / 100.0
                END,
               amount_planned = CASE
                    WHEN so.planned_percent = 0 THEN 0
                    ELSE sol.price_unit
                         * (100.0 - so.planned_percent) / 100.0
                         * COALESCE(sol.qty_planned, 0)
                END
          FROM sale_order so
         WHERE sol.order_id = so.id
           AND COALESCE(sol.display_type, '') = ''
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
