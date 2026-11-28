# Plan: consultas libres sobre un catálogo

Estado: sprints 1 a 4 hechos (2026-11-27). Solo en local, como el resto del asistente.

## 1. Qué se quiere

Que IncoBot pueda contestar preguntas de datos que nadie ha previsto («¿qué obra tiene más beneficio?», «¿cuánto hemos facturado a cada cliente este año?», «¿qué proveedor nos ha facturado más en la obra X?») comparando, ordenando y sumando ella misma, sin programar una herramienta por pregunta.

Pedido por el usuario al ver «eso no lo puedo consultar todavía» ante «dime cuál de las obras tiene más beneficio».

## 2. Enfoque elegido: herramienta genérica sobre un catálogo

| | Herramientas a medida (hoy) | Lectura libre de Odoo | **Catálogo (elegido)** |
|---|---|---|---|
| Preguntas nuevas | Hay que programar | Sí | Sí, si está en el catálogo |
| Acierta con los campos | Sí | Se lía con cientos de modelos y nombres técnicos | Sí: nombres en español y significado |
| Campos calculados (margen) | Sí | No se pueden filtrar ni ordenar | Sí, con tope de filas |
| Riesgo de sacar algo sensible | Bajo | Alto | Bajo: solo lo que está en la lista |
| Ampliar | Código nuevo | — | Una entrada más en el catálogo |

- **Catálogo**: lista cerrada de lo que se puede consultar. Por cada cosa: modelo, nombre en español, para qué sirve y sus campos con nombre en español y significado («margen: certificado menos facturas de proveedor; no incluye mano de obra propia ni gastos generales»). Cada módulo añade lo suyo (`_catalog()`, como hoy `_tools()`): facturas en el de facturas, obra en el de obra.
- **Herramienta `consultar`**: «de esto, con estos filtros, dame estos campos, ordenado así, como mucho N» o «agrupado por esto, sumando esto». La IA no escribe dominios de Odoo: manda filtros estructurados (campo, operador, valor) que este código traduce, comprobando que todo esté en el catálogo.
- **Se quedan a medida** solo las que tienen lógica propia: `mis_avisos` (comprueba en el momento) y `resumen_obra` (junta varias cosas de una obra). `buscar_facturas` y `buscar_certificaciones` se retiraron en el sprint 4: el catálogo las cubre.

## 3. Seguridad (lo que no cambia y lo que se añade)

Igual que hoy:
- Solo lectura: savepoint con `SET TRANSACTION READ ONLY` y `statement_timeout` de 5 s.
- Como el usuario, nunca con sudo: sus permisos de modelo, de campo y reglas de registro (también al agrupar: `read_group` las aplica).
- Lista negra de modelos y campos (`BLOCKED_MODELS`, `BLOCKED_FIELDS`, `BLOCKED_WORDS`) como segunda barrera, aunque algo se colara en el catálogo.
- Un campo que el usuario no puede leer sale «sin permiso» (también los calculados que tiran de otro modelo, como el margen).

Nuevo:
- **Todo pasa por el catálogo**: modelo, campos, filtros, orden y agrupaciones. Nada que no esté declarado, ni rutas con puntos que no estén declaradas (p. ej. «cliente.nombre» sí; «cliente.cuentas_bancarias» no).
- **Operadores cerrados**: `=`, `!=`, `>`, `>=`, `<`, `<=`, `contiene`, `en`, `vacío`. Los valores se comprueban por tipo (fecha, número, texto, sí/no, opción de una lista).
- **Topes**: como mucho 50 filas devueltas; para ordenar por un campo calculado se leen como mucho 200 registros (si hay más, se dice y se pide afinar el filtro); como mucho 30 grupos.
- **Test de oro**: para cada entrada del catálogo, un usuario sin permiso no recibe nada que no vería en pantalla.

## 4. Coste

