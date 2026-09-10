# Handoff — Incoluz OCR de Facturas con IA (Odoo 14)

Módulo: `incoluz_invoice_ai_ocr` v14.0.1.0.0 — port (foto fija) de la suite `incoespacio_invoice_ocr` de Odoo 17.
Las mejoras posteriores de 17 NO se auto-portan: este módulo es una línea base independiente.

## Instalación en producción
1. Descomprimir/copiar `incoluz_invoice_ai_ocr` en un directorio del `addons_path`.
2. Reiniciar el servicio Odoo y actualizar la lista de aplicaciones.
3. Instalar `Incoluz: OCR de Facturas con IA (Gemini)` (depende solo de `account` y `mail`).
   **No requiere ningún `pip install`**: PyPDF2 ya viene en la imagen oficial odoo:14 y el
   checksum IBAN va embebido.
4. Ajustes → Facturación → *Digitalización OCR de Facturas con IA*: pegar la clave de Google
   Gemini y guardar.
5. Reiniciar no es necesario tras guardar la clave.

## Checklist de validación en staging (antes de producción)
- [ ] Facturación → *Digitalizar facturas con IA* → subir 1 PDF real → el cajón inferior derecho
      muestra progreso y termina en verde; el borrador tiene proveedor, líneas, IVA y total.
- [ ] Sin clave configurada: el escaneo devuelve error amable indicando dónde configurarla.
- [ ] Factura de otra empresa (editar el CIF del emisor en el PDF de prueba o forzar datos):
      alerta ámbar de discrepancia + botón *Forzar procesado de todos modos* funciona.
- [ ] IBAN: subir factura con IBAN ya conocido del proveedor → estado IBAN "Coincide";
      IBAN nuevo válido → se da de alta en el proveedor; IBAN del proveedor distinto → alerta roja.
- [ ] Duplicada: subir dos veces la misma factura → alerta de duplicada con enlace.
- [ ] Multi-factura: PDF con 2 facturas → se crean 2 borradores con sus páginas partidas.
- [ ] Cron: dejar un borrador en cola y reiniciar el servidor → el cron lo procesa en ≤2 min.
- [ ] Multi-compañía: usuario con una sola compañía sube factura de otra compañía del grupo →
      discrepancia detectada (el sudo de res.company es intencionado).

## Notas de operación
- El módulo crea **borradores**; nunca publica facturas automáticamente.
- El cajón inferior consulta cada 4 s solo mientras hay trabajo visible (coste despreciable,
  sin longpolling/websocket: válido aunque el nginx de producción no proxye /longpolling).
- Límite 25 MB por archivo en el asistente.
- Los hilos de procesado arrancan post-commit: cerrar el navegador no cancela el trabajo;
  el cron de 2 min es la red de seguridad si el proceso muere a mitad.

## Divergencia con Odoo 17
- Sin capa bus/websocket (14 usa longpolling con API distinta): solo polling.
- Wizard clásico TransientModel en vez del diálogo OWL 2 con drag & drop.
- IBAN con mod-97 embebido (17 usa schwifty).
- Cuentas de línea: diario.default_account_id + fallback por tipo (17 usa el compute nativo de 17).
