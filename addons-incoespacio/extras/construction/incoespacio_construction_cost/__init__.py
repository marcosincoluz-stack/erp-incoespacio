from . import models

MOVED_FIELDS = (
    (
        "incoespacio_invoice_ocr_obra",
        "field_account_move_line__construction_section_id",
    ),
    ("incoespacio_invoice_ocr_obra", "field_sale_order__chapter_cost_text"),
    ("incoespacio_invoice_ocr_obra", "field_sale_order__amount_cost_in_chapter"),
    ("incoespacio_invoice_ocr_obra", "field_sale_order__amount_cost_no_chapter"),
    (
        "incoespacio_invoice_ocr_obra_partida",
        "field_account_move_line__construction_line_id",
    ),
    ("incoespacio_invoice_ocr_obra_partida", "field_sale_order_line__bc3_section_id"),
    (
        "incoespacio_invoice_ocr_obra_partida",
        "field_sale_order_line__amount_vendor_cost",
    ),
    (
        "incoespacio_invoice_ocr_obra_partida",
        "field_account_move__has_unassigned_partida",
    ),
    (
        "incoespacio_invoice_ocr_obra_purchase",
        "field_purchase_order_line__construction_line_id",
    ),
)


def pre_init_hook(env):
    # El campo pasa de modulo antes de que Odoo actualice el antiguo: si no,
    # el update borra la columna. En una base nueva no hay filas y no hace nada.
    for module, name in MOVED_FIELDS:
        env.cr.execute(
            """
            UPDATE ir_model_data
               SET module = 'incoespacio_construction_cost'
             WHERE module = %s AND name = %s AND model = 'ir.model.fields'
            """,
            (module, name),
        )


def post_init_hook(env):
    env.cr.execute(
        """
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'account_move' AND column_name = 'ocr_obra_state'
        """
    )
    if not env.cr.fetchone():
        return
    env.cr.execute(
        """
        UPDATE account_move
           SET construction_not_job = TRUE
         WHERE ocr_obra_state = 'skipped'
        """
    )