El catálogo va en la descripción de la herramienta, así que entra en cada pregunta: unos 2.000–3.000 tokens más, unos 0,001 € más por pregunta (de ~0,001 € a ~0,002 €). Si creciera mucho, se pasa a dos pasos (la IA pide primero el detalle de una sola entrada del catálogo).

## 5. Sprints

Cada sprint se cierra con la suite en verde, el tope de 500 líneas por módulo, la demo actualizada y la revisión del usuario.

### Sprint 1 ✅: la base (catálogo y `consultar` con filtros, orden y límite)

- Módulo nuevo `incoespacio_assistant_ai_catalog` (depende de `incoespacio_assistant_ai_data` para la lectura segura).
- Formato del catálogo y `_catalog()` ampliable por módulos.
- `consultar`: filtros estructurados, campos, orden por campos guardados, límite. Enlaces a los registros como hoy.
- Catálogo inicial: **obras** (presupuestos de obra) y **facturas** (cliente y proveedor).
- Tests: filtros y operadores, rechazo de todo lo que no está en el catálogo (modelo, campo, ruta, operador), valores de tipo equivocado, topes, como el usuario sin sudo, y el test de oro de permisos.
- Prueba: «facturas de proveedor de este mes de más de 1.000 €», «obras del cliente X».

### Sprint 2 ✅: agrupar, sumar y campos calculados

- Agrupar y sumar (`read_group`): por cliente, proveedor, obra, mes, estado.
- Ordenar por campos calculados (margen, certificado, coste) leyendo hasta 200 registros.
- Texto del sistema: cuándo usar `consultar` y cómo explicar lo que significa cada dato (margen ≠ beneficio neto).
- Tests: sumas que cuadran con la pantalla, tope de 200, «sin permiso» en el margen para quien no ve costes.
- Prueba: **«¿qué obra tiene más beneficio?»** (la pregunta que lo empezó todo), «facturado por cliente este año», «obras que pierden dinero».

### Sprint 3 ✅: ampliar el catálogo

- Certificaciones, pedidos de compra (y comprometido por obra), cobros y pagos pendientes, clientes y proveedores (sin NIF, cuentas ni datos de contacto sensibles), proyectos.
- Cada entrada con su significado revisado con el usuario (qué es «pendiente», «vencido», «comprometido»…).
- Tests de oro por entrada.

### Sprint 4 ✅: calidad y coste con preguntas reales

- Batería de unas 20 preguntas reales: las de «Lo que IncoBot no sabe», las de la demo y las que diga el usuario.
- Pasarlas contra Gemini en la demo: cuántas acierta, tokens y coste por pregunta.
- Ajustar descripciones del catálogo donde falle.
- Decidir si se retiran `buscar_facturas` y `buscar_certificaciones`.

### Sprint 5: demo con el usuario y documentación (documentación ✅; falta la prueba)

- El usuario prueba como jefe de obra, administración y dirección.
- README del módulo y notas en `docs/asistente-ia-fase2.md`.
- Se suma a la prueba con el equipo.

## 6. Por decidir

1. **Qué ve cada rol** (ya pendiente en la fase 2): con el catálogo esto pesa más, porque la IA podrá comparar y sumar todo lo que cada uno ve. En especial, ¿quién ve márgenes y costes? Se decide en los roles, no en IncoBot.
2. **Entradas del catálogo inicial** (sprints 1 y 3): propuesta arriba; el usuario puede quitar o añadir.
3. **Topes** de filas (50), registros para campos calculados (200) y grupos (30): valores de partida.
4. **Retirar herramientas a medida** que el catálogo cubra (sprint 4).

## 7. Límites

- Solo responde sobre lo que está en el catálogo; lo demás sigue saliendo en «Lo que IncoBot no sabe», y suele bastar con añadir una entrada.
- Los números son los del ERP: si una factura no tiene obra, no cuenta en el margen de ninguna obra (los avisos ya lo señalan).

## 8. Notas

