company = env.company
if not company.country_id:
    company.country_id = env.ref("base.es").id
env["account.chart.template"].try_loading("es_pymes", company, install_demo=False)
env.cr.commit()
