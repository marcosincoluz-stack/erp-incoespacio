# Project Guidelines

## Ponytail
Usamos el ponytail oficial del repo, no resúmenes a mano:
- Plugin de opencode: `@dietrichgebert/ponytail` (declarado en `opencode.json`).
- Fuente de verdad del ruleset y los skills: https://github.com/DietrichGebert/ponytail
- Comandos: `/ponytail` (nivel lite|full|ultra|off), `/ponytail-review`, `/ponytail-audit`, `/ponytail-debt`.
- Alcance del audit propio: `addons-incoespacio/`.

## Micro-modularidad
- Layout de `addons-incoespacio/` (espejo de Incoluz): módulos transversales en la raíz (`theme`, `security`, `support`, `reports`, `ai_core`) y módulos de dominio bajo `extras/<dominio>/` (`invoice`, `partner`, `purchases`, `sales`). Odoo solo escanea el primer nivel de cada entrada de `addons_path`: las carpetas `extras/*` están declaradas en `config/odoo.conf` y `config/odoo.conf_example`.
- Estándar OCA: un módulo, un propósito. Toda característica nueva propia es un **submódulo** que depende del de negocio (`depends: [modulo_base]`), no un volcado en el módulo ya instalado. Misma carpeta de dominio (`extras/invoice/`, etc.). Nombre técnico: `incoespacio_<base>_<feature>` (como la familia OCR). Tope ~500 líneas.
- En el módulo base solo entra lo que es el propósito original, un bugfix de ese propósito, o un ajuste sin el cual esa función no se puede usar. Si se puede instalar o no a parte, es submódulo.
- Módulos de la OCA / comunitarios: ubicados en `addons/`, no están sujetos a la limitación de 500 líneas al ser componentes estándar del ecosistema. Si se porta o adapta un módulo de la OCA para Incoespacio, se mantiene su integridad estructural comunitaria.
- Excepciones documentadas propias: `incoespacio_theme` (chrome corporativo completo), familia OCR (`incoespacio_invoice_ocr` / `_async` / `_ui` / `_obra` = extraer factura + imputar gasto a obra/capítulo), `incoespacio_reports` (factura + pedido legales y paperformat), port OCA `bc3_importer` en `extras/sales/` (17 no está mergeado en OCA; parches locales; mismo nombre técnico/AGPL/autores), suite de obra `incoespacio_construction_certification` (certificaciones a origen, retención 4308, proyecto, coste/margen, modificados).
- Theme backend: los colores vienen de las variables SCSS del core (`primary_variables.scss`); `backend_theme.scss` solo viste chrome sin variable y carga tras el core (cascada, no `!important`).
- CSS de informes (`report_styles.css`): `!important` congelados a propósito (wkhtmltopdf, PDF legal).

## Tooling
- Nunca editar ficheros del repo con `Set-Content`/`Get-Content` de PowerShell 5.1: relee UTF-8 sin BOM como ANSI y doble-codifica los acentos (mojibake en PDFs y vistas). Usar las tools de edición o python leyendo/escribiendo bytes.
