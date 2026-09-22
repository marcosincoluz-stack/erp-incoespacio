NAMES = {
    "product_product_product_units": "Unidades",
    "product_product_product_template_units": "Unidades",
    "product_product_product_meter": "Metro lineal",
    "product_product_product_template_meter": "Metro lineal",
    "product_product_product_square_meter": "m²",
    "product_product_product_template_square_meter": "m²",
    "product_product_product_cubic_meter": "m³",
    "product_product_product_template_cubic_meter": "m³",
    "product_product_product_g": "g",
    "product_product_product_template_g": "g",
    "product_product_product_l": "L",
    "product_product_product_template_l": "L",
}


def migrate(cr, version):
    # noupdate=1: el XML no reescribe los nombres ya instalados
    for xmlid, label in NAMES.items():
        cr.execute(
            """
            UPDATE product_template t
               SET name = jsonb_build_object('en_US', %s, 'es_ES', %s)
              FROM ir_model_data d
              LEFT JOIN product_product p
                ON d.model = 'product.product' AND p.id = d.res_id
             WHERE d.module = 'bc3_importer'
               AND d.name = %s
               AND t.id = COALESCE(
                    p.product_tmpl_id,
                    CASE WHEN d.model = 'product.template' THEN d.res_id END
               )
            """,
            (label, label, xmlid),
        )
