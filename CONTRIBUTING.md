# Cómo se trabaja en el ERP de Incoespacio

Odoo 17. Lo que está en este fichero es la norma. El código de los agentes (ponytail, skills) no forma parte del ERP.

## Layout

Odoo solo lee el primer nivel de cada entrada de `addons_path` (`config/odoo.conf` en el servidor, `config/odoo.conf_example` en el repo).

- Transversales en `addons-incoespacio/`: `theme`, `security`, `support`, `reports`, `ai_core`, y los de chrome (`app_filters`, `chatter_fold`, `section_fold`, `it`).
- Dominio en `addons-incoespacio/extras/<dominio>/`: `construction`, `invoice`, `partner`, `purchases`, `sales`. Cada carpeta de dominio va en `addons_path`.
- OCA fijada en `addons/`. No se reformatea ni se le aplica el tope de líneas.

## Módulos

Un módulo, un propósito. Lo que se puede instalar aparte es un submódulo que depende del de negocio, en la misma carpeta de dominio. Nombre: `incoespacio_<base>_<feature>`.

En el módulo base solo entra su propósito original, un bugfix de ese propósito, o un ajuste sin el cual esa función no se puede usar.

Tope: **500 líneas de Python + JS**, sin contar tests, migraciones, XML, CSS ni SCSS. Lo comprueba `scripts/check_module_size.py`.

Excepciones, porque partirlas no deja un módulo instalable con sentido:

- `incoespacio_construction_certification` — certificación a origen, retención, proyecto y mediciones.
- Familia OCR de extracción: `incoespacio_invoice_ocr`, `_async`, `_ui`, `_obra`.
- `incoespacio_reports` — factura y pedido legales.
- `incoespacio_theme` — chrome. Los colores salen de las variables SCSS del core; `backend_theme.scss` no usa `!important`.
- `bc3_importer` — port OCA (AGPL, autores originales). No se reformatea.

`incoespacio_construction_certification_assistant` está en su techo medido (504). No se deja crecer.

El `!important` de `report_styles.css` se queda: wkhtmltopdf lo necesita.

## Commits y ramas

`[TAG] modulo: por qué`

`ADD` módulo nuevo, `FIX` bug, `REF` refactor, `IMP` mejora, `DEL` borrado, `REV` revert, `REL` versión, `MERGE` fusión, `I18N` traducción.

- `main`: producción.
- `feat-*` y `hotfix-*`: el cambio entra por pull request. No se fusiona con el CI en rojo.

## Codificación

UTF-8. No editar el repo con `Set-Content` ni `Get-Content` de PowerShell 5.1: relee UTF-8 como ANSI y doble-codifica los acentos. `scripts/check_mojibake.py` lo rechaza.

## Tests y lint

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

Suite en una base desechable (no usa la de producción). Primero el plan contable, porque sin diarios `account.move` no se puede crear. `--test-tags` limita a los módulos propios:

```bash
python scripts/custom_modules.py --csv
python scripts/custom_modules.py --tags
docker exec incoespacio_web odoo -d ci --db-filter=ci -i l10n_es \
  --stop-after-init --without-demo=all --workers=0 --http-port=8099
docker exec -i incoespacio_web odoo shell -d ci --db-filter=ci --no-http \
  --workers=0 --http-port=8097 < scripts/ci_chart.py
docker exec incoespacio_web odoo -d ci --db-filter=ci -i <csv> \
  --test-enable --test-tags <tags> --stop-after-init --without-demo=all \
  --workers=0 --http-port=8099
```

El mismo recorrido lo hace GitHub Actions (`.github/workflows/ci.yml`).

Actualizar módulos ya instalados, sin lista a mano:

```bash
python scripts/update_modules.py
python scripts/update_modules.py incoespacio_theme
```
