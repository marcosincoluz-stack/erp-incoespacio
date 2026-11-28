def migrate(cr, version):
    # El precio ya va con el modelo (PRICES): los ajustes a mano sobran.
    cr.execute(
        "DELETE FROM ir_config_parameter WHERE key IN %s",
        (("incoespacio_assistant_ai.price_in", "incoespacio_assistant_ai.price_out"),),
    )
