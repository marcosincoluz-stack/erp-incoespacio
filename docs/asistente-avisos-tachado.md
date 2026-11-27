# Avisos: tachar en el mensaje lo ya hecho

- Fecha: 2026-11-26
- Estado: **plan, sin código**. Se revisa antes de empezar.
- Todo en local hasta que el asistente esté acabado del todo (mismas reglas que las fases 1 y 2).

## 1. Qué se quiere

Los avisos llegan en un mensaje del chat, una línea por aviso, con su chapa para abrir el registro. Cuando alguien arregla uno, la línea se tacha **en ese mismo mensaje**, sin mandar otro, y cuando se guarda el arreglo, no al día siguiente.

Decidido con el usuario:

| Tema | Decisión |
|---|---|
| Aspecto | Opción A: la línea tachada y en gris, con «✓ Hecho» en verde al final. Las líneas no cambian de sitio y el enlace sigue funcionando. |
| Contador | La cabecera pasa a «Tienes 6 avisos · 2 hechos». Si no queda ninguno: «Todo hecho por hoy». |
| Qué mensajes | Todos los que tengan ese aviso: los resúmenes de todos los días y de todas las personas que lo recibieron, incluido el resumen de Dirección. |
| Quién lo hizo | «✓ Hecho por Luis» solo si el aviso lo tenían 2 personas o más. Si era solo tuyo, «✓ Hecho». |
| Cuándo | Al guardar el arreglo (ganchos, ver 3). Las comprobaciones al mirar y la revisión de la mañana se quedan como red de seguridad. |

## 2. Cómo se ve

```
Tienes 6 avisos · 2 hechos
~~[DEMO-077] · Aislamientos · 1.840,00 €~~   ✓ Hecho por Luis
[DEMO-072] · Electricidad Voltio · 1.753,00 €
~~[CERT/2026/0040] · Nave Polígono Sur~~     ✓ Hecho
...
```

Si el aviso vuelve a abrirse (alguien deshace el arreglo), la línea vuelve a su estado normal en todos los mensajes.

## 3. Cuándo se entera el ERP de que algo está hecho

Tres momentos, de más rápido a más lento:

| Momento | Quién lo hizo | Para qué |
|---|---|---|
| **Al guardar** el registro (ganchos) | Se sabe seguro: quien guarda | El tachado al momento. Es lo nuevo. |
| Al abrir «Mis avisos» o preguntar a la IA | No se sabe: sin nombre | Red de seguridad, ya hecha |
| Revisión de la mañana | No se sabe: sin nombre | Red de seguridad, ya existía |

Los ganchos van en los modelos de cada tipo de aviso:

| Tipo de aviso | Módulo | Se vigila al guardar |
|---|---|---|
| Facturas de proveedor sin obra, sin partida, OCR con error, vacías; facturas de cliente vencidas | `incoespacio_assistant_invoice` | Facturas (`account.move`) y sus líneas (`account.move.line`) |
| Certificaciones sin facturar y en borrador | `incoespacio_assistant_construction` | Certificaciones (`construction.certification`) |
| Obras sin certificar | `incoespacio_assistant_construction` | Presupuestos de obra (`sale.order`) y certificaciones |

Funcionamiento de cada gancho:
1. Alguien guarda una factura (o una línea, o una certificación…).
2. El gancho anota ese registro y espera a que termine de guardarse todo (los campos calculados, como «tiene líneas sin partida», también).
3. Justo antes de confirmar el guardado, mira si ese registro tiene avisos abiertos. Casi nunca los tiene, y entonces no hace nada más: una búsqueda pequeña.
4. Si los tiene, pasa la regla de ese tipo de aviso. Si ya no se cumple, resuelve el aviso para todos con el nombre de quien guardó y vuelve a pintar los mensajes donde sale.
5. Si algo falla en el gancho, no se bloquea el guardado: se apunta en el log y la red de seguridad lo recoge después.

Si en el futuro se añade un tipo de aviso nuevo y se olvida su gancho, funciona igual, pero sin el tachado al momento: lo tachará la red de seguridad.

## 4. Piezas

