# Buzón de facturas y OCR — mejoras candidatas tras rodar en real

- Fecha: 2026-11-15
- Para: contabilidad / administración / IT (no es un plan cerrado)
- Premisa: **no tocar código hasta rodar 1-2 semanas con correo real en Outlook** y ver qué casos aparecen de verdad.
- Puesta en marcha actual: [`addons-incoespacio/extras/invoice/incoespacio_invoice_ocr_mail/README.md`](../addons-incoespacio/extras/invoice/incoespacio_invoice_ocr_mail/README.md).

---

## Mejoras candidatas

### 1. Abonos y facturas rectificativas (`in_refund` / `out_refund`)

- **Problema hoy**: cualquier abono entra como factura ordinaria (`in_invoice` o `out_invoice`).
- **Cuándo compensa**: en cuanto empiecen a entrar abonos reales por correo o por subida manual.
- **Dónde tocar**:
  - `addons-incoespacio/incoespacio_ai_core/models/ai_ocr_service.py`: añadir `"es_rectificativa": false` al esquema JSON del prompt de Gemini e indicar que normalice cantidades y precios unitarios en positivo.
  - `addons-incoespacio/extras/invoice/incoespacio_invoice_ocr/models/account_move.py`: asegurar importes de línea positivos cuando el documento sea rectificativo para que Odoo no invierta el signo dos veces.
  - `addons-incoespacio/extras/invoice/incoespacio_invoice_ocr_mail/models/account_move.py`: en `_ocr_mail_set_kind`, asignar `in_refund` / `out_refund` si `es_rectificativa` es `true`, y dejar botones de revisión para rectificativas si hiciera falta forzarlas a mano.

### 2. Aviso de descuadre entre el total del PDF y el calculado por Odoo

- **Problema hoy**: el OCR crea las líneas, aplica IVA/IRPF y marca el borrador como `done` sin comprobar si `amount_total` coincide con `factura.total` del PDF. Con descuentos por línea, suplidos exentos, portes o varios tipos de IRPF puede quedar un borrador con un total distinto sin saltar alerta.
- **Cuándo compensa**: si al revisar borradores aparecen diferencias de importe que contabilidad tiene que cazar a ojo.
- **Dónde tocar**:
  - `addons-incoespacio/extras/invoice/incoespacio_invoice_ocr/models/account_move.py`: al final de `_apply_ai_extracted_data`, comparar `abs(self.amount_total - total_factura) > 0.02`; si difiere, dejar nota en el chatter con ambos importes y pasar a revisión (`ocr_status = "review"`, motivo `total_mismatch`).
  - `addons-incoespacio/extras/invoice/incoespacio_invoice_ocr_mail/views/account_move_views.xml`: añadir el motivo `Descuadre de total` en el aviso y en los filtros de **Facturas por revisar**.

### 3. Limpieza rápida en «Facturas por revisar» y listado de proveedores

- **Problema hoy**: cuando entra un albarán, presupuesto o publicidad (`not_invoice`) o un duplicado claro (`duplicate_file`), hay que entrar y cancelar/borrar a mano; además, los borradores del correo aún pendientes o sin clasificar (`unknown_type`) asoman también en la lista general de Facturas de proveedor.
- **Cuándo compensa**: si entran varios documentos no contables por semana o si a contabilidad le estorban los borradores sin clasificar en la vista de proveedores.
- **Dónde tocar**:
  - `addons-incoespacio/extras/invoice/incoespacio_invoice_ocr_mail/views/account_move_views.xml`: botón `Descartar` (`button_cancel`) directo en la franja amarilla para `not_invoice`, `duplicate_file` y `no_attachment`, y filtro por defecto en la acción de Facturas de proveedor para ocultar los borradores `ocr_from_mail` mientras estén en `pending` o `unknown_type`.

### 4. Fotos de facturas desde móvil (`JPEG` / `PNG`)

- **Problema hoy**: `AiOcrService` ya sabe enviar imágenes a Gemini, pero el buzón mueve a `Odoo-Ignorados` cualquier correo sin PDF ni XML (y `account.move` filtra imágenes por defecto).
- **Cuándo compensa**: solo si desde obra o compras van a mandar fotos de tickets/facturas al buzón y contabilidad las quiere ahí.
- **Dónde tocar**:
  - `addons-incoespacio/extras/invoice/incoespacio_invoice_ocr_mail/models/fetchmail_server.py` y `account_move.py`: aceptar `image/jpeg` e `image/png` únicamente cuando sean adjuntos reales (`Content-Disposition != "inline"`) y superen un umbral mínimo de tamaño (p. ej. 25 KB) para no tragar logos de firma.

---

## Qué descartamos a propósito

- **Contabilizar automáticamente (`action_post` sin revisión humana)**: un error de lectura de IVA, cuenta de gasto u obra pasaría directo al libro diario. El borrador ya quita casi todo el tecleo sin asumir ese riesgo.
- **Descargar facturas desde enlaces de portales («Descarga tu factura aquí»)**: eléctricas, telecos y gasolineras piden login o cambian el HTML cada pocos meses; mantener scrapers rompe más de lo que ahorra. En esos proveedores conviene activar el envío del PDF adjunto en su portal de cliente.

---

## Qué mirar las primeras dos semanas en producción

1. **Carpeta `Odoo-Ignorados` en Outlook**: ver si caen ahí fotos desde obra o correos de proveedores que solo mandan enlace sin PDF.
2. **`Contabilidad > Facturas por revisar`**: contar cuántas entran como `No es una factura`, `Tipo desconocido` o `PDF duplicado`, y si llegan abonos.
3. **Validación de borradores**: anotar cualquier factura donde el total calculado por Odoo no cuadre al céntimo con el PDF original.
