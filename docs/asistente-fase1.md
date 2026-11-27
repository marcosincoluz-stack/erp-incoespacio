# Asistente IncoBot: fase 1 (avisos por reglas)

- Fecha: 2026-11-25 (revisado 2026-11-26)
- Objetivo: que cada usuario reciba de IncoBot Asistente, en un chat de Discuss, lo que tiene pendiente en el ERP.
- Fuera de la fase 1: IA (Gemini), chatbot con preguntas, wiki, plan de tareas del día, reglas configurables desde la interfaz.

## Decisiones tomadas

- **Avisos por reglas en código.** La IA no decide nada. Entra en una fase posterior como módulo aparte (`incoespacio_assistant_ai`) que solo redacta el mismo contenido.
- **Entrega:** chat directo de **IncoBot Asistente** con cada usuario. Es un contacto propio (`res.partner` sin usuario ni login). No se toca OdooBot (`base.user_root`).
- **Factura sin obra → Administración y jefe de obra.** Las marcadas «No es de obra» no avisan.
- **Roles con `base_user_role` (OCA, `addons/server-backend`).** Marcos crea a mano los roles *Administración* y *Jefe de obra* y decide qué apps abre cada uno. El código no fija permisos de roles.
- **Motor separado de los avisos:** un núcleo que no sabe de facturas ni obras, y un módulo de avisos por área en `extras/`.
- **El jefe de obra ve todas las obras.** No hacen falta reglas de acceso nuevas. Aun así, cada jefe solo **recibe** los avisos de sus obras, por la casilla de responsable y no por rol.
- **4 días de margen** para `bill_draft_no_obra`. Las facturas marcadas «No es de obra» nunca avisan.
- **Dirección recibe un resumen**, no cada aviso suelto. De momento solo por chat.
- **Los 4 días cuentan desde que la factura entra en el ERP** (`create_date`), en días naturales.
- **Nombre del contacto: «IncoBot Asistente».**
- **Jefe de obra = quien crea la obra** (ver «Jefe de obra» abajo).

## Jefe de obra

Hoy `project.project.user_id` (Responsable) no está relleno en las obras. La obra la crea `sale.order._ensure_project()` (en `incoespacio_construction_certification`) al confirmar el presupuesto, sin pasar responsable.

Propuesta:
- **Obras nuevas:** `_ensure_project()` rellena `user_id` con el usuario que crea la obra (quien confirma el presupuesto). Es un `[IMP]` pequeño en ese módulo.
- **Obras existentes:** un script de una vez rellena `user_id` con `create_uid` de la obra si está vacío.
- **El campo es editable:** si la obra pasa a otra persona, se cambia el Responsable a mano y los avisos le llegan a la nueva.
- El asistente solo lee `project.project.user_id`. No deduce nada: lo que diga ese campo es la verdad.

Si una obra no tiene responsable, el aviso le llega solo a los roles marcados (Administración), nunca se pierde.

## Módulos

| Módulo | Ubicación | Depende de | Qué hace |
|---|---|---|---|
| `incoespacio_assistant` | `addons-incoespacio/` | `mail`, `base_user_role` | Núcleo: tipos de aviso, avisos con estado, destinatarios, preferencias, cron y chat |
| `incoespacio_assistant_summary` | `addons-incoespacio/` | núcleo | Resumen de Dirección (diario y semanal), su regla de lectura y el ajuste de roles |
| `incoespacio_assistant_invoice` | `extras/invoice/` | núcleo, `incoespacio_invoice_ocr_obra`, `incoespacio_construction_cost` | Avisos de facturas |
| `incoespacio_assistant_construction` | `extras/construction/` | núcleo, certificación, márgenes | Avisos de obra (segunda tanda) |

Cada uno por debajo del tope de 500 líneas de Python + JS. Estimación del núcleo: unas 300.

## Destinatarios: quién recibe cada aviso

Los roles se crean a mano, sin identificador fijo en el código. Por eso **cada tipo de aviso dice a quién va, y eso se configura desde la interfaz**:

