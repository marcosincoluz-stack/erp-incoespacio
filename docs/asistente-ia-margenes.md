# Plan: IncoBot analiza márgenes hasta la partida

Estado: sprint 1 hecho (2026-11-27); falta que el usuario mire la pantalla de márgenes. Solo en local, como el resto del asistente.

## 1. Qué se quiere

Que IncoBot use la IA a fondo para entender la economía de las obras: no solo «qué obra pierde», sino **dónde** (capítulo, partida), **por qué** (sobrecoste, coste sin avance, imputación pendiente, comprometido por encima de lo previsto) y **qué mejorar**, y que compare entre obras («¿en qué obra nos sale más cara la tabiquería?»). Y que avise solo, sin que nadie pregunte, cuando algo se desvía.

Pedido por el usuario (2026-11-27). Quedan fuera por ahora: puntuación de trabajadores y previsión de compras / «a quién llamar».

## 2. Lo que ya hay en el ERP

Los datos existen, partida a partida (`sale.order.line`), en módulos que ya están en el repo:

| Dato | Campo | Módulo |
|---|---|---|
| Capítulo | `bc3_section_id` | `incoespacio_construction_cost` |
| Código BC3 | `bc3_code` | `bc3_importer` |
| Venta (medición × precio) | `product_uom_qty`, `price_unit`, `price_subtotal` | Odoo |
| Coste objetivo y precio objetivo | `amount_planned`, `price_planned` | `incoespacio_bc3_planned_cost` |
| Certificado a origen, avance % | `amount_cert_origin`, `progress_percent` | `incoespacio_construction_margins` |
| Objetivo ejecutado | `amount_planned_done` | `incoespacio_construction_margins` |
| Coste real imputado, P.U. real | `amount_vendor_cost`, `price_unit_real` | `incoespacio_construction_cost` / `_margins` |
| Desviación (objetivo ejecutado − coste) | `amount_cost_deviation` | `incoespacio_construction_margins` |
| Margen y % | `amount_margin`, `margin_percent` | `incoespacio_construction_margins` |
| Comprometido, incurrido, previsión a fin de obra | `amount_po_cost`, `amount_cost_incurred`, `amount_cost_forecast`, `amount_margin_forecast` | `incoespacio_construction_margins_forecast` |

A nivel obra, lo mismo agregado (`amount_cost_unassigned`, `amount_cost_deviation`, `amount_margin_forecast`…).

Casi todos son **campos calculados** (no guardados): no se pueden filtrar ni sumar en la base de datos. Hoy el catálogo los lee hasta 200 registros y solo sabe ordenar y filtrar por ellos, no sumarlos.

**La demo no sirve todavía**: sus obras tienen 5 partidas sin capítulos y no tiene instalados el coste objetivo, los márgenes ni la previsión. En `pruebas/obras/` hay 4 presupuestos BC3 con capítulos y facturas (con `generar.py`), que se pueden usar y ampliar.

## 3. Enfoque

Tres piezas, cada una para lo que hace bien (revisado el 2026-11-27 con el usuario: **la IA razona con los datos, no lee un informe hecho por código**):

1. **Catálogo hasta la partida** (`consultar`): preguntas libres y comparaciones. Entradas nuevas `partidas` y `capitulos`. Hace falta una capacidad nueva: **agrupar y sumar campos calculados** (sumar el coste por capítulo) leyendo los registros, con tope.
2. **Datos de detalle para razonar** (en vez de una herramienta `analizar_obra`, descartada): la IA tiene que poder investigar el porqué por sí misma, también lo que nadie ha previsto. Para eso necesita (a) el detalle, no solo totales: las líneas de factura de proveedor de cada partida (`gastos`), las líneas de pedido de compra (`compras_partidas`) y lo certificado por periodo (`certificaciones_partidas`); (b) entender qué significa cada dato (definiciones en el catálogo y pautas de cómo investigar, no reglas que decidan por ella); y (c) margen para investigar: más consultas por pregunta (de 4 a 8). Los datos tienen que ser honestos: sin coste objetivo no hay desviación (no «− todo el coste»).
3. **Aviso de desviación** (reglas, no IA): un tipo de aviso nuevo cuando un capítulo o una partida se desvía más de un umbral, al jefe de obra y a Dirección, con la comprobación al momento y el tachado que ya existen.