1. **Qué mensajes tiene cada aviso.** Campo nuevo en el aviso con los mensajes donde ha salido. Se rellena al mandar el resumen diario de cada persona y el de Dirección.
2. **Quién y cuándo.** Campos nuevos en el aviso: «resuelto por» (vacío si se resolvió por la red de seguridad) y la fecha, que ya existe.
3. **Volver a pintar.** Cada mensaje se vuelve a generar con sus mismos avisos, en el mismo orden, con el estado de ahora. Se usa el mismo cambio en directo que el «Pensando…» de la IA, y el navegador lo actualiza solo.
4. **Ganchos** en los dos módulos de avisos (facturas y obra), con una función común en el módulo base que hace los pasos 3 a 5.
5. **Redes de seguridad.** La lista, la IA y la revisión de la mañana también vuelven a pintar los mensajes cuando resuelven o reabren un aviso, sin nombre.
6. **CSS.** Tachado y gris para la línea hecha, y la chapa en gris; «✓ Hecho» en verde. Va en el mismo archivo de las chapas.
7. **«(editado)».** Mirar si Odoo marca como editados los mensajes del bot al cambiarlos y, si se puede, evitarlo.

## 5. Tests

1. Guardar la obra en una factura sin obra: el aviso se resuelve con el nombre de quien guardó y la línea sale tachada en los mensajes de todas las personas que lo tenían.
2. Asignar la partida en una línea (sin tocar la factura): también se tacha.
3. Aviso solo de una persona: «✓ Hecho», sin nombre.
4. Resuelto al abrir la lista o en la revisión: tachado sin nombre.
5. Deshacer el arreglo: en la siguiente comprobación el aviso se reabre y la línea vuelve a la normalidad.
6. Guardar una factura sin avisos no pasa ninguna regla.
7. Si la regla falla dentro del gancho, la factura se guarda igual.
8. Contador y «Todo hecho por hoy».

## 6. Pasos

| Paso | Qué | Cómo se comprueba |
|---|---|---|
| 1 ✅ | Mensajes de cada aviso y «resuelto por» | 2 tests (59 en total) |
| 2 ✅ | Volver a pintar con el tachado y el contador (opción A) | 3 tests (62 en total); comprobado en la demo |
| 3 ✅ | Ganchos de facturas | 4 tests (66 en total); comprobado en la demo |
| 4 ✅ | Ganchos de obra | 5 tests (71 en total); comprobado en la demo |
| 5 ✅ | Redes de seguridad que también tachan y reabren | 2 tests (73 en total) |
| 6 ✅ | Demo: Pedro abre un aviso, lo arregla y vuelve al chat | El usuario (2026-11-27): tachado también en la respuesta de la IA, línea entera, 2 px |

Cada paso se cierra con tests en verde y la demo actualizada.

## 7. Notas

