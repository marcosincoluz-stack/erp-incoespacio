# Ponytail Audit — `addons-incoespacio/`

- Fecha: 2026-09-08 · Skill: `ponytail-audit` (plugin oficial `@dietrichgebert/ponytail@4.9.0`)
- Alcance: 13 módulos propios (~4.982 líneas). Solo sobre-ingeniería y complejidad; bugs/seguridad/rendimiento van a revisión normal.
- Etiquetas: `delete:` muerte real · `stdlib:`/`native:` ya existe hecho · `yagni:` flexibilidad sin usar · `shrink:` misma lógica, menos líneas.

## Hallazgos (mayor corte primero)

1. `delete:` `report_styles.css` duplica regla por regla el `<style>` inline de `layout_templates.xml` (dos fuentes con valores que ya discrepan). Quédate con el fichero, borra el bloque `<style>` (líneas 109-228). —120 [incoespacio_reports]
2. `delete:` bloque `.olcards` (95% del fichero) no lo referencia ninguna plantilla. Nada. —87 [incoespacio_theme/static/src/css/report_theme.css:6-95]
3. `delete:` selectores heredados del port de Incoluz (Odoo 14), 0 referencias en este ERP: `worksheet_pdf`, `work_note`/`bom_note`, `o_open_tab_cell`, `record_title`, `o_purchase_dashboard`, `o_cp_top_left`, `custom-control`, `ui-menu-item`/`ui-autocomplete`, `o_blockUI`, `o_list_button_add`, reglas vacías `.o_sale_order{}`/`.worksheet_pdf{}` y el bloque huérfano `box-shadow: none;}` (532-533, CSS roto). —70 [incoespacio_theme/static/src/css/backend_theme.css]
4. `shrink:` la subida de ficheros está copiada 3 veces (drawer, wizard, patch): `readFileAsBase64` + límite 25 MB + bucle. `onFilesSelected`≡`onDrop` dentro del wizard. Un helper compartido. —60 [incoespacio_invoice_ocr_ui/static/src/components/]
5. `shrink:` las tarjetas de informes repiten 10 veces el style inline (`#fafbfc; border: 1px solid #e2e8f0...`) cuando `.inco-card`/`.inco-card-title` ya están definidos en el layout y sin usar; los `th`/`td` inline de report_invoice.xml y report_sale_order.xml son idénticos entre sí y además redundantes con el CSS. —50 [incoespacio_reports/report/]
6. `delete:` campos y configs que nadie lee: `ai_ocr_processed` (2 escrituras, 0 lecturas), `ocr_mismatch_type` (viaja al bus pero la UI lo ignora), `ocr_pdf_url` (computeado, sin uso), `it_groups.xml` (grupos sin aplicar en ninguna parte), `ocr_auto_create_partner` y `ocr_default_expense_account_id` (ajustes que ningún `get_param` consulta). —45 [ocr:17,37 · split_view:10 · security · ai_core:22-34]
7. `shrink:` `_create_document_from_attachment` del diario reimplementa el bucle crear+adjuntar+message_post+encolar que ya hace `upload_bills_batch`. Un solo camino. —30 [incoespacio_invoice_ocr_async/models/account_journal.py:54-70]
8. `shrink:` `button_working`/`button_soon`/`button_done` = mismo write+message_post con otro texto. Un `_transition(state, msg_fn)`. —30 [incoespacio_support/models/ticket.py:92-130]
9. `shrink:` bucle de reintentos Gemini a mano (backoff+jitter+429/5xx, 35 líneas) → `HTTPAdapter(max_retries=urllib3.Retry(...))` sobre la Session que ya tenéis. —25 [incoespacio_ai_core/models/ai_ocr_service.py:238-271]
10. `shrink:` `_find_or_create_supplier`/`_find_or_create_customer` son el mismo search-por-vat/nombre + create con ranks invertidos. Una función. —25 [incoespacio_invoice_ocr/models/account_move.py:424-483]
11. `delete:` triple blindaje del menú Odoo.com: `registry.remove` + filtro en `getElements` + CSS `[data-menu]` display:none; además `getIncoluzElements()` (0 llamadores) y `usermenu_template.xml` (fichero vacío cargado en assets). Con el filtro basta. —20 [theme: web_title_widget.js, backend_theme.css:700-710, xml vacío]
12. `shrink:` `app_sidebar.js`: try/catch + `?.` sobre API estable de Odoo 17 (`menuService.getApps`). —19 [incoespacio_theme/static/src/js/app_sidebar.js]
13. `native:` `detect_mimetype` (magic bytes a mano, 21 líneas) → `odoo.tools.mimetypes.guess_mimetype(data, filename)` que ya trae Odoo. —18 [incoespacio_ai_core/models/ai_ocr_service.py:108-130]
14. `native:` cuentas por defecto buscando códigos '600%'/'700%' a mano → el diario ya tiene `default_account_id`/cuentas de contrapartida nativas del asiento. —16 [incoespacio_invoice_ocr/models/account_move.py:485-499]
15. `delete:` reglas CSS duplicadas dentro del propio theme (`.btn-link:hover` dos veces con colores distintos, `.o_form_uri`, `.badge-primary`, `.text-primary` redefinidos con `var(--primary)`). —15 [incoespacio_theme/static/src/css/backend_theme.css:237-285]
16. `shrink:` los dos bucles "otra empresa del grupo" de `_check_fiscal_identity` son idénticos (emisor/receptor). Extraer lambda. —15 [incoespacio_invoice_ocr/models/account_move.py:258-302]
17. `native:` `is_customer`/`is_supplier` como booleanos manuales que nunca se sincronizan con `customer_rank`/`supplier_rank` (los partners creados por el OCR salen sin badge). Cómputo desde los ranks nativos. —10 [incoespacio_partner_is_customer_or_supplier]
18. `shrink:` el HTML de la alerta de discrepancia del chatter (13 líneas de style inline) → `alert alert-warning` de Bootstrap que el theme ya pinta. —10 [incoespacio_invoice_ocr/models/account_move.py:330-342]
19. `native:` `_validate_iban_checksum` a mano (módulo 97) → `schwifty.IBAN(x).is_valid` — schwifty YA está instalado en la imagen y no se importa en ningún sitio: o se usa o se quita del Dockerfile. —9 [incoespacio_invoice_ocr/models/account_move.py:553-560]
20. `yagni:` `ticket_type.color` se configura pero no se pinta en ningún ticket/kanban. —8 [incoespacio_support]
21. `delete:` `paperformat_data.xml` crea un paperformat propio Y reescribe `base.paperformat_euro` con los mismos márgenes; dos fuentes de verdad. —6 [incoespacio_reports/data/paperformat_data.xml]
22. `delete:` ramas `this.env.searchModel` en componentes main (drawer/wizard): un main component no tiene searchModel, siempre cae al `?:{}`. —4 [incoespacio_invoice_ocr_ui]
23. `stdlib:` limpieza de ```json fences con 3 ifs → `clean_text.removeprefix('```json').removeprefix('```').removesuffix('```').strip()`. —4 [incoespacio_ai_core/models/ai_ocr_service.py:294-300]
24. `delete:` `from datetime import datetime, timedelta` sin uso. —1 [incoespacio_support/models/ticket.py:3]
25. `yagni:` módulo `incoespacio_invoice_notes` completo: `account.move.narration` ya es la nota interna nativa. Si se quiere página aparte, heredar y mostrar `narration`, no un campo clon. —51 (módulo) [incoespacio_invoice_notes]

## Verificados y NO marcados

- `incoespacio_invoice_date`: el core 17 no tiene `@api.onchange('invoice_date')` que sincronice `date` → el módulo aporta. Se queda.
- `_get_edi_decoder`: lo llama el core (account/models/account_move.py:3277) en la digitalización de adjuntos → vivo.
- `web_responsive` sí está instalado (addons/web-oca) → el `home-menu-bg-overlay.svg` del theme es válido.
- Workers OCR en hilo + cron de respaldo cada 2 min: redundancia intencionada (hilo muere con el proceso), no es bloat.

## Nota fuera de alcance (para revisión normal)

- `_get_edi_decoder(self, file_data, filename=None)` no acepta el kwarg `new=` con el que lo llama el core → TypeError en esa ruta.
- `sequence_data.xml` fija el diario `account.1_sale` (xmlid de demo) con `noupdate="0"` → sobreescribe edición del usuario en cada upgrade.
- `:focus-visible { outline: none !important }` elimina el foco de accesibilidad.

## Net

`net: -740 líneas, -1 dep (schwifty, o úsalo), -1 módulo (invoice_notes) posibles.`

---

# Cierre (2026-09-08, tandas B1-B9 aplicadas)

Git: repo local iniciado con lista negra de secretos; commits por tanda `a8088f0..HEAD`.
Diff final: **33 ficheros, +329 / −905 = net −576 líneas** (incluye el módulo `incoespacio_invoice_notes` desinstalado y borrado).

## Estado por hallazgo

- 1 CSS duplicado informes → aplicado (B2): `report_styles.css` fuente única, `<style>` inline fuera.
- 2 `.olcards` → aplicado (B1).
- 3 selectores legacy → aplicado PARCIAL (B1): tras verificar contra el core 17, `o_blockUI`, `o_list_button_add` y `o_purchase_dashboard` están VIVOS y se quedaron; fuera `worksheet_pdf`, `work_note/bom_note`, `o_open_tab_cell`, `record_title`, `o_cp_top_left`, `custom-control`, clases de chat ≤15, reglas vacías y el bloque CSS roto de la 532.
- 4 subida JS x3 → aplicado (B3): `ocr_upload_utils.js` compartido.
- 5 tarjetas/th/td inline → aplicado (B2): clases `.inco-card`/`.inco-card-title` y CSS.
- 6 campos/configs muertos → aplicado (B5/B8): `ai_ocr_processed`, `ocr_mismatch_type`, `ocr_pdf_url`, `it_groups.xml`; los 2 ajustes Gemini muertos verificados y… ver nota.
- 7 diario duplica creación → aplicado (B6): `_create_move_with_attachment`.
- 8 botones ticket → aplicado (B7): `_transition`.
- 9 retry a mano → aplicado (B4): `urllib3.Retry`.
- 10 find_or_create x2 → aplicado (B5): `_find_or_create_partner`.
- 11 triple blindaje menú → aplicado (B1): `registry.remove` + CSS; filtro JS, renames de items ocultos, `getIncoluzElements` y `usermenu_template.xml` fuera.
- 12 app_sidebar ruido → aplicado (B1).
- 13 detect_mimetype → aplicado (B4): `guess_mimetype` del core.
- 14 cuentas 600/700 → aplicado (B5): cuenta nativa del asiento/diario.
- 15 CSS duplicado theme → aplicado (B1).
- 16 bucles fiscal x2 → aplicado (B5): `_match_other_company`.
- 17 is_customer/is_supplier → aplicado (B8): compute+inverse desde `customer_rank`/`supplier_rank`.
- 18 alerta chatter inline → aplicado (B5): `alert alert-warning`.
- 19 IBAN a mano → aplicado (B5): `schwifty.IBAN`.
- 20 ticket_type.color → aplicado (B7).
- 21 paperformat doble → aplicado (B2).
- 22 ramas searchModel → aplicado (B3).
- 23 fences → aplicado (B4).
- 24 import datetime → aplicado (B7).
- 25 invoice_notes → aplicado (B9): desinstalado (0 filas de datos) y carpeta borrada.

Nota hallazgo 6: los ajustes `ocr_auto_create_partner` y `ocr_default_expense_account_id` siguen en `res.config.settings` (se decidió no tocar la UX de Ajustes en esta pasada); quedan como deuda conocida: o se cablean en la lógica o se retiran.

## ponytail-review del diff (skill oficial)

3 hallazgos, los 3 aplicados en el commit de cierre: `Retry(connect/read)` redundante, splat condicional `journal_id`, `{ context: {} }` en `orm.call`. `net: -3 lines` incluido en el −576.

## ponytail-debt (skill oficial)

1 marcador `ponytail:` (comment de chatter en ocr/account_move.py:528) sin ceiling ni trigger → no era deuda real (describía una reducción ya hecha), retirado. Ledger: **0 markers. Clean ledger.**

## Verificación

- Upgrades `-u` por tanda sin WARNING/ERROR; `web: 200` tras cada restart.
- PDFs de factura y pedido renderizan (`%PDF`, 94 KB / 1,2 KB) tras B2.
- Columnas `ai_ocr_processed`/`ocr_mismatch_type` confirmadas fuera de `information_schema`.
- Grupos IT huérfanos eliminados por el propio upgrade.

---

# Frente theme CSS + modularidad (2026-09-08, tarde)

## Conversión SCSS (commit e2b1a15)
- `backend_theme.css` (771 líneas, 209 `!important`) → `backend_theme.scss` (583 líneas, 15 `!important`).
- Los 15 restantes pelean con especificidad alta/inline del core (sheet redimensionable, modales, chatter 30%, attachment viewer, blindaje de marca); el resto gana por cascada: el SCSS propio carga después del core en `web.assets_backend`.
- Reglas de color eliminadas por redundantes: las variables SCSS (`$o-brand-primary`, `$o-action`, `$o-component-active-*`, mapa `$o-btns-bs-override`, `$form-check-input-checked-bg-color`, `$link-color`) ya producían el azul; solo quedan los añadidos de diseño (mayúsculas, hover exacto, focus).
- Navbar vía custom properties `--NavBar-*` sin `!important` (el `navbar.scss` del core no usa ninguno).
- Bonus: fuera `:focus-visible { outline: none !important }` (devuelve el foco de accesibilidad nativo).
- Verificado: bundle `web.assets_backend` compila (949 KB, theme presente); web 200.

## Congelaciones y política (commit C2)
- `report_styles.css`: 53 `!important` CONGELADOS con cabecera que explica el porqué (wkhtmltopdf, PDF legal). No es deuda: es una excepción aceptada.
- `AGENTS.md`: política de micro-modularidad (módulos nuevos ≤ ~500 líneas, un propósito; comprobar encaje antes de crear) con las tres excepciones documentadas (theme, familia OCR, reports). La media 380 líneas/módulo frente a los 173 de Incoluz queda explicada por esas excepciones, no perseguida con splits artificiales.

## Métricas tras el frente theme
- `!important` propios: 268 → 74 (15 backend + 53 reports congelados + 5 frontend + 1 report_theme).
- `incoespacio_theme`: 976 → ~788 líneas.
- `addons-incoespacio/`: 4.560 → ~4.372 líneas desde el pre-audit (5.136): −14,9%.
