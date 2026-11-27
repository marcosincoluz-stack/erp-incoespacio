# Roles de usuario (base_user_role): guía rápida

- Módulo: **User roles** (`base_user_role`, OCA, en `addons/server-backend/`).
- Objetivo: crear *Administración*, *Jefe de obra* y *Dirección* una vez, y asignar cada persona a su rol con un clic.
- Ensayar primero en local (con la copia de producción neutralizada, ver fase 1.1 C) y apuntar aquí los grupos de cada rol. En producción solo habrá que repetirlo.

## Lo que hay que saber antes de tocar nada

1. **Un rol es una plantilla de permisos.** Se le marcan grupos (Ventas: Usuario, Contabilidad: Facturación…) y los usuarios del rol reciben exactamente esos grupos.
2. **Los roles se suman.** Si alguien tiene *Administración* y *Dirección*, tiene los grupos de los dos.
3. ⚠️ **Con un rol asignado, los permisos ya no se tocan a mano en ese usuario.** El módulo recalcula sus grupos a partir de sus roles: nada más y nada menos. Si marcas una casilla a mano en la pestaña de permisos, desaparece en el siguiente recálculo. Lo que falte, se añade **al rol**.
4. ⚠️ **No asignes roles a tu propio usuario administrador** hasta tener un rol que incluya *Ajustes: Administración*. Si le das un rol sin ese grupo, pierdes el acceso a Ajustes. Lo seguro es dejar el admin sin roles.
5. **Los grupos propios de Incoespacio también cuentan:** *Facturación: Validar y Publicar Facturas*, Soporte, IT y Alertas de compra de IncoBot. Si un rol no los incluye, quien tenga ese rol los pierde.

## Dónde está

*Ajustes → Usuarios y compañías → Roles* (con el modo desarrollador activo si no aparece).

En la ficha de cada usuario sale una pestaña **Roles**.

## Crear un rol: la forma rápida

En vez de marcar grupo a grupo, se parte de una persona que ya tiene bien los permisos:

1. *Ajustes → Usuarios*: abre a alguien que hoy trabaje como, por ejemplo, administración.
2. Menú **Acción (⚙) → Crear rol desde el usuario**.
3. Ponle nombre («Administración»). El rol nace con los grupos de esa persona.
4. Abre el rol, repasa la pestaña **Grupos** y quita lo que sea personal de esa persona y no del puesto.

## Crear un rol desde cero

1. *Roles → Nuevo*. Nombre.
2. Pestaña **Grupos**: añade los grupos. Basta con el más alto de cada app, porque incluye los inferiores (*Contabilidad: Facturación* ya implica *Usuario interno*, por ejemplo).
3. Guardar.

## Asignar personas

Desde el rol (pestaña **Usuarios**) o desde el usuario (pestaña **Roles**). Cada línea admite:
- **Desde / Hasta:** fechas opcionales. Útil para sustituciones: «Pedro es jefe de obra del 1 al 15 de agosto». Un cron diario activa y desactiva según las fechas.
- **Activo:** se calcula con las fechas.

Al guardar, los grupos del usuario se recalculan solos.

## Cambiar permisos a todo un puesto

Edita el rol y añade o quita el grupo. Se aplica a todos sus usuarios a la vez. Esta es la ventaja frente a ir usuario por usuario.

## Rol por defecto para usuarios nuevos

*Usuarios →* usuario plantilla «Default User» (puede estar archivado: quita el filtro). Los roles que tenga se ponen a cada usuario nuevo.

## Roles de Incoespacio (rellenar al ensayar)

| Rol | Grupos | Quién | Avisos del asistente |
|---|---|---|---|
| Administración | _(apuntar)_ | _(apuntar)_ | Marcado en: facturas sin obra, sin partida, vacías, OCR con error, facturas de cliente vencidas y certificaciones aprobadas sin facturar |
| Jefe de obra | Incluir **Ventas: Usuario: todos los documentos** (si no, no ve las obras que no creó y no le llegan sus avisos) | _(apuntar)_ | **No** se marca en ningún tipo: cada jefe recibe los de sus obras por ser el responsable del proyecto (certificaciones en borrador, obras sin certificar, facturas de sus obras) |
| Dirección | _(apuntar)_ | _(apuntar)_ | Marcado en facturas de cliente vencidas, y en *Ajustes → Asistente → Roles que reciben el resumen* |

## Checklist para producción

1. Copia de seguridad de producción.
2. Instalar **User roles** (tras el `git pull` y añadir `server-backend` al `addons_path` del `odoo.conf` del servidor).
3. Crear los roles con los grupos apuntados en la tabla.
4. Asignar **primero a un usuario de prueba**, entrar con él y comprobar que ve lo que debe.
5. Asignar al resto. El admin, sin roles.
6. En el asistente: roles en cada tipo de aviso y el rol de Dirección en Ajustes.