- **Roles que lo reciben** (`role_ids`, a `res.users.role`): todos los usuarios con ese rol reciben el aviso. Ejemplo: `bill_draft_no_obra` → rol *Administración*.
- **También al responsable del registro** (`notify_responsible`, casilla): el colector dice quién es el responsable de cada registro. Ejemplo: el jefe de la obra de esa factura.

Destinatarios de un aviso = usuarios de los roles marcados ∪ responsable del registro (si la casilla está marcada).
Siempre se filtra: si un usuario no puede abrir el registro con sus permisos, no recibe el aviso.

Así Marcos decide en una pantalla qué rol recibe qué, sin desplegar código. Con un tipo sin roles y sin casilla, el aviso queda desactivado de hecho; útil para pilotar.

Cuidado al configurar: el rol *Jefe de obra* **no** se marca en `role_ids` de los avisos de facturas. Si se marca, todos los jefes reciben las facturas de todas las obras. A cada jefe le llegan las suyas por la casilla de responsable.

Los usuarios archivados no reciben nada.

## Resumen de Dirección

Un mensaje aparte, para los usuarios de los roles marcados en *Ajustes → Asistente → Roles que reciben el resumen* (`summary_role_ids`). No genera avisos; lee los `assistant.alert` de todos. Si Dirección también tiene avisos propios, le llegan en su mensaje normal.

Criterio: **de los asuntos, no de las personas.** Nada de clasificaciones por persona («Ana: 8, Pedro: 2»). El responsable aparece solo junto a cada asunto atascado, para saber a quién preguntar.

**Diario (lunes a viernes), corto:**

> **Resumen del 26/11/2026**
>
> | Aviso | Abiertos | Nuevos hoy | Más de 7 días |
> |---|---|---|---|
> | Facturas de proveedor sin obra | 12 | 3 | 4 |
> | Facturas con líneas sin partida | 8 | 1 | 2 |
>
> **Lo más atascado**
> - FACTPROV/2026/0311 · sin obra · 19 días · Administración
> - FACTPROV/2026/0287 · sin partida · 15 días · Obra Calle Mayor 12 (Juan)
> - … (como mucho 5)
>
> Resueltos ayer: 6. [Ver todos los avisos]

**Lunes, además, la semana:** abiertos ahora frente al lunes pasado, resueltos en la semana y tiempo medio hasta resolver, por tipo. Sirve para ver si el asistente funciona o si un tipo de aviso se ignora siempre (ese sobra o hay que replantearlo).

Para la tendencia semanal, el núcleo guarda los avisos resueltos (no se borran), y con eso basta: no hace falta tabla de histórico.

## Núcleo: `incoespacio_assistant`

### Modelos

**`assistant.alert.type`**: catálogo de avisos. Los módulos de área lo rellenan por XML; los destinatarios se ajustan en la interfaz.
- `code` (único), `name`, `active`, `sequence`.
- `collector`: nombre del método que busca los registros.
- `threshold_days`: días de margen antes de avisar (cada colector decide si lo usa).
- `since_date`: solo registros desde esa fecha. `bill_no_partida` sale con la fecha de instalación para no arrastrar el histórico; vaciarla incluye todo.
- `role_ids`, `notify_responsible`: destinatarios (ver arriba).

**`assistant.alert`**: un aviso concreto, para un usuario y un registro.
- `type_id`, `user_id`, `res_model`, `res_id` y la referencia para abrirlo.
- `message`: texto corto ya montado por el colector.
- `state`: `new` / `open` / `snoozed` / `resolved`.
- `first_seen`, `last_seen`, `snooze_until`, `resolved_date`.
- Clave única: `(type_id, user_id, res_model, res_id)`.
- Regla de registro: cada usuario solo ve sus avisos.

**Preferencias**: `res.users.assistant_muted_type_ids` (tipos silenciados por cada usuario).

### Contrato del colector

```python
def _collect_<code>(self):
    """Devuelve [(record, responsable_o_vacío, message), ...] con lo que hoy cumple la regla."""
```

El núcleo, no el colector, calcula los destinatarios (roles + responsable) y comprueba los permisos. Así cada colector es corto y solo contiene la regla de negocio.

### Cron diario (8:00, lunes a viernes)

