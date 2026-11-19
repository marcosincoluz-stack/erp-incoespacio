# Producto en las líneas del OCR

Cuando el OCR o un Facturae crea las líneas, este módulo intenta poner el producto y deja siempre el precio y la etiqueta del documento.

Aprende de las facturas ya contabilizadas del mismo proveedor o cliente. Compara el texto de la línea, sin números, sin el código de obra y sin el mes. Hace falta que un producto gane con claridad: al menos dos palabras, o una sola si coincide exactamente, y 0,15 de margen sobre el siguiente. Si no hay historial o la duda es grande, la línea queda sin producto. La primera factura de cada contacto se elige a mano y, una vez contabilizada, sirve de ejemplo.

El precio no vuelve a 0 € al elegir el producto, ni a mano ni al asignarlo aquí. La cuenta y el IVA salen de la ficha, pasados por la posición fiscal del contacto (inversión del sujeto pasivo, intracomunitario). Si la ficha no tiene IVA, se queda el del PDF. Si el PDF trae IRPF y la ficha no, se añade. Si el porcentaje del IVA no coincide, la factura pasa a **Facturas por revisar** con el motivo «IVA distinto al PDF». Si el total de Odoo no cuadra con el del documento en más de dos céntimos, el motivo es «El total no cuadra con el PDF».

En la ficha del producto, pestaña Contabilidad, tiene que estar la **Cuenta de gastos** (en una gestoría, servicios profesionales, no compras de mercaderías). Si está vacía, Odoo usa la cuenta por defecto.
