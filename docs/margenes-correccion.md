# Plan: corregir los totales de la pestaña Márgenes

Estado: pasos 1 a 3 hechos (2026-11-27); falta la revisión del usuario y el PR. Solo en local hasta que el usuario lo dé por bueno.

## 1. Qué pasa

Al preparar la demo de márgenes (`docs/asistente-ia-margenes.md`, sprint 1) salieron tres casos en los que la pestaña Márgenes da totales que engañan. Cada número sale bien de su fórmula; el problema son las fórmulas en esos casos. Ejemplos con la demo:

| # | Qué | Ejemplo | Tipo |
|---|---|---|---|
| 1 | El **margen real** de la obra resta solo el coste imputado a partidas; lo no imputado sale aparte y no se resta | Vivienda Mayor: dice −969 €; con los 1.200 € sin imputar es −2.169 €. Además, el ERP tiene dos «márgenes» distintos (`amount_margin_real` y `amount_job_margin`), y IncoBot usa el otro | Decisión de diseño que engaña |
| 2 | La **desviación** de la cabecera no cuadra con la de la tabla: la cabecera cuenta el coste de partidas sin avance y la tabla no | Vivienda Mayor: cabecera −1.982 €, tabla −532 €; la diferencia son 1.450 € en una partida sin certificar | Incoherencia |
| 3 | La **previsión a fin de obra** cuenta lo comprometido en compras como gastado y lo extrapola a lo que falta | Cafetería Plaza: va al 22 % y prevé −112 %, porque un pedido de la partida entera se cuenta dos veces | Error en la práctica (el código ya avisa: «sobreestima») |

## 2. Solución

### 2.1 Previsión a fin de obra (problema 3)

Hoy, por partida: `previsto = incurrido + lo que falta × (incurrido / medición certificada)`, con incurrido = facturado + comprometido.

Nuevo:

```
precio real   = facturado / medición certificada   (sin certificar: precio objetivo)
previsto      = facturado + máx(comprometido, lo que falta × precio real)
```

- Lo comprometido se entiende como lo que se va a gastar en lo que falta: no se suma encima de la extrapolación, se compara con ella y manda la mayor.
- Si lo comprometido supera lo que falta al ritmo real, la previsión sube: es la señal buena (en Cafetería, el pedido al 1,35× del objetivo sale como sobrecoste de esa partida, no como −112 % de la obra).
- A nivel obra: suma de partidas **más el coste sin imputar** (es coste real de la obra).
- Sin pedidos ni certificación, igual que hoy (los tests actuales de previsión siguen valiendo).

### 2.2 Desviación coherente y «coste adelantado» (problema 2)

En obra es normal pagar antes de certificar (se compra material y se certifica a fin de mes). Por eso no se mete ese coste en la desviación (saldrían todas las obras en rojo al empezar), sino que se separa:

- **Desviación** = sobre lo ejecutado, partida a partida (como hoy en la tabla). La cabecera pasa a ser la **suma de la tabla**: cuadran siempre.
- **Coste adelantado** (nuevo, en la cabecera y marcado en la fila): lo gastado en partidas que aún no tienen nada certificado. Puede ser normal (acopio de material) o un error de imputación; la pantalla lo enseña y lo explica en el «?», sin mezclarlo.

### 2.3 Margen real total (problema 1)

- **Margen real** de la obra = certificado − **todo** el coste de la obra (imputado o no). Debajo: «de ellos, 1.200 € sin imputar a partida» cuando los haya.
- Así `amount_margin_real` y `amount_job_margin` dan lo mismo, y la pantalla, la lista de obras e IncoBot dicen el mismo margen.
- La tabla sigue siendo por partida (lo sin imputar no es de ninguna): el total de la columna «Margen real» es el de lo imputado, y la cabecera lo dice.

## 3. Piezas

| Pieza | Módulo | Qué |
|---|---|---|
| Previsión | `incoespacio_construction_margins_forecast` | Nueva fórmula por partida; la obra suma lo sin imputar |
| Desviación y coste adelantado | `incoespacio_construction_margins_forecast` (márgenes está en el tope de líneas) | Cabecera = suma de la tabla; campo nuevo de coste adelantado (partida y obra); marca en la fila |
| Margen real total | `incoespacio_construction_margins_forecast` (ídem) | Resta todo el coste; texto «sin imputar» bajo el margen |
| Vista y colores | `incoespacio_construction_margins` (`views/sale_order_views.xml`, `static/src/js/margin_lines.js`) | Cabecera nueva y «?» con la explicación |
| Lista de obras | `incoespacio_construction_margins_list` | Comprobar que sus columnas toman el margen nuevo |
| IncoBot | `incoespacio_assistant_ai_construction` | El catálogo usa los mismos campos (margen, desviación, coste adelantado, previsión) |