1. Por cada tipo activo, llamar a su colector y calcular destinatarios.
2. Por cada (usuario, registro): si el aviso existe, actualizar `last_seen` (y reabrir si estaba `resolved`); si no, crearlo en `new`.
3. Los avisos abiertos que **no** han salido hoy pasan a `resolved`. Así se sabe sin IA que el usuario ya lo ha hecho.
4. Los pospuestos con `snooze_until` vencido vuelven a `open`.
5. Por cada usuario con avisos `new` u `open` (y tipo no silenciado), un mensaje de IncoBot Asistente. Si no hay nada, no se envía nada. Como mucho 10 líneas por tipo; el resto sale como «y 37 más» con enlace a la lista filtrada.
6. Los `new` enviados pasan a `open`.
7. Resumen de Dirección.

La hora es la de Madrid (el cron de Odoo va en UTC: se ajusta al instalar).

**Primer día:** habrá pendientes antiguos acumulados, quizá cientos de borradores. El tope de 10 líneas por tipo evita un mensaje enorme. Los avisos antiguos salen como «pendiente desde hace N días» desde el primer día.

Un fallo en un colector se registra en el log y no para el resto.

### Mensaje (ejemplo)

> **Buenos días, Ana. Tienes 4 avisos.**
>
> **Facturas de proveedor sin obra (2)**
> - 🆕 FACTPROV/2026/0412 · Ferretería López · 1.240,00 €
> - FACTPROV/2026/0398 · Hormigones Sur · pendiente desde hace 6 días
>
> **Facturas con líneas sin partida (2)**
> - 🆕 FACTPROV/2026/0405 · Obra Calle Mayor 12
> - …
>
> [Ver todos mis avisos]
>
> _Este chat solo envía avisos; no responde mensajes._

Cada referencia enlaza al registro.

### Chat

- Un canal `discuss.channel` de tipo `chat` por usuario, con dos miembros: el usuario e IncoBot Asistente. Se crea la primera vez y se reutiliza.
- Se publica con `author_id` = contacto del asistente. Nadie contesta: el pie del mensaje lo dice.

### Interfaz

- Menú **Mis avisos**: lista agrupada por tipo, con botones *Abrir*, *Posponer 1 día* y *Posponer 1 semana*.
- En las preferencias del usuario: silenciar tipos.
- Menú de configuración (solo administradores): tipos de aviso con sus roles, casilla de responsable y días de margen.

### Seguridad

- Usuarios internos: leen y actualizan (posponer) solo sus avisos. No crean ni borran.
- Configuración de tipos: solo `base.group_system`.
- El cron corre como superusuario para encontrar registros, pero nunca asigna un aviso sin comprobar antes el acceso con `with_user(usuario)`.
- El asistente no escribe nada fuera de sus propios modelos y del chat.

## Primera tanda de avisos: `incoespacio_assistant_invoice`

| Código | Regla | Rol propuesto | Responsable |
|---|---|---|---|
| `bill_draft_no_obra` | Factura o abono de proveedor en borrador, sin obra y **sin** la marca «No es de obra» (`construction_not_job`), creada hace más de 4 días (`threshold_days`) | Administración | Jefe de la obra sugerida por el OCR (`ocr_obra_suggested_id.user_id`), si la hay |
| `bill_no_partida` | Factura de proveedor publicada con obra y líneas sin partida (`has_unassigned_partida`) | Administración | Jefe de esa obra |
| `bill_ocr_failed` | Elemento de la cola OCR o correo del buzón que falló | Administración | — |

Una factura sin obra siempre está en borrador, porque el candado al publicar obliga a tener obra o la marca. Si el OCR no sugirió obra, solo le llega a Administración.

Candidatos para la segunda tanda (`incoespacio_assistant_construction`): facturas de la obra sin certificar (`certification_pending_bills`), obra sin certificar en X días, partida cuya previsión supera el presupuesto (`margins_forecast`) y pedidos de IncoBot sin confirmar.

## Preguntas abiertas

1. **Cómo se guarda la obra en la factura** (analítica del proyecto u otro campo). Se confirma al implementar `bill_no_partida`; no bloquea el núcleo.
2. **Imagen** del contacto: el logo de Incoespacio si no se dice otra cosa.
3. **¿Email** para quien no abre Odoo a diario? Fuera de la fase 1.

