from . import models


def post_init_hook(env):
    # New columns arrive NULL or false; existing print_prices stays as the user left it.
    env.cr.execute(
        """
        UPDATE sale_order
           SET print_show_code = TRUE,
               print_signature = TRUE,
               print_gg_pct = 13,
               print_bi_pct = 6,
               print_prices = COALESCE(print_prices, TRUE),
               print_subtotals = COALESCE(print_subtotals, TRUE),
               print_summary = COALESCE(print_summary, TRUE),
               print_summary_pct = COALESCE(print_summary_pct, TRUE),
               print_code = COALESCE(print_code, 'decimal')
        """
    )