- Paso 1 (2026-11-26): el módulo base llegaba a 504 líneas, así que el tachado va en un submódulo, `incoespacio_assistant_done`. En el base solo quedan que publicar devuelva el mensaje y el gancho vacío `_link_message` (base: 490 líneas). Los ganchos de los pasos 3 y 4 harán que los módulos de avisos de facturas y de obra dependan de `incoespacio_assistant_done`.
- `resolved_by_id` se vacía en cualquier cambio de estado que no lo diga, así que la revisión diaria, la comprobación al mirar y la reapertura lo dejan vacío sin tocar su código.
- Paso 2 (2026-11-26): cada línea del resumen lleva la clase `o_incobot_alert_<id>`. No se vuelve a generar el mensaje: se toca el HTML ya publicado (la línea tachada con «✓ Hecho» o «✓ Hecho por …» y el contador « · N hechos» / « · todo hecho» dentro del primer negrita), así el saludo, los totales y «y N más» quedan como se mandaron. Se repinta en cualquier cambio de estado del aviso (resolver, reabrir), venga de donde venga. Odoo 17 tiene desactivada la marca «(editado)», así que no sale. CSS en `incoespacio_assistant_done/static/src/scss/done.scss`.
- Paso 3 (2026-11-26): la función común está en `incoespacio_assistant_done/models/recheck.py`. Los ganchos (`write`/`unlink` de la factura y `create`/`write`/`unlink` de la línea, en `incoespacio_assistant_invoice/models/account_move.py`) solo apuntan el registro; justo antes del commit (precommit, tras guardar los campos calculados) se buscan sus avisos abiertos y, si los hay, se pasa la regla. Lo ya hecho se resuelve para todos con el nombre de quien guardó, salvo si guarda el OCR o un cron (superusuario): entonces sin nombre. Todo en un savepoint: si falla, la factura se guarda igual. `incoespacio_assistant_invoice` depende ahora de `incoespacio_assistant_done`.
- Probado en la demo con un guardado real (RPC, con commit): Ana pone obra a DEMO-073 y el aviso sale «✓ Hecho por Ana Administración» con « · 1 hecho» en los mensajes de Ana y de Luis (290 y 291, resúmenes nuevos que se les mandaron para la prueba).
- Paso 4 (2026-11-27): ganchos en `incoespacio_assistant_construction/models/hooks.py`: `create`/`write`/`unlink` de la certificación (apuntan también su obra, porque una certificación nueva o facturada cambia «obras sin certificar») y `write` de la obra (`sale.order`). El módulo depende ahora de `incoespacio_assistant_done`. Archivar el proyecto de una obra no pasa por estos ganchos: ese aviso lo quita la red de seguridad.
- Probado en la demo dentro de una transacción deshecha (los avisos siguen abiertos para el paso 6): Ana factura CERT/2026/0038 y su aviso sale «✓ Hecho por Ana Administración» en los mensajes de Ana y de Luis; una certificación nueva en Viviendas Residencial El Prado tacha su «obra sin certificar» en el mensaje de Pedro.
- El nombre es el de quien abre la transacción. En la aplicación cada guardado es una petición de una sola persona, así que coincide.
- Paso 5 (2026-11-27): sin cambios de código. La revisión diaria, la comprobación al abrir «Mis avisos» y la reapertura cambian el estado con `write`, que ya repinta. Dos tests nuevos: abrir la lista tacha en los mensajes de todos (sin nombre), y deshacer el arreglo reabre el aviso y quita el tachado y el contador del primer mensaje.
- Paso 6 (2026-11-27), preparado: Pedro (`demo.jefe1`, contraseña en `scripts/assistant_demo_data.py`) tiene en el mensaje 287 dos avisos abiertos: CERT/2026/0040 en borrador y Viviendas Residencial El Prado sin certificar. Ensayado como Pedro en una transacción deshecha: «Aprobar Certificación» y «Nueva Certificación» los tachan con «✓ Hecho» (sin nombre: solo los tiene él) y la cabecera pasa a « · todo hecho».
- Respuestas de la IA (2026-11-27, pedido en la prueba del paso 6): la respuesta de «mis avisos» la escribe Gemini en texto libre, sin la clase de cada aviso, así que no se tachaba. Ahora el enlace (chip) de cada aviso lleva `o_incobot_alert_<id>` (`incoespacio_assistant_ai_data`, que también apunta la respuesta en esos avisos) y el repintado tacha el chip y pone «✓ Hecho» detrás. Sin contador: la respuesta no tiene cabecera. Solo se tachan las respuestas nuevas. Probado en la demo con Gemini en una transacción deshecha (74 tests).
- Estilo (2026-11-27, elegido por el usuario: opción A con el chip tachado): el tachado y «✓ Hecho» se veían poco. Ahora «✓ Hecho» es un sello verde con fondo, y en las respuestas de la IA se tacha la línea entera del aviso (de un `<br>` al siguiente, envuelta en `span.o_incobot_done_line`), no solo el chip. Al reabrirse se deshace y el mensaje queda como estaba. Mensaje 300 de Pedro repintado en la demo.
- Para la demo se ha mandado a Pedro un resumen nuevo (mensaje 287) que ya guarda sus avisos.
- En la demo, los resúmenes ya enviados no tienen sus avisos guardados: el tachado se verá en los que se manden a partir de ahora.

## 8. Límites

- Los mensajes que ya estaban enviados antes de este cambio no saben qué avisos tenían: no se tachan. Sí los de los resúmenes nuevos.
- El tachado al momento depende de que el arreglo pase por los modelos vigilados. Uno que se haga por otro camino (por ejemplo, SQL directo en una migración) se tacha después, por la red de seguridad.