## Cómo se trabaja

- Rama `feat-assistant` desde `main`; entra por pull request con el CI en verde.
- Antes de empezar: commitear `addons/server-backend/`, `addons/README.md` y `config/odoo.conf_example` (ya están en local, falta el commit). En AWS ya está instalado `base_user_role`.
- Commits: `[ADD] incoespacio_assistant: …`, `[ADD] incoespacio_assistant_invoice: …`.
- `scripts/custom_modules.py` debe recoger los módulos nuevos para el CI.

## Pasos

0. Jefe de obra: `[IMP] incoespacio_construction_certification` para rellenar el Responsable al crear la obra, y script para las existentes.
1. Núcleo: modelos, seguridad, cálculo de destinatarios, cron y chat, con un tipo de aviso de prueba en los tests.
2. Vista *Mis avisos*, posponer, silenciar y configuración de tipos.
3. Resumen de Dirección (diario y semanal de los lunes).
4. `incoespacio_assistant_invoice` con `bill_draft_no_obra`.
5. Piloto en AWS: crear los roles, asignarlos a 1–2 usuarios y dejar el aviso activo una semana.
6. Añadir `bill_no_partida` y `bill_ocr_failed`.
7. Segunda tanda: obras.

Tests en cada paso:
- Colector: qué entra y qué no («No es de obra», días de margen).
- Destinatarios: rol, responsable, unión sin duplicados.
- Permisos: un usuario sin acceso al registro no recibe el aviso.
- Ciclo de vida: deduplicación, resolución automática, reapertura y posponer.
- Chat: se reutiliza el canal, no se envía nada si no hay avisos y se respeta lo silenciado.

---

# Fase 1.1: ajustes antes del piloto

- Fecha: 2026-11-26
- Origen: la primera prueba en local con datos de muestra (funciona: agrupa, marca nuevos, tope y pie).
- Todo en local. Nada a GitHub ni a AWS hasta que funcione perfecto.

## 0. Poner `feat-assistant` al día con `main` ✅ (hecho 2026-11-26)

`main` ya tiene en producción las claves cifradas y `gemini-3.5-flash-lite` (`incoespacio_ai_core` 17.0.1.2.0). El asistente se prueba encima de eso.

- Cuidado: `docker-compose.yml` tiene un cambio local sin commitear (el puerto) y `main` también lo ha cambiado (`ODOO_SECRETS_KEY`). Git no deja hacer el merge con ese archivo modificado.
- Pasos: apartar el cambio local del compose (`git stash push docker-compose.yml`), `git merge origin/main`, recuperar el cambio (`git stash pop`) y resolver si choca. Los módulos del asistente están sin seguimiento y ocultos, así que no se ven afectados.
- Actualizar en la base local `incoespacio_ai_core` e `incoespacio_invoice_ocr_async`.
- Para pegar una clave en Ajustes en local hace falta `ODOO_SECRETS_KEY` en el `.env` local (otra llave distinta de la de producción) y la clave `ERP-INCOESPACIO-gemini-dev`. **Solo si se quiere probar el OCR en local:** el script de datos de muestra no llama a Gemini.

## A. Ordenar por antigüedad real ✅ (hecho 2026-11-26, en local)

**Problema:** dentro de cada tipo, el orden sale 8, 5, 10, 10, 7… días. El núcleo ordena por `first_seen` (cuándo lo vio el asistente, igual para todos), y la antigüedad real va metida en el texto del mensaje. El resumen la lee con una expresión regular (`hace N días`).

**Arreglo:**
- El colector devuelve una cuarta pieza: la fecha desde la que está pendiente (`since`). Para facturas, la fecha de entrada en el ERP (`create_date`, en hora de Madrid).
- `assistant.alert` guarda `pending_since` (Date). Si el colector no la da, vale `first_seen`.
- El núcleo calcula «pendiente desde hace N días» a partir de `pending_since` y ordena: nuevos primero y, dentro, lo más antiguo arriba.
- Los colectores dejan de escribir la antigüedad en el mensaje. Fuera la expresión regular del resumen: «más de 7 días» y «lo más atascado» usan `pending_since`.
- Se siguen aceptando colectores de tres piezas, para no romper los futuros módulos de avisos.
- Módulos tocados: `incoespacio_assistant`, `incoespacio_assistant_summary` e `incoespacio_assistant_invoice`.

