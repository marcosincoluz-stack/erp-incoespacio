# Incoespacio: Asistente con IA

Preguntas a IncoBot Asistente en el chat de cada usuario.

Dependencias: incoespacio_assistant, incoespacio_ai_core.

- El usuario escribe en su chat con IncoBot. La pregunta entra en una cola (`assistant.ai.question`) y el bot responde «Pensando…» al momento; un cron la contesta y reemplaza ese mensaje por la respuesta.
- En *Ajustes → IncoBot*: interruptor, modelo y gasto máximo al mes. El modelo es el de IncoBot (si no se elige, el del OCR) y su precio va en el código (`PRICES`; «última versión» se cuenta al más caro). El tope de 30 preguntas por persona y día sigue por dentro (`incoespacio_assistant_ai.daily_limit`), sin pantalla. Al llegar a un tope, no se llama a la IA.
- La cola es también el registro: pregunta, respuesta, tokens y coste. Solo la ven los administradores en *Ajustes → Preguntas a la IA*.
- Plan y seguridad: `docs/asistente-ia-fase2.md` y `docs/asistente-ia-seguridad.md`.
