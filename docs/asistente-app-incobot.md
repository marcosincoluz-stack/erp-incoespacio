# Plan: app IncoBot

Estado: hecho (2026-11-27). Probado por el usuario en la demo. Solo en local, como el resto del asistente.

## 1. Qué se quiere

Que todo lo de IncoBot esté en una app propia con su icono, como Proyecto o Facturación, en vez de repartido por el menú de Ajustes y por Conversaciones. Pedido por el usuario al ver que el menú de arriba de Ajustes se llenaba de cosas nuestras y que «Asistente» salía sin icono en la barra lateral de Ajustes.

## 2. Cómo está hoy

| Qué | Dónde | Módulo |
|---|---|---|
| Mis avisos | Conversaciones > Mis avisos | `incoespacio_assistant` |
| Tipos de aviso | Ajustes (menú de arriba), solo administradores | `incoespacio_assistant` |
| Preguntas a la IA | Ajustes (menú de arriba), solo administradores | `incoespacio_assistant_ai` |
| Lo que IncoBot no sabe | Ajustes (menú de arriba), solo administradores | `incoespacio_assistant_ai_feedback` |
| Sección de ajustes | Ajustes > «Asistente», sin icono | `<app name="incoespacio_assistant">` y bloques de IA y Dirección |
| Todos los avisos (Dirección) | Sin menú: solo desde el enlace del resumen de Dirección | `incoespacio_assistant_summary` |

## 3. Cómo quedará

```
IncoBot (icono en la pantalla de inicio, todo el equipo)
├── Mis avisos                      todo el equipo
├── Todos los avisos                administradores (ver 6.1)
└── Configuración                   administradores
    ├── Tipos de aviso
    ├── Preguntas a la IA
    ├── Lo que IncoBot no sabe
    └── Ajustes                     abre Ajustes en la sección IncoBot
```

- En Ajustes, «Asistente» pasa a llamarse **IncoBot** y sale con el icono (Odoo lo coge de `incoespacio_assistant/static/description/icon.png`).
- El menú de arriba de Ajustes vuelve a ser solo de Odoo.
- «Mis avisos» sale de Conversaciones: un solo sitio. El enlace «Ver todos mis avisos» del chat sigue funcionando (va a la acción, no al menú).
- Quien no es administrador solo ve IncoBot > Mis avisos.

## 4. Piezas

| Pieza | Módulo | Qué |
|---|---|---|
| Icono | `incoespacio_assistant` | `static/description/icon.png` (y SVG fuente), estilo de los iconos de Odoo 17 |
| Menú raíz y «Mis avisos» | `incoespacio_assistant` | `menu_incobot_root` con `web_icon`; `menu_my_alerts` cambia de padre |
| Configuración y Ajustes | `incoespacio_assistant` | `menu_incobot_config` (administradores); acción de Ajustes con `context="{'module': 'incoespacio_assistant'}"`; «Tipos de aviso» cambia de padre |
| Preguntas a la IA | `incoespacio_assistant_ai` | `menu_assistant_ai_questions` cambia de padre |
| Lo que IncoBot no sabe | `incoespacio_assistant_ai_feedback` | `menu_assistant_ai_gaps` cambia de padre |
| Todos los avisos | `incoespacio_assistant_summary` | menú nuevo a `action_all_alerts_checked` (si se decide en 6.1) |
| Nombre en Ajustes | `incoespacio_assistant` | `<app string="IncoBot">` |

Solo XML y una imagen: no cuenta para el tope de 500 líneas (el base está en 491).

## 5. Pasos

| Paso | Qué | Cómo se comprueba |
|---|---|---|
| 1 ✅ | Icono: 3 propuestas; elegido el bocadillo con check | El usuario |
| 2 ✅ | App IncoBot con «Mis avisos» y Configuración; mover los tres menús de Ajustes | Test de menús: un usuario normal ve solo Mis avisos; un administrador lo ve todo; nada nuestro bajo `base.menu_administration` |
| 3 ✅ | Ajustes: «IncoBot» con icono y el menú Configuración > Ajustes que lleva a esa sección | Comprobado en la demo |
| 4 ✅ | Todos los avisos, para administradores | 1 test (82 en total) |
| 5 ✅ | Demo: entrar como Pedro y como administrador | El usuario |

Cada paso se cierra con la suite en verde y la demo actualizada.

## 6. Por decidir

1. ~~«Todos los avisos» en la app~~: decidido, menú para administradores (`incoespacio_assistant_summary.menu_all_alerts`). Si más adelante lo quieren los roles del resumen de Dirección, se amplía.
2. ~~El icono~~: decidido, el bocadillo.

## 7. Límites

- En producción, al actualizar, los menús cambian de sitio solos (no son `noupdate`). Los marcadores del navegador con la URL antigua de un menú pueden abrir otro sitio: poco probable y sin riesgo.

## 8. Notas

- Icono (2026-11-27): bocadillo morado con un check verde (el mismo verde que «✓ Hecho»), 256 px, en `incoespacio_assistant/static/description/icon.png`. Se dibujó con PIL; el script no está en el repo.
- Pasos 2 y 3 (2026-11-27): `menu_incobot_root` (todo el equipo), «Mis avisos» sale de Conversaciones, `menu_incobot_config` solo para administradores con Tipos de aviso, Preguntas a la IA, Lo que IncoBot no sabe y Ajustes (`action_incobot_settings`, abre la sección IncoBot). En Ajustes, «Asistente» pasa a «IncoBot». 3 tests de menús (post_install, para ver también los de la IA): 81 en total. En la demo, Pedro solo ve IncoBot > Mis avisos y en el menú de Ajustes ya solo quedan los de Odoo.
- Ajustes > IncoBot lleva también enlaces a «Preguntas a la IA» y «Lo que IncoBot no sabe» (estilo «→ Manage Users» de Odoo). El icono no salía en la barra lateral por la caché del navegador (la imagen se pidió antes de existir): con Ctrl+F5 sale.