Tests: orden por antigüedad, cálculo de días, colector de tres piezas y resumen sin depender del texto.

## B. Aviso «Borradores vacíos» ✅ (hecho 2026-11-26, en local)

**Problema:** sale `FACTU/2026/11/0001 · 0,00 €` sin proveedor: un borrador a medias.

**Decidido:** aviso aparte para Administración, y fuera de «sin obra».

Propuesta de regla (`bill_draft_empty`, en `incoespacio_assistant_invoice`):
- Factura o abono de proveedor en borrador, **sin proveedor y con total 0 €**, creado hace más de 2 días (`threshold_days`, editable).
- `bill_draft_no_obra` deja de incluir esos borradores, para que no salgan dos veces.
- Mensaje: «FACTU/… · creado por X» (la antigüedad la pone el núcleo), para saber a quién preguntar antes de borrarlo.
- No entran los que siguen en la cola del OCR (`pending`, `processing`) ni los que fallaron (`error`): esos van en «Cola OCR con error».
- Sin casilla de responsable: solo roles (Administración).

## C. Datos de muestra realistas en local ✅ (hecho 2026-11-26)

Producción está vacía. Hay que **fabricar** los datos con el volumen esperado.

**Script `scripts/assistant_demo_data.py`** (se lanza con `odoo shell`, **solo en local** y en una base aparte, `demo_asistente`; se niega a correr si la base se llama `incoespacio`):
- **Usuarios (5, como en producción):** 1 de dirección, 2 de administración y 2 jefes de obra. Contraseñas de prueba generadas por el script y apuntadas en un archivo local fuera de git.
- **10 obras** abiertas (presupuesto confirmado → obra con jefe), repartidas entre los 2 jefes. Una sin responsable.
- **12–15 proveedores.**
- **Unas 80 facturas de proveedor de un mes normal** (unas 8 por obra), con fechas de entrada escalonadas a lo largo del mes, la mayoría ya bien imputadas. Y, mezclados, **los casos del asistente**:
  - Borrador sin obra a 1, 3, 4, 5, 10 y 30 días (avisa desde 4).
  - Borrador sin obra con obra sugerida por el OCR (avisa también al jefe).
  - Borrador marcado «No es de obra» (**no** avisa).
  - Borradores vacíos (B).
  - Publicadas con obra y líneas sin partida.
  - OCR en error en borrador (avisa) y ya publicada (no avisa).
  - Abonos de varios casos.
- **Roles:** los crea el script (Administración, Jefe de obra y Dirección), los asigna a los usuarios y configura los tipos de aviso y el resumen de Dirección.
- **Repetible:** borra lo que creó la vez anterior (marcado con un prefijo) y vuelve a crearlo.
- **Simular días:** una opción que lanza el cron para varios días seguidos (`assistant_today`) y corrige alguna factura entre medias. Así se ve el ciclo completo: nuevo, pendiente, resuelto solo, pospuesto y el resumen del lunes.

Qué mirar, entrando con cada usuario:
- Que cada caso sale (o no sale) para quien debe.
- Cómo se ve el chat de cada perfil: administración, jefe de obra y dirección.
- Si con 80 facturas al mes el mensaje diario se lee bien o abruma (tope de 10 líneas, 4 días de margen).
- Posponer, silenciar y la resolución automática.
- El resumen de Dirección, diario y del lunes.

**Consecuencias de que producción esté vacía:**
- La migración de responsables no hace nada allí: no hay obras. Las nuevas nacerán con jefe.
- La fecha de corte de «sin partida» no hace falta en producción; no estorba.
- **El piloto es el arranque del ERP:** el asistente puede entrar desde el primer día, con avisos que crecen según se use.

### Cómo usarlo

