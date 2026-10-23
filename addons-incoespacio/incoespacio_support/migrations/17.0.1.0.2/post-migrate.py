def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    # noupdate congeló los acentos de una instalación en Windows como '?'.
    env = api.Environment(cr, SUPERUSER_ID, {})
    seeds = (
        ("incoespacio_support.ticket_cat_it", "Informática / Conectividad"),
        ("incoespacio_support.ticket_cat_erp", "ERP & Facturación"),
        ("incoespacio_support.ticket_type_error", "Error crítico"),
    )
    for xid, name in seeds:
        rec = env.ref(xid, raise_if_not_found=False)
        if rec is None or rec.name == name:
            continue
        broken = name.encode("ascii", "replace").decode()
        if rec.name in (broken, broken.replace("?", "\ufffd")):
            rec.name = name
    cr.execute(
        """
        UPDATE mail_message
           SET body = replace(replace(replace(body, '&lt;b&gt;', '<b>'),
                                      '&lt;/b&gt;', '</b>'),
                              '&lt;br/&gt;', '<br/>')
         WHERE model = 'incoespacio_support.ticket' AND body LIKE '%&lt;b&gt;%'
        """
    )