- Sprint 1 (2026-11-27): módulo `incoespacio_assistant_ai_catalog`, entradas `facturas` y `obras`. `_rows` admite ahora un tope propio (`cap`) para llegar a 50 filas. 11 tests nuevos (94 en total): filtros y operadores, opciones por clave o etiqueta, rechazo de todo lo de fuera del catálogo, tope, lista negra, como el usuario, y de oro en facturas y obras.
- **Hallazgo de permisos**: el margen (y el coste) se calcula con las facturas de proveedor que ve quien pregunta. Un jefe de obra sin contabilidad no ve ninguna, así que su «margen» salía igual a lo certificado: un número engañoso, no un error. Ahora coste y margen solo se enseñan con el grupo Facturación (`account.group_account_invoice`); si no, «sin permiso», y no se puede filtrar ni ordenar por ellos. Corregido también en `resumen_obra`, que tenía el mismo problema. Quién debe ver márgenes se decide en los roles (6.1).
- Probado en la demo con Gemini (transacción deshecha), como Ana (Facturación): «facturas de proveedor de noviembre de más de 1.000 €» (53, enseña las 20 primeras), «facturas de cliente sin cobrar y cuánto suman» (3, 14.610 €, la suma la hizo ella con las filas: en el sprint 2 la hará la herramienta) y una búsqueda de obras por cliente. Entre 0,0013 y 0,0048 € por pregunta; la cara es la de la lista larga (más texto de salida).
- Sprint 2 (2026-11-27): `agrupar` (con «campo:mes» o «campo:año» para fechas) y `sumar` con `read_group` como el usuario, como mucho 30 grupos ordenados por la primera suma. Ordenar y filtrar por campos calculados numéricos o de fecha (el margen) leyendo hasta 200 registros; si hay más, pide afinar el filtro. Ordenar por un calculado de texto, no. La descripción de la herramienta dice que use agrupar y sumar para totales y no sume listas a mano. Código en `models/question_more.py`. 4 tests nuevos (98 en total).
- Probado en la demo con Gemini (transacción deshecha): «¿qué obra tiene más beneficio?» → Clínica dental Centro, 19.345,60 €, con la aclaración de que el margen no es beneficio neto; «facturado a cada cliente este año» (agrupa por empresa y suma); «obras que pierden dinero» → Rehabilitación fachada Avenida, −14.536 €. Unos 0,0016–0,0023 € por pregunta. Pedro también recibe márgenes porque en la demo el rol «Jefe de obra» lleva Facturación (para imputar facturas): en producción depende de los roles reales (6.1).
- Sprint 3 (2026-11-27): entradas nuevas `certificaciones`, `compras` y `proyectos` (en `incoespacio_assistant_ai_construction`) y `pagos` y `contactos` (en `incoespacio_assistant_ai_invoice`). Contactos sin NIF, cuentas, correo, teléfono ni dirección; «por cobrar» y «por pagar» solo con Facturación. **Test de oro genérico** (`incoespacio_assistant_ai_catalog/tests/gold.py`): para cada entrada y cada usuario de prueba, nunca devuelve un registro que no vería en pantalla y los campos con grupo salen «sin permiso»; cubre solo cualquier entrada nueva. Un campo sin permiso ahora sale como «sin permiso» en vez de desaparecer. Se puede agrupar, ordenar y sumar por campos heredados (la fecha de un pago está en su asiento) y «sumar» sin «agrupar» da los totales. 7 tests nuevos (105 en total).
- **Significados para revisar con el usuario** (sprint 3 decía revisarlos): «pendiente» de una factura = lo que queda por cobrar o pagar; «facturación» de un pedido de compra = si el proveedor ya lo ha facturado; «por cobrar» / «por pagar» de un contacto = saldo contable ahora; «jefe de obra» = el responsable del proyecto.
- Probado en la demo con Gemini como Elena (Dirección): proveedores a los que más se debe (agrupa facturas por empresa y suma lo pendiente), obras que lleva Pedro (5), certificado a origen de El Prado (14.414,40 €), pedidos pendientes de facturar (ninguno), cobros del mes (en la demo no hay cobros: 0) y pagos por mes (sin pagos, contesta con lo facturado y lo dice). Entre 0,0019 y 0,0034 € por pregunta; la descripción de la herramienta ha crecido a unos 6.000 tokens de entrada por pregunta.
- Sprint 4 (2026-11-27): batería de 20 preguntas reales en `scripts/assistant_eval.py` (fuera de git), con la respuesta esperada calculada en la base de datos en el momento; se pasa contra Gemini en la demo en una transacción deshecha (unos 0,04 €). Primera pasada: 15/20. Fallos de verdad: ordenar «el que más» sin pedir de mayor a menor (salía la peor obra) y sumar borradores como deuda. Arreglos: el orden acepta «margen desc» o «-margen» y la descripción de «descendente» explica cuándo usarlo; la entrada de facturas explica que un borrador aún no se debe, cómo se ve una vencida o sin obra, y que las rectificativas van aparte. **Retiradas `buscar_facturas` y `buscar_certificaciones`**: lo que hacían de especial (sin obra, sin partida, vencida) está en el catálogo (`excluida_de_obra`, `lineas_sin_partida`); sus tests pasan a `consultar`. Se quedan a medida `mis_avisos`, `resumen_obra` y `wiki_pagina`. Pasada final: **20/20**, 0,0020 € de media, unos 5.900 tokens de entrada por pregunta. 105 tests.
- Sprint 5 (2026-11-27): documentación hecha (README del catálogo, `consultar` en `docs/asistente-ia-fase2.md`). Guion de prueba para el usuario:
  - Como **Elena (Dirección)**: «¿qué obra tiene más beneficio?», «¿qué obras pierden dinero?», «¿a qué proveedores debemos más?», «¿cuánto hemos facturado a clientes este año?», «¿qué facturas de cliente están vencidas?».
  - Como **Ana (Administración)**: «¿cuántas facturas de proveedor hay en borrador?», «¿qué facturas de proveedor no tienen obra?», «¿cuánto nos debe [DEMO] Cliente obras?», «¿cuál es la factura de proveedor más cara de noviembre?».
  - Como **Pedro (Jefe de obra)**: «¿cómo va Calle Mayor 12?», «¿cuál es la última certificación de Calle Mayor 12?», «¿qué certificaciones hay en borrador?», «¿qué avisos tengo?».
  - Una que no sepa (para ver que sale en «Lo que IncoBot no sabe»): «¿cuántas horas ha trabajado Pedro esta semana?».
  - En la demo los tres roles llevan Facturación, así que todos ven márgenes: para ver «sin permiso» habría que quitárselo a un rol.
- Prueba del usuario (2026-11-27), como Marta: «dime la obra que más se ha facturado» agotó las 4 consultas (y al repetirla contestaba con el presupuesto). Causa: «facturado» de una obra es el certificado, un dato calculado; Gemini intentaba agruparlo y sumarlo. Arreglos: el error de sumar un calculado le dice a la IA cómo hacerlo (ordenar por él de mayor a menor, sin agrupar), y la entrada de obras dice que el certificado es «lo facturado». También: si la IA no dice el sentido del orden, las fechas van de la más reciente a la más antigua («la última certificación» salía la primera). Batería ampliada a 21 preguntas: **21/21**, 0,0022 € de media. 108 tests.
- Los resúmenes de la demo del 26/11 (antes de los chips y el tachado) se quedan como estaban; los nuevos ya salen con chips y se tachan. En producción no habrá mensajes antiguos. A Marta se le mandó un resumen nuevo (mensaje 318). Una pregunta de Marta falló con «Falta la clave de Gemini» justo mientras se reiniciaba la demo; vuelta a la cola, el servidor la contestó bien.
