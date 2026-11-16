# Facturae desde el correo

Si el buzón de facturas trae un XML **Facturae 3.2.x**, se lee aquí, sin Gemini. El resultado es el mismo diccionario que usa el OCR, así que la clasificación por CIF, las líneas, la revisión y la sugerencia de obra siguen en los módulos que ya existen.

Un PDF sigue por la cola de IA. Un XML que no es Facturae deja el borrador en **Facturas por revisar** con el motivo «XML no legible». El buzón no se para.

Un abono (`InvoiceClass` OR o CR) entra como rectificativa. La misma factura en PDF y en XML, con distinto adjunto, se marca duplicada por CIF emisor y número.

Un lote con varias facturas solo aplica la primera y lo avisa en el chatter. Partir el lote cuando aparezca uno de verdad.

UBL, CII y la firma XAdES quedan fuera.
