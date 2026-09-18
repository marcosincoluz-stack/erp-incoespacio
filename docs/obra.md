# Obra: decisiones y espera

- Fecha: 2026-09-14
- Premisa: el presupuesto y la medición legal salen de Presto. Odoo consume ficheros, no sustituye a Presto.
- Código: módulos en `addons-incoespacio/extras/` (certificaciones, BC3, OCR obra/partida). Submódulo nuevo si no es el propósito del base.

Los fallos que prioricemos se añaden abajo. Sin muestra o sin “sí, esto nos duele”, no se construye.

---

## Ya en el ERP

- Cabecera fija de partidas en la certificación.
- Lupa que salta (no filtra): `incoespacio_construction_certification_search`.
- Retención por defecto **0 %** en certificaciones nuevas (el 5 % a mano). Las ya creadas no se tocan.
- Imputar factura de proveedor a capítulo y/o partida, con reparto: `incoespacio_invoice_ocr_obra_partida`.
- Candado al publicar: factura/abono de proveedor exige obra o «No es de obra».
- Pedido: coste obra, imputado a capítulo, sin capítulo; columna Coste por partida.
- OCR: empate de palabras = vacío; pegajoso de proveedor a la última UO de esa obra.
- Pedido de compra: partida en la línea (`incoespacio_invoice_ocr_obra_purchase`); *Comprometido* al lado del margen (no entra en el coste).
- Wizard de reparto: la primera línea sale a importe 0 (queda el restante); al añadir otra vacía, copia lo que falta.
- Filtro *Gastos sin partida* (factura de proveedor publicada con obra y línea de producto sin UO). Desde Márgenes, *Sin imputar a partida* abre ese filtro de la obra.
- Imputar a partidas en factura **publicada**: escribe la UO, no parte el asiento. Partir importes sigue siendo las tijeras en borrador.
- Certificación: *Aprobar y crear factura* (si la factura falla tras aprobar, se queda en Aprobada).
- Un pedido confirmado por obra. Reimportar BC3 avisa: crea otro pedido, no actualiza el presupuesto abierto.

---

## Esperando un BC3 real (no construir)

### Precio objetivo / coste previsto

El importador toma el último precio `~C` → `price_unit` (venta). El coste de obra en el ERP es el de facturas de proveedor publicadas, no el objetivo de Presto.

El BC3 de Presto 8.8 que vimos (`venta\objetivo`) no traía segunda naturaleza. Hasta que haya un export que sí la traiga, no hay nada que parsear.

### Mediciones (`~M`) → `Med. Origen`

El origen legal sigue en Presto. En Odoo se pisa `Med. Origen` a mano. Un BC3 de **presupuesto** no es una certificación hecha.

Hoy:

- El importador solo lee `V/C/D/T`. Ignora `~M`.
- `Nueva certificación` copia la medición de la cert. anterior; el jefe escribe el origen.
- En `~V` ya hay número y fecha de certificación (`bc3_certification_number` / `bc3_certification_date`), pero no crean un `construction.certification`.

FIEBDC sí contempla un BC3 de certificación (mismo presupuesto, a menudo `obra#certificación NNNN`), con `~M` y `MEDICION_TOTAL` por partida. Ese total es `Med. Origen`, no el desglose 3×4×2.

Cómo se haría, cuando haya fichero:

1. Preguntar al jefe de obra: ¿exportáis de Presto un BC3 **de la certificación** o solo el presupuesto? Si no exportan cert, no hay import.
2. Hace falta **un `.bc3` real** de una cert. 1 o 2 de una obra vuestra.
3. Submódulo (`incoespacio_construction_certification_bc3`): botón en el pedido *Importar certificación BC3*. Detecta `~V`, lee totales `~M` por código, rellena un **borrador** de certificación. No crea otro pedido. No pisa certs ya facturadas.
4. Solo el total por `bc3_code`. Códigos que no casen (nuevo, modificado) a lista de revisión.
5. Humano al final: aprobar y facturar siguen siendo clics de ahora. La IA no escribe origen.

Qué no: editar mediciones en Odoo y devolverlas a Presto; reimportar el presupuesto entero cada mes; parsear `~M` al crear el pedido si la cantidad ya viene del `~D`.

---

## Coste / margen / imputación (hecho)

El margen sigue siendo **último certificado facturado − facturas de proveedor publicadas con obra**. No hay motor de costes previstos ni IA por línea.

Sigue igual a propósito:

- Facturas ya publicadas sin obra: el filtro *Gastos sin obra*. No se migran.
- «No es de obra» marcado mal: el candado no lo ve.
- No se bloquea por falta de capítulo (el ferretería a veces solo sabe el tajo).