Son campos calculados sin guardar: no hace falta migrar datos; al actualizar, los números cambian solos.

## 4. Pasos

| Paso | Qué | Cómo se comprueba |
|---|---|---|
| 1 ✅ | Previsión (2.1) | Test nuevo: pedido de la partida entera no se cuenta dos veces; los 3 tests actuales de previsión siguen igual. Demo: Cafetería deja de dar −112 % |
| 2 ✅ | Desviación y coste adelantado (2.2) | Tests: cabecera = suma de la tabla; coste en partida sin avance sale como adelantado y no como desviación. Demo: Vivienda Mayor, cabecera = tabla y 1.450 € de coste adelantado |
| 3 ✅ | Margen real total (2.3) | Test: el margen real resta lo sin imputar (el test actual `test_unassigned_cost` se amplía). Demo: Vivienda Mayor da −2.169 € con «1.200 € sin imputar» |
| 4 | Lista, colores, IncoBot y suite de construcción entera | Suite en verde; el usuario revisa las 4 obras de la demo en pantalla |
| 5 | Rama y PR propios desde `main`, cuando el usuario lo diga | Es código de producción e independiente del asistente: puede subir antes que él |

## 5. Por decidir

1. **Textos de la cabecera**: «Coste adelantado» o «Gastado sin avance»; y si lleva también columna en la tabla o solo la marca en la fila.
2. **Acopios**: si se compra material de toda la obra al principio, el coste adelantado será alto los primeros meses. ¿Se quiere ver así, o se marca de alguna forma el acopio?

## 6. Límites

- Lo comprometido sin partida (pedidos de la obra sin imputar a ninguna partida) no entra en la previsión por partida; se puede añadir como «comprometido sin imputar» si hace falta.
- La previsión sigue siendo una extrapolación al ritmo real: orienta, no es un presupuesto cerrado.

## 7. Notas

- Paso 1 (2026-11-27): `incoespacio_construction_margins_forecast` 17.0.1.1.0. Por partida, previsión = facturado + máx(comprometido, lo que falta × precio real con lo facturado); la obra suma también lo sin imputar. 3 tests nuevos (pedido de la partida entera no se cuenta dos veces, pedido por encima del ritmo sube la previsión, lo sin imputar entra en la obra); los 4 que había siguen igual. En la demo: Cafetería Plaza pasa de −112,4 % a 11,0 % (el pedido a 1,35× del objetivo baja el margen previsto desde el 20 %); Vivienda Mayor de −7,2 % a −22,2 % (cuenta los 1.200 € sin imputar); las otras dos no cambian.
- **Fallo previo, no de esta corrección**: 2 tests de `incoespacio_bc3_planned_cost` (`test_percent_and_qty_change`, `test_qty_planned_can_diverge`) fallan también pasándolos solos en una base limpia, sin cambios en el módulo. Hay que mirarlo aparte.
- Paso 2 (2026-11-27): `incoespacio_construction_margins` estaba en 499 líneas (tope 500) y cualquier cambio lo pasaba, así que **las correcciones van en `incoespacio_construction_margins_forecast`** (17.0.1.2.0), que se instala solo con él y ya llevaba los totales de coste: el campo «coste adelantado» (partida y obra), la desviación de la obra como suma de las partidas (sobrescribe `_compute_order_margins` de márgenes) y la vista (línea «Adelantado (sin avance)» con «?» bajo el coste real, y fila en naranja). El módulo de márgenes queda sin tocar. 2 tests nuevos. En la demo, Vivienda Mayor: cabecera y tabla −532,13 €, adelantado 1.450 €, el lijado de puertas en naranja. 59 tests de obra y márgenes en verde.
- El paso 3 (margen real total) irá también en el módulo de previsión, por lo mismo.
- Paso 3 (2026-11-27): también en `incoespacio_construction_margins_forecast` (17.0.1.3.0): margen real = certificado − todo el coste de la obra, y bajo él «Incluye X € sin imputar» con «?». Coincide con `amount_job_margin`, que es el que ya usaban la lista de obras e IncoBot: ahora los tres dicen lo mismo. 1 test nuevo; 60 tests de obra y márgenes en verde. En la demo, Vivienda Mayor pasa de −968,75 € a −2.168,75 € (−47,1 %), con «Incluye 1.200,00 € sin imputar».
- Paso 4: la lista de obras e IncoBot no necesitan cambios (ya usaban `amount_job_margin`). Llevar al catálogo de IncoBot el coste adelantado y la desviación es el sprint 2 de `docs/asistente-ia-margenes.md`.
