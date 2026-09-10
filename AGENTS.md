# Project Guidelines

## Ponytail
Usamos el ponytail oficial del repo, no resúmenes a mano:
- Plugin de opencode: `@dietrichgebert/ponytail` (declarado en `opencode.json`).
- Fuente de verdad del ruleset y los skills: https://github.com/DietrichGebert/ponytail
- Comandos: `/ponytail` (nivel lite|full|ultra|off), `/ponytail-review`, `/ponytail-audit`, `/ponytail-debt`.
- Alcance del audit propio: `addons-incoespacio/`.

## Micro-modularidad
- Layout de `addons-incoespacio/` (espejo de Incoluz): módulos transversales en la raíz (`theme`, `security`, `support`, `reports`, `ai_core`) y módulos de dominio bajo `extras/<dominio>/` (`invoice`, `partner`, `purchases`). Odoo solo escanea el primer nivel de cada entrada de `addons_path`: las carpetas `extras/*` están declaradas en `config/odoo.conf` y `config/odoo.conf_example`.
- Módulos nuevos: ≤ ~500 líneas y un solo propósito de negocio. Antes de crear uno, comprobar si encaja en uno existente.
- Excepciones documentadas: `incoespacio_theme` (chrome corporativo completo), familia OCR (`incoespacio_invoice_ocr` / `_async` / `_ui` = una suite de negocio por capas), `incoespacio_reports` (factura + pedido legales y paperformat).
- Theme backend: los colores vienen de las variables SCSS del core (`primary_variables.scss`); `backend_theme.scss` solo viste chrome sin variable y carga tras el core (cascada, no `!important`).
- CSS de informes (`report_styles.css`): `!important` congelados a propósito (wkhtmltopdf, PDF legal).

## Tooling
- Nunca editar ficheros del repo con `Set-Content`/`Get-Content` de PowerShell 5.1: relee UTF-8 sin BOM como ANSI y doble-codifica los acentos (mojibake en PDFs y vistas). Usar las tools de edición o python leyendo/escribiendo bytes.
