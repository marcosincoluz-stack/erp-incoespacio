# IA en el circuito de obra — ideas para contrastar

- Fecha: 2026-09-11
- Para: oficina / obra / administración (no es un plan de desarrollo cerrado)
- Premisa: **apoyar, no cerrar solo.** La IA propone; una persona confirma.
- Stack: reutilizar `incoespacio_ai_core` + OCR de facturas. No hace falta un agente nuevo.

El circuito BC3 → certificar → factura (retención a mano; default 0 %) → devolución a `430800` ya funciona con reglas. Un modelo no debe decidir importes, cuentas ni el %. Decisiones de producto y espera de BC3: `docs/obra.md`.

---

## Dónde sí ayuda la IA

| Qué | Cómo | Riesgo | ¿Os ahorraría tiempo? |
|---|---|---|---|
| Factura de proveedor → **sugerir obra** (`project_id`) | El OCR lee el PDF; el modelo propone el pedido (ej. P2600330) por cliente y texto. Tú confirmas. El campo sigue opcional: muchas facturas OCR no son de obra. | Bajo | |
| **Chat en el pedido** | Preguntas del tipo “¿cuánto retenido?”, “¿margen?”. Solo lee campos, no escribe. | Bajo | |
| **Modificado** desde PDF/mail de dirección de obra | Extrae partidas y las deja en borrador (Añadir modificado). Tú revisas cantidad y precio. | Medio | |
| **Mediciones a origen** desde fotos / WhatsApp | Posible a medio plazo. La medición legal sale de Presto. La IA **no** debe escribir `Med. Origen` sin que alguien pulse OK. | Alto | |

La de más retorno día a día es la primera: hoy la factura entra por OCR y la obra se imputa a mano; sin eso el margen se queda a 0.

---

## Esto no es IA (son clics)

Encadenar botones y fechas es automatización normal, no un modelo:

- Siguiente certificación con Med. Anterior
- 5 % y línea `430800`
- Factura de devolución de retención
- Crear proyecto al confirmar un BC3
- Copiar líneas de modificado a la cert.

Si molestan los clics, se puede hacer **Aprobar y crear factura** en un gesto, o un aviso/borrador de devolución a los 12 meses. Confirmar facturas y rellenar mediciones siguen siendo humanos.

No queremos un agente que “lleve la obra” (certificar, facturar, devolver retención). Eso ya es el circuito.

---

## Cómo contrastarlo

Marcad en la tabla la última columna (sí / no / más adelante) y anotad un ejemplo real (un PDF, un mail, una foto de tajo). Con eso se prioriza; sin caso de uso no se construye.
