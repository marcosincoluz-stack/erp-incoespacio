from . import models


def post_init_hook(env):
    partner = env.ref(
        "incoespacio_assistant.partner_incobot_assistant", raise_if_not_found=False
    )
    if partner and env.company.logo and not partner.image_1920:
        partner.image_1920 = env.company.logo
    cron = env.ref("incoespacio_assistant.ir_cron_assistant", raise_if_not_found=False)
    if cron:
        cron.nextcall = env["assistant.alert"]._next_call()
