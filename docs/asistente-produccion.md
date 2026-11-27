# IncoBot: pasos para subirlo a producción

Producción está vacía (2026-11-27): no hay datos que migrar. IncoBot se instala **apagado** y se enciende al final, en Ajustes.

## 1. Qué tiene que estar en `main` antes

En este orden (los tres primeros no dependen del asistente y pueden subir antes):

| PR | Qué | Rama |
|---|---|---|
| Wiki | `docs/wiki/` (importar BC3) | `feat-wiki` (ya en GitHub) |
| Coste objetivo | Cambiar la cantidad no devuelve el P.U. a la tarifa (2 tests que fallaban) | `fix-bc3-planned-cost-precio` |
| Márgenes | Previsión, desviación con coste adelantado y margen real total (`docs/margenes-correccion.md`) | por crear desde `main` |
| IncoBot | Todos los módulos del asistente, `server-backend` (OCA, para `base_user_role`), responsable de obra al confirmar, montaje de la wiki y documentación | `feat-assistant` |

## 2. En el servidor

1. `git pull` de `main`.
2. **`config/odoo.conf`** (el real, no está en git): añadir `/mnt/extra-addons/server-backend` a `addons_path`, como en `config/odoo.conf_example`.
3. **`.env`**: ya tiene `ODOO_SECRETS_KEY` desde el endurecimiento de claves. Comprobarlo.
4. `docker compose up -d --build` (cambia `docker-compose.yml`: la wiki se monta en `/mnt/wiki`).
5. Actualizar lo que ya estaba instalado:
   ```
   python scripts/update_modules.py incoespacio_construction_certification incoespacio_bc3_planned_cost incoespacio_construction_margins_forecast
   ```
   (`incoespacio_construction_certification` trae una migración: las obras sin responsable quedan con quien las creó.)
6. **Instalar** IncoBot (`update_modules.py` solo actualiza; esto instala, y las dependencias vienen solas):
   ```
   docker exec incoespacio_web odoo -i incoespacio_assistant_summary,incoespacio_assistant_invoice,incoespacio_assistant_construction,incoespacio_assistant_ai_wiki,incoespacio_assistant_ai_catalog,incoespacio_assistant_ai_invoice,incoespacio_assistant_ai_construction,incoespacio_assistant_ai_feedback -d <base> --stop-after-init --workers=0 --max-cron-threads=0 --http-port=8098
   ```
7. `docker restart incoespacio_web`.

## 3. Configurar (IncoBot sigue apagado)

1. **Roles** (Ajustes > Usuarios > Roles): crear los de la empresa y asignar a cada persona. Ver `docs/roles-guia.md`. Decidir quién ve costes y márgenes: hoy, quien tenga **Facturación**.
2. **IncoBot > Configuración > Tipos de aviso**: a qué roles va cada aviso y con qué margen de días.
3. **Ajustes > IncoBot**:
   - Roles que reciben el resumen de Dirección.
   - Preguntas a la IA: encendido, modelo (3.5 Flash-Lite) y gasto máximo al mes.
4. **Clave de Gemini** de producción en Ajustes (se guarda cifrada): comprobar que su estado sale como guardada. Es la que tiene la restricción de IP del servidor; la de pruebas local no vale allí.
5. **Aviso al equipo**: que IncoBot usa la IA de Google, qué datos ve y que los administradores pueden leer sus preguntas y valoraciones.

## 4. Encender y comprobar

1. Ajustes > IncoBot > **IncoBot activo**.
2. Preguntar algo en el chat de IncoBot como administrador («¿qué facturas de proveedor hay en borrador?»).
3. Al día siguiente, a las 8:00 (hora de Madrid, solo laborables), sale el primer resumen de avisos.
4. Revisar IncoBot > Configuración > Lo que IncoBot no sabe tras unos días.

## 5. Si algo va mal

- Ajustes > IncoBot > desmarcar **IncoBot activo**: deja de mandar avisos, de contestar y de tachar. Los datos se quedan.
- Solo la IA: desmarcar **Preguntas a la IA** (los avisos siguen).
