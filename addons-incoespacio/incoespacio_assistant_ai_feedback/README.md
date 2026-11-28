# Incoespacio: Asistente con IA, valoraciones

Para saber qué pide el equipo y qué falla, antes de añadir más funciones.

- **Lo que no sabe contestar.** Cuando IncoBot responde «eso no lo puedo consultar todavía» o «eso aún no está en la wiki», la pregunta queda marcada (`gap`: datos o wiki).
- **Valorar cada respuesta.** Debajo de cada respuesta hay dos iconos (pulgar arriba y abajo, de Font Awesome, en contorno). Al pulsar uno se queda relleno y en color; pulsarlo otra vez lo quita. Solo puede valorar quien preguntó (`rate`, comprobado en el servidor). Las respuestas con error no llevan botones.
- **Ajustes > Lo que IncoBot no sabe** (solo administradores): las preguntas sin respuesta y las marcadas como no útiles, con filtros y agrupar por persona.

El clic lo recoge un parche de `Message.onClick` (`static/src/js/rating.js`); el servidor repinta el mensaje.
