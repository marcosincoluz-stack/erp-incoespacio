def migrate(cr, version):
    # Hook 1.0.0 used <= and swallowed same-day bills of the last invoiced cert.
    cr.execute(
        """
        UPDATE account_move AS m
           SET certification_id = NULL
          FROM construction_certification AS c
         WHERE m.certification_id = c.id
           AND (m.invoice_date IS NULL OR m.invoice_date >= c.date)
        """
    )