Por qué así: lo que tiene que ser exacto e igual para todos (los datos, los avisos) lo calcula el código; el análisis es de la IA, con acceso al detalle y sin un guion que la limite. La seguridad no cambia: todo pasa por el catálogo, como el usuario, en solo lectura, con la lista negra y con coste y margen solo para Facturación.

## 4. Seguridad y coste

- Igual que el catálogo: solo lectura, como el usuario, lista negra.
- Coste, margen, desviación, comprometido y previsión solo con **Facturación** (si no, saldrían calculados con lo que ve cada uno y engañarían). Venta, medición y avance, con los permisos de ventas.
- **Topes**: `partidas` y `capitulos` piden filtrar por obra (o por código / descripción para comparar entre obras), para no leer miles de líneas. Tope propio de lectura por entrada (p. ej. 2.000 líneas) y como mucho 50 filas o 30 grupos de vuelta.
- Las entradas de detalle (`gastos`, `compras_partidas`, `certificaciones_partidas`) piden filtrar por obra, partida o documento, y entran en el test de oro como el resto. Importes y precios de proveedor, solo con Facturación.
- Más consultas por pregunta (8) solo encarecen las preguntas de análisis (unos 0,005–0,01 €); las sencillas siguen con 1 o 2.

## 5. Sprints

Cada sprint se cierra con la suite en verde, el tope de 500 líneas por módulo, la demo actualizada y la revisión del usuario.

### Sprint 1 ✅: demo realista

- Instalar en la demo `incoespacio_bc3_planned_cost`, `incoespacio_construction_margins` y `_forecast` (comprobar antes que están en producción y con qué versión).
- Cargar 3 o 4 obras desde los BC3 de `pruebas/obras/` (ampliados con `generar.py` si se quedan cortos): capítulos, partidas, coste objetivo, certificaciones con medición a origen, facturas de proveedor imputadas a partida y pedidos de compra.
- Desviaciones a propósito para poder probar: una partida con sobrecoste, coste sin avance, coste sin imputar, un capítulo que se come el margen, una obra sana.
- Prueba: el usuario abre la pantalla de márgenes de esas obras y los números tienen sentido.

### Sprint 2 ✅: catálogo hasta la partida

- Entradas `partidas` (por obra, capítulo, código, descripción; venta, objetivo, avance, certificado, coste, desviación, margen, P.U. real, comprometido, previsión) y `capitulos`.
- Capacidad nueva: agrupar y sumar campos calculados leyendo los registros (con tope), y filtro obligatorio por entrada.
- Tests: sumas por capítulo que cuadran con la pantalla de márgenes, tope, filtro obligatorio, permisos (test de oro).
- Prueba: «¿qué capítulo de Calle Mayor 12 va peor?», «¿qué partidas tienen sobrecoste?», «¿cuánto llevamos gastado en albañilería?».

### Sprint 3: datos para razonar (sustituye a `analizar_obra`)

- Desviación honesta: una partida sin coste objetivo no tiene desviación (hoy sale «− todo el coste»).
- Entradas `gastos` (líneas de factura de proveedor de la obra, con o sin partida), `compras_partidas` (líneas de pedido) y `certificaciones_partidas` (medición por periodo).
- Definiciones completas y pautas de investigación en el catálogo («para explicar una desviación, mira precio real frente a objetivo, avance frente a coste, las facturas y compras de la partida y la misma partida en otras obras»).
- Hasta 8 consultas por pregunta.
- Tests de las entradas nuevas y de oro; batería con preguntas «¿por qué?» sobre las obras del sprint 1 (pavimento caro, lijado sin avance, factura sin imputar, capítulo 02 de la oficina, pedido caro de la cafetería): la IA tiene que encontrar cada causa por sí sola.
- Prueba: «¿por qué va mal Albañilería?», «¿qué podemos mejorar en la obra X?», «¿por qué pierde dinero la obra Y?».

### Sprint 4: comparar entre obras

- Comparar la misma partida (por código BC3 o descripción) o el mismo capítulo entre obras: P.U. real frente a objetivo, % de margen.
- Prueba: «¿en qué obra nos sale más cara la tabiquería?», «¿qué capítulo suele desviarse más?».

### Sprint 5: aviso de desviación

- Tipo de aviso nuevo (reglas): capítulo o partida con desviación por encima de un % y de un importe mínimo, al jefe de obra y a Dirección. Comprobación al momento, tachado al imputar o certificar (ganchos en líneas de factura y certificaciones).
- Umbrales en Ajustes > IncoBot.

### Sprint 6: batería, prueba y documentación

