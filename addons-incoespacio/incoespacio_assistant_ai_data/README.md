# Incoespacio: Asistente con IA, consultas

Lo común a las consultas de IncoBot sobre el ERP, y la consulta `mis_avisos`.

- `_rows()`: lectura para las herramientas. Siempre con el usuario que pregunta, nunca con sudo: aplica sus permisos, sus reglas de registro y los grupos de cada campo. Como mucho 20 filas, más el total.
- Lista negra fija de modelos (parámetros, secretos, usuarios, cuentas bancarias, mensajes, chats y la cola de preguntas) y de campos (`vat`, `bank_ids`, contraseñas, tokens, IBAN…). Se aplica también al administrador.
- Si un campo calculado necesita algo que el usuario no ve, sale «sin permiso» y el resto se lee igual.
- Enlaces: cada fila lleva su registro (`_link`), que se quita antes de mandarlo a Gemini. Al publicar la respuesta, los nombres de esos registros que aparezcan en el texto se convierten en enlaces (`data-oe-model` / `data-oe-id`, como en los avisos). Los enlaces los pone este código, nunca la IA: lo que escribe el modelo llega siempre escapado.
- Las consultas de facturas y de obra están en `extras/invoice/incoespacio_assistant_ai_invoice` y `extras/construction/incoespacio_assistant_ai_construction`.