```bash
# Base nueva (una vez): plan contable y módulos
docker exec incoespacio_web odoo -d demo_asistente --db-filter=demo_asistente -i l10n_es --stop-after-init --without-demo=all --workers=0 --http-port=8099
docker exec -i incoespacio_web odoo shell -d demo_asistente --db-filter=demo_asistente --no-http --workers=0 --http-port=8097 < scripts/ci_chart.py
docker exec incoespacio_web odoo -d demo_asistente --db-filter=demo_asistente -i base_user_role,incoespacio_assistant,incoespacio_assistant_summary,incoespacio_assistant_invoice --stop-after-init --without-demo=all --workers=0 --http-port=8099

# Datos (repetible) y simulación de una semana
docker exec -i incoespacio_web odoo shell -d demo_asistente --db-filter=demo_asistente --no-http --workers=0 --http-port=8097 < scripts/assistant_demo_data.py
docker exec -i -e DEMO_MODE=simular incoespacio_web odoo shell -d demo_asistente --db-filter=demo_asistente --no-http --workers=0 --http-port=8097 < scripts/assistant_demo_data.py
```

Para entrar: contenedor `demo_asistente_web` en `http://localhost:8071` (solo ve `demo_asistente`). Usuarios y contraseñas en `demo_asistente_usuarios.txt` (local, fuera de git).

### Resultado de la primera pasada (2026-11-26)

- 10 obras, 87 facturas y abonos de proveedor, 17 casos del asistente.
- Administración: 12 avisos cada uno (6 sin obra, 4 sin partida, 1 OCR, 1 vacío). Pedro (jefe): 3, los de sus obras. Marta (jefe): 1. La obra sin jefe solo llega a Administración. Dirección: resumen.
- Simulación: lo corregido el viernes se resuelve solo el lunes; lo pospuesto 1 día un viernes vuelve el lunes; el lunes llega el resumen semanal.
- Encontrado: la fecha de corte de «sin partida» oculta las facturas con fecha pasada. En la demo se vacía; en producción (base vacía) no afecta.

### A revisar en D

1. ✅ **El mensaje se repetía cada día** aunque no cambiara nada. Decidido y hecho (`incoespacio_assistant` 17.0.1.2.0): solo se escribe si hay algo nuevo (incluido lo que vuelve de posponer) y los lunes llega el repaso completo. En la demo, Ana pasa de 7 mensajes a 3 en la semana.
   - ✅ El resumen de Dirección pasa a **solo los lunes** (`incoespacio_assistant_summary` 17.0.1.2.0). «Resueltos desde el último resumen» cuenta la semana. En la demo, Elena pasa de 7 resúmenes a 1.
2. **Formato de importes en inglés** (`2,293.00 €`): los usuarios de demo están en inglés porque la base no tiene el español instalado. En producción, comprobar que los usuarios tienen `es_ES`.
3. **«Lunes pasado 0»** en la primera semana: normal, el asistente empezó esa semana.

## D. Ajustar con lo que salga de C

Días de margen, tope de líneas y qué roles reciben qué. Casi todo se cambia desde *Tipos de aviso*, sin código. Lo que se decida se apunta aquí y en la tabla de `docs/roles-guia.md`.

## Orden

0. Poner `feat-assistant` al día con `main`.
1. A (código + tests).
2. B (código + tests).
3. C: script y base `demo_asistente`.
4. Revisión entrando con cada usuario.
5. D.
6. Cuando funcione perfecto: commit y PR de `server-backend`, `incoespacio_construction_certification` (responsable de obra) y los tres módulos del asistente. Instalar en producción antes del arranque.

## Decisiones de la fase 1.1 (2026-11-26)

- **Usuarios de muestra:** los decide el script. Serán 1 de dirección, 2 de administración y 2 jefes de obra.
- **Roles:** los crea el script por defecto (Administración, Jefe de obra y Dirección) y los asigna a los tipos de aviso y al resumen. `docs/roles-guia.md` queda para hacerlo a mano en producción.
- **Borradores vacíos:** sin proveedor y a 0 €, con 2 días de margen.

---

# Reglas para la IA en el asistente (fases futuras)

Principio: **la IA lee y propone; el código decide; una persona confirma.** La IA nunca tiene una vía para modificar el ERP por sí misma.

