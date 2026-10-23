# -*- coding: utf-8 -*-


def post_init_hook(env):
    # account.1_sale lo crea el plan contable, no el modulo account.
    # En una base nueva (CI) todavia no existe: no impedir el install.
    journal = env.ref("account.1_sale", raise_if_not_found=False)
    if journal:
        journal.code = "P26"
