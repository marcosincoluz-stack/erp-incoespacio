def _strip_pipe(cr, table):
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = %s
           AND column_name = 'bc3_text'
        """,
        (table,),
    )
    if not cr.fetchone():
        return
    # table is one of the two names below; it is not user input.
    cr.execute(
        "UPDATE %s SET bc3_text = regexp_replace(bc3_text, '\\s*\\|\\s*$', '') "
        "WHERE bc3_text ~ '\\|\\s*$'" % table
    )


def migrate(cr, version):
    _strip_pipe(cr, "sale_order_line")
    _strip_pipe(cr, "construction_certification_line")
