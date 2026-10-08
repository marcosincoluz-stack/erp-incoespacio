# Módulos OCA fijados (Odoo 17)

Estos directorios **van en Git**. No uses submódulos ni clones sueltos en el servidor: `git clone` del ERP ya trae lo que Odoo necesita para arrancar.

Congelados desde la rama `17.0` de cada repo OCA el **2026-10-08**. `OCA/web` está en `web-oca` porque así lo espera `addons_path` en `config/odoo.conf`.

| Carpeta | Origen |
| :--- | :--- |
| `account-financial-reporting` | https://github.com/OCA/account-financial-reporting |
| `account-payment` | https://github.com/OCA/account-payment |
| `account-reconcile` | https://github.com/OCA/account-reconcile |
| `bank-payment` | https://github.com/OCA/bank-payment |
| `bank-statement-import` | https://github.com/OCA/bank-statement-import |
| `community-data-files` | https://github.com/OCA/community-data-files |
| `l10n-spain` | https://github.com/OCA/l10n-spain |
| `partner-contact` | https://github.com/OCA/partner-contact |
| `reporting-engine` | https://github.com/OCA/reporting-engine |
| `server-ux` | https://github.com/OCA/server-ux |
| `vertical-construction` | https://github.com/OCA/vertical-construction |
| `web-oca` | https://github.com/OCA/web |

Para actualizar uno: clonar de nuevo esa carpeta (`--branch 17.0 --depth 1`), borrar su `.git`, commit en este repo.