1. **Sin credenciales.** Gemini no recibe acceso a la base ni a la API de Odoo. Recibe el texto que nuestro código le manda y devuelve texto o JSON. Si devuelve algo raro, el código lo descarta.
2. **Solo lectura sobre el ERP.** Para preguntar, solo herramientas cerradas escritas por nosotros (`facturas_pendientes(proveedor)`, `estado_obra(obra)`…), ejecutadas **con los permisos del usuario que pregunta** (`env.user`, nunca `sudo()`). Nada de SQL libre ni de `search_read` genérico.
3. **Propuestas en su propia tabla.** Si la IA sugiere algo («esta factura es de la obra X»), se guarda en un modelo propio de sugerencias, no en la factura. Solo se aplica cuando una persona pulsa *Aceptar*, por el código normal y con sus permisos. Es el mismo patrón que ya usa el OCR: la IA rellena un borrador y una persona lo valida.
4. **Sin salida al exterior.** La IA no puede mandar correos, llamar a URLs ni escribir a terceros. Las facturas entran por correo y un PDF puede llevar instrucciones escondidas (inyección de prompt); sin salidas, lo peor que pasa es una respuesta equivocada.
5. **Interruptor y límites.** Un ajuste para apagar la IA sin desplegar, tope de gasto diario y registro de cada llamada (quién, qué herramienta, tokens). Si la IA falla o está apagada, los avisos por reglas siguen funcionando.
6. **Datos a Google.** Solo con una clave de pago (la capa gratuita puede usar los datos para entrenar).

## Datos de partida (2026-11-26)

- 5 usuarios en el ERP por el momento.
- Producción vacía: el ERP aún no se usa.
- API de Gemini de pago. Presupuesto orientativo de IA: unos 100 €/mes si es útil.
- La IA solo lee la base de datos; puede escribir lo que haga falta en el chat. Plan de seguridad: `docs/asistente-ia-seguridad.md`.

## Preguntas abiertas (actualizado)

Decidido el 2026-11-26:
- **Borradores vacíos:** aviso aparte, «Borradores vacíos», para Administración (opción B.2).
- **Volumen:** unas 10 obras a la vez. Supuesto para los datos de muestra: unas 8 facturas de proveedor por obra y mes (unas 80 al mes).
- **Arranque del ERP:** en unas semanas.
- **IA:** de momento en el chat; más adelante, un botón flotante abajo a la derecha.
- **2FA, clave separada y 90 días de registro:** según lo recomendado (`docs/asistente-ia-seguridad.md`).

- **La IA la usan los 5 usuarios.** Nunca lee secretos (lista de `docs/asistente-ia-seguridad.md` §2.13).

Siguen abiertas:
1. **Notas internas del chatter:** propuesta en §2.13 (solo notas internas, nunca correos externos ni Discuss), pendiente de confirmar.
2. **PDF:** propuesta en §2.13 (solo el texto del OCR en las sugerencias), pendiente de decidir.

## Avisos añadidos (2026-11-26)

De prueba: se quitan los que no sirvan (desactivar en *Ajustes → Tipos de aviso*).

| Aviso | Módulo | Margen | A quién |
|---|---|---|---|
| Facturas de cliente vencidas | incoespacio_assistant_invoice | 0 días desde el vencimiento | Administración y Dirección |
| Certificaciones aprobadas sin facturar | incoespacio_assistant_construction (nuevo) | 3 días desde la fecha de la certificación | Administración |
| Certificaciones en borrador | incoespacio_assistant_construction | 7 días desde que se creó | Jefe de la obra |
| Obras sin certificar | incoespacio_assistant_construction | 30 días desde la última certificación o la confirmación | Jefe de la obra |

Encontrado: el jefe de obra necesita «Ventas: Usuario: todos los documentos» en su rol; con «solo sus documentos» no ve las obras que no creó y el aviso no le llega.

## Tareas: aplazado (2026-11-26)

Sin actividad real todavía no se sabe qué tareas se olvidan. Se decide cuando haya uso: lo más probable, tareas periódicas comprobadas en el ERP (con fecha límite), que reutilizan el mecanismo de avisos.

Probado en la demo por el usuario: enlaces del chat abren la ficha; Ana y Pedro entienden los avisos y el «→ Qué hacer».