- Ampliar `scripts/assistant_eval.py` con preguntas de márgenes, con la respuesta esperada calculada.
- Prueba del usuario como Dirección y como jefe de obra. README y notas.

## 6. Por decidir

1. **¿Están en producción** el coste objetivo, los márgenes y la previsión, y se rellena el coste objetivo en todas las obras? Sin coste objetivo no hay desviación (solo margen real).
2. **Datos de la demo**: los BC3 de `pruebas/obras/` (generados) o un BC3 real vuestro anonimizado.
3. **Umbrales del aviso** (sprint 5): p. ej. desviación > 10 % y > 500 €; y quién lo recibe.
4. **Qué ve cada rol** (pendiente de la fase 2): con esto, quién ve costes y márgenes por partida.

## 7. Límites

- Los números son los del ERP: si las facturas no están imputadas a partida, el coste aparece como «sin imputar» y el análisis lo dirá, pero no puede adivinar a qué partida va.
- Las sugerencias de mejora son de la IA a partir de los datos: orientan, no sustituyen el criterio del jefe de obra.

## 8. Notas

- Sprint 1 (2026-11-27): instalados en la demo `incoespacio_bc3_planned_cost` y, solos por `auto_install`, `incoespacio_construction_margins`, `_forecast` y `_list`. Script `scripts/assistant_demo_margins.py` (fuera de git; se puede relanzar, borra lo suyo con el prefijo MARG-): importa los 4 BC3 de `pruebas/obras/` (copiados al contenedor en `/tmp/pruebas/obras`), con coste objetivo, dos certificaciones facturadas, facturas de proveedor imputadas a partida y pedidos de compra. El producto DEMO-MAT pasa a facturarse por lo pedido, para que cuente como comprometido. Resultado:

  | Obra | Presupuesto | Margen objetivo | Margen real | Preparado |
  |---|---|---|---|---|
  | P260085 Consulta de fisioterapia (Pedro) | 8.670 € | 20 % | 28 % | Sana |
  | P260086 Oficina diáfana (Marta) | 26.982 € | 18 % | 3 % | Capítulo 02 (particiones y techos) a 1,6× el objetivo |
  | P260087 Vivienda Mayor (Pedro) | 8.005 € | 22 % | −21 % | Pavimento a 2,1×, 1.450 € en una partida sin avance, 1.200 € sin imputar |
  | P260088 Cafetería Plaza (Marta) | 14.440 € | 20 % | 22 % | 22 % de avance, 4.068 € comprometidos (uno a 1,35× el objetivo), una partida certificada al 115 % |

- Los BC3 son pequeños (16–21 partidas, 5 capítulos con subcapítulos). Para probar los topes de lectura con obras de cientos de partidas habrá que ampliarlos con `pruebas/obras/generar.py` (sprint 2).
- Sigue por confirmar (6.1) si el coste objetivo, los márgenes y la previsión están en producción.
- Sprint 2 (2026-11-27): entrada `partidas` en `incoespacio_assistant_ai_construction` (venta, objetivo, avance, certificado, objetivo ejecutado y, con Facturación, coste, desviación, adelantado, margen, precio real, comprometido y previsión). Pide filtrar por obra, presupuesto, código o descripción (`requires`) y lee hasta 3.000 líneas (`scan`). Campos nuevos en la partida, sin guardar: `assistant_project_id` (la obra, para filtrar por su nombre), `assistant_chapter` (capítulo de primer nivel, «[02] PARTICIONES Y TECHOS») y `assistant_subchapter` («[02.02] Techos»); el de pantalla lleva el presupuesto y el cliente. No hace falta entrada `capitulos`: «por capítulo» es agrupar las partidas. Módulo nuevo **`incoespacio_assistant_ai_catalog_calc`** (el catálogo está en 499 líneas): `requires` y agrupar y sumar datos calculados leyendo los registros. En el catálogo, cada entrada puede tener su propio tope de lectura y «=» en una relación busca por el nombre (Gemini lo usa y se quedaba sin consultas). 36 tests de catálogo y obra en verde.
- Probado en la demo con Gemini como Marta: análisis de Vivienda Mayor con sus partidas (pavimento a −52 % y lijado con 1.450 € sin avance), «¿qué capítulo de Oficina diáfana va peor?» → [02] PARTICIONES Y TECHOS, −3.813,35 € (como la pestaña), partidas con sobrecoste, coste adelantado y gasto por capítulo. Entre 0,0023 y 0,0048 € por pregunta.
