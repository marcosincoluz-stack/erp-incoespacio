# Incoespacio: Asistente, avisos hechos

Tacha en los mensajes del chat de IncoBot los avisos que ya se han hecho, sin mandar otro mensaje. Plan completo: `docs/asistente-avisos-tachado.md`.

Va aparte de `incoespacio_assistant` porque el módulo base está cerca del tope de 500 líneas.

## Hecho (paso 1)

- `message_ids`: los mensajes donde ha salido cada aviso. Se rellena al mandar el resumen diario de cada persona (solo las líneas que se muestran, como mucho 10 por tipo) y el resumen de Dirección (las de «Lo más atascado»), con el gancho `_link_message` del módulo base.
- `resolved_by_id`: quién lo arregló, solo si se sabe seguro. Cualquier cambio de estado que no lo diga (revisión diaria, comprobación al mirar, reapertura) lo deja vacío.

## Hecho (paso 2)

- Cada línea del resumen lleva la clase `o_incobot_alert_<id>`. Al cambiar el estado de un aviso se tocan los mensajes donde sale: la línea se tacha con «✓ Hecho» (o «✓ Hecho por …» si lo tenían varias personas y se sabe quién fue) y la cabecera suma « · N hechos» o « · todo hecho». Al reabrirse, vuelve a la normalidad.
- El resto del mensaje no se toca. CSS en `static/src/scss/done.scss`.

## Hecho (paso 3)

- `_recheck_later(records)`: lo llaman los ganchos al guardar. Apunta los registros y, justo antes del commit, comprueba sus avisos abiertos; lo ya hecho se resuelve para todos con el nombre de quien guardó (sin nombre si guarda el OCR o un cron). Si falla, no bloquea el guardado.
- Ganchos de facturas y líneas en `incoespacio_assistant_invoice`.

## Hecho (paso 4)

- Ganchos de certificaciones (y su obra) y de obras en `incoespacio_assistant_construction`.

## Hecho (paso 5)

- Las comprobaciones de siempre (revisión diaria, al abrir «Mis avisos», reapertura) también tachan y destachan, porque cambian el estado con `write`. Con sus tests.

## Respuestas de la IA

- En las respuestas de IncoBot el aviso va en el enlace (`a.o_incobot_link.o_incobot_alert_<id>`): al hacerse se tacha la línea entera del enlace (de un salto de línea al siguiente) y el sello «✓ Hecho» va al final. Lo marca y lo apunta `incoespacio_assistant_ai_data`.
- «✓ Hecho» es un sello verde con fondo, en el resumen y en la IA.

## Hecho (paso 6)

- Probado en la demo por el usuario con Pedro.
