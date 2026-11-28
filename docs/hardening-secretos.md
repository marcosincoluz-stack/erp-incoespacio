# Claves de API fuera de la base (en claro)

- Fecha: 2026-11-26
- Objetivo: que las claves de API (hoy, la de Gemini) **no queden legibles** en la base de datos ni, por tanto, en los backups. Se siguen pegando desde *Ajustes*.
- Cuándo: antes del arranque en producción, mientras la base está vacía.

## Alcance

**Sí:**
- Guardar las claves de API cifradas en la base (sprint 1).
- Rotar y restringir la clave de Google (sprint 2).

**No se toca (decidido el 2026-11-26):** backups (`scripts/backup.py`, `restore.py`, S3, IAM), correo de Outlook, contraseñas del servidor ni 2FA. Los backups funcionan bien y se quedan como están.

## Por qué hace falta rotar la clave

Los backups que ya existen llevan la clave actual **en claro**. Cifrarla a partir de ahora no arregla los antiguos. Por eso, al terminar, se crea una clave nueva en Google y se borra la vieja: la que quede en los backups antiguos ya no servirá.

## Sprint 0: preparación (½ hora)

1. Acceso a Google Cloud (proyecto de la clave actual) y por SSH al servidor.
2. Un sitio seguro para guardar la llave maestra: un gestor de contraseñas (Bitwarden, 1Password, KeePassXC).
3. ~~Apuntar la IP pública fija del servidor de AWS~~: IP elástica `35.43.198.227` (comprobado el 2026-11-26).
4. Trabajar en local, en una rama aparte desde `main`.

## Sprint 1: la clave de Gemini, cifrada en la base (1–2 días, código)

**Objetivo:** la clave se sigue pegando en *Ajustes* como hasta ahora, pero en la base (y en los backups) solo queda **cifrada**. Sin la llave maestra, que vive en el `.env` del servidor, no sirve para nada.

**Decisión 2026-11-26:** las claves se pegan desde la interfaz de Odoo. No se usa una variable de entorno para cada clave.

### Cómo funciona

```
Ajustes (pegas la clave) ──► Odoo la cifra con la llave maestra ──► base: gAAAAB…(ilegible)
                                       ▲
                       .env del servidor: ODOO_SECRETS_KEY (no entra en git ni en backups)

Al usarla: Odoo lee el texto cifrado ──► lo descifra en memoria ──► llamada a Gemini
```

- **Llave maestra:** `ODOO_SECRETS_KEY` en el `.env` del servidor, generada una vez (`Fernet.generate_key()`). Se guarda también en el gestor de contraseñas.
- **Cifrado:** Fernet (AES + HMAC) de la librería `cryptography`, que ya viene en la imagen de Odoo (versión 3.4.8 comprobada en local).
- Un backup robado contiene la clave cifrada; sin el `.env` del servidor no se puede descifrar.
- **Si se pierde la llave maestra** no se pierde nada importante: se genera otra y se vuelven a pegar las claves de API en Ajustes.

### Código (en `incoespacio_ai_core`)

1. **Utilidad de secretos** reutilizable para cualquier clave futura (asistente, otros servicios):
   - `_secret_set(nombre, valor)`: cifra con `ODOO_SECRETS_KEY` y guarda el texto cifrado en `ir.config_parameter`.
   - `_secret_get(nombre)`: lee y descifra en memoria. Nunca lo escribe en el log.
   - Si `ODOO_SECRETS_KEY` no existe, **no guarda nada** y avisa en Ajustes («falta la llave maestra en el servidor»). Nunca cae a guardar en claro.
2. **Campo de Ajustes de solo escritura:**
   - Para pegar una clave nueva.
   - Tras guardar, no vuelve a mostrar el valor: solo «Configurada · termina en …a1B2» y la fecha del último cambio.
   - Para cambiarla, se pega otra encima. Botón *Borrar clave*.
   - Solo visible para administradores (`base.group_system`).
3. Cambiar los dos sitios que hoy leen el parámetro en claro para que usen `_secret_get`:
   - `incoespacio_ai_core/models/ai_ocr_service.py`
   - `incoespacio_invoice_ocr_async/models/account_journal.py`
4. **Migración:** si existe el parámetro antiguo en claro y hay llave maestra, cifrarlo y borrar el antiguo. Si no hay llave, dejarlo y avisar.
5. **Registro de cambios:** quién cambió la clave y cuándo (sin el valor), en el chatter de Ajustes o en el log.
6. **Que la clave no se filtre por errores:** revisar que las excepciones de `requests` y `ocr_error_message` no incluyen cabeceras ni la clave. Se mantiene en la cabecera `x-goog-api-key`, nunca en la URL.
7. `docker-compose.yml`: pasar `ODOO_SECRETS_KEY=${ODOO_SECRETS_KEY}` al servicio `web`.
8. Subir versión de `incoespacio_ai_core` e `incoespacio_invoice_ocr_async`.

### Tests

- Guardar una clave deja en la base un texto cifrado distinto de la clave, y `_secret_get` devuelve la original.
- Sin `ODOO_SECRETS_KEY` no se guarda nada en claro y Ajustes avisa.
- Con otra llave maestra distinta, el descifrado falla limpio (sin romper el OCR con un error ilegible) y Ajustes pide volver a pegar la clave.
- Ajustes nunca devuelve el valor, solo los 4 últimos caracteres.
- La migración cifra el parámetro antiguo y lo borra.
- Un fallo de Gemini no deja la clave en `ocr_error_message` ni en el log.

### En el servidor (tras el despliegue)

1. Generar la llave maestra y añadir `ODOO_SECRETS_KEY=...` al `.env`. Guardarla en el gestor de contraseñas.
2. `docker compose up -d web`.
3. En *Ajustes*, pegar la clave **nueva** de Google (sprint 2) y probar el OCR con una factura.
4. Comprobar en *Parámetros del sistema* que el valor es ilegible.

Criterio de hecho: el OCR funciona, en la base solo hay texto cifrado y buscar la clave en un backup recién hecho no encuentra nada.

Marcha atrás: el código antiguo leía el parámetro en claro; volver a la versión anterior y pegar la clave otra vez.

### Límite honesto

Un administrador de Odoo con acceso al servidor, o capaz de ejecutar código en Odoo, puede descifrar la clave: el ERP necesita usarla. El cifrado protege **los backups y las copias de la base**, no frente a un administrador. Por eso importa también la restricción por IP de Google (sprint 2).

## Sprint 2: la clave de Google, rotada y restringida (½ día, sin código)

**Objetivo:** que una clave robada sirva para muy poco y cueste poco.

Tareas en Google Cloud:
1. **Crear una clave nueva** solo para el OCR. (Más adelante, otra distinta para el asistente con IA.)
2. **Restricción de API:** solo «Generative Language API». Con eso no sirve para Maps, Drive ni otros servicios.
3. **Restricción de aplicación por IP:** solo la IP elástica del servidor de AWS, `35.43.198.227` (instancia `i-086ba2031ed634b90`, `eu-south-2`, sin IPv6). Las llamadas desde los contenedores Docker salen por esa IP. Para desarrollo en local, **otra clave aparte**, con su propio tope bajo.
4. **Presupuesto y alertas** en Facturación: alerta al 50 %, 90 % y 100 % de un tope mensual (por ejemplo 30 € para el OCR).
5. **Cuotas** de la API: límite de peticiones por minuto y por día acorde al uso (unas 80 facturas al mes dan mucho margen).
6. Pegar la clave nueva en *Ajustes* (sprint 1) y probar.
7. **Borrar la clave antigua.** Los backups viejos la llevan, y así queda inservible.
8. Guardar en el gestor de contraseñas: qué clave es cuál, sus restricciones y la fecha de creación.

Criterio de hecho: la clave antigua no existe, la nueva solo funciona desde la IP del servidor (probar desde otro equipo: debe fallar) y las alertas de presupuesto están activas.

## Orden y despliegue

1. Sprint 1 en local, con tests y probado con el OCR.
2. Sprint 2: crear la clave nueva en Google (sin borrar aún la vieja).
3. Despliegue a producción: `git pull`, añadir `ODOO_SECRETS_KEY` al `.env`, `docker compose up -d web` y actualizar los módulos.
4. Pegar la clave nueva en *Ajustes* y probar el OCR.
5. Borrar la clave vieja en Google.

## Dudas por resolver

1. **¿Usáis algún gestor de contraseñas** para guardar la llave maestra?
2. ~~¿El servidor tiene IP elástica?~~ Sí: `35.43.198.227`. La restricción por IP es posible.

## Notas de infraestructura (fuera de alcance)

- La entrada al ERP pasa por **Cloudflare** (usuarios → Cloudflare → EC2). No afecta a este plan: las llamadas de Odoo a Google **salen** directamente desde la EC2 por `35.43.198.227`, así que la restricción por IP de la clave sigue siendo válida.
- Para más adelante: comprobar que el grupo de seguridad de la EC2 solo acepta 80/443 desde los rangos de IP de Cloudflare. Si no, se puede entrar directamente por `https://35.43.198.227` saltándose Cloudflare (y su protección).

---

# Estado (2026-11-26)

Sprint 1 hecho en local, en la rama `hardening-secretos` (copia de trabajo `../incoespacio-erp-hardening`). Sin commit.

- `incoespacio_ai_core` 17.0.1.1.0: modelo `incoespacio.secret` (métodos privados, no llamables por RPC), Ajustes de solo escritura con estado y botón *Borrar clave*, y migración que cifra la clave en claro.
- `incoespacio_invoice_ocr_async` 17.0.1.1.1: lee la clave con `incoespacio.secret`.
- `docker-compose.yml` pasa `ODOO_SECRETS_KEY` al servicio `web`; `.env.example` lo documenta.
- Probado: base con la versión antigua y una clave en claro → actualización con llave maestra → en la base queda `enc:v1:…`. 32 tests en verde (ai_core 14, OCR 15, OCR asíncrono 3). La clave no aparece en el log.

# Guía: llave maestra en Vaultwarden y despliegue

## 1. Generar la llave maestra (una sola vez)

En el servidor, por SSH, dentro de la carpeta del ERP:

```bash
docker exec incoespacio_web python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Sale una línea de 44 caracteres terminada en `=`. Esa es la llave. No la pegues en chats, correos ni tickets.

## 2. Guardarla en Vaultwarden

1. En Vaultwarden, dentro de la **organización** de la empresa (no en la bóveda personal), en una colección tipo «ERP Incoespacio · Infraestructura» a la que solo tengan acceso las 2 personas responsables.
2. *Nuevo elemento → Nota segura* (o *Inicio de sesión*, si preferís).
   - **Nombre:** `ERP Incoespacio · ODOO_SECRETS_KEY (llave maestra de claves API)`
   - **Campo personalizado** de tipo **Oculto**, nombre `ODOO_SECRETS_KEY`, valor: la llave.
   - **Notas:**
     - Dónde se usa: `.env` del servidor EC2 `i-086ba2031ed634b90` (`35.43.198.227`), carpeta del ERP.
     - Para qué: Odoo cifra con ella las claves de API (Gemini) que se pegan en Ajustes.
     - Si se pierde: generar otra (paso 1), cambiarla en `.env`, `docker compose up -d web` y volver a pegar las claves en Ajustes. No se pierde ningún dato.
     - Fecha de creación.
   - Activar **«Volver a pedir la contraseña maestra»** (Master password re-prompt) en el elemento.
3. En la misma colección, un elemento por cada clave de Google:
   - `Gemini · producción (OCR)`: restringida a la IP `35.43.198.227`, solo Generative Language API, fecha de creación.
   - `Gemini · desarrollo local`: con tope de gasto bajo.

## 3. Ponerla en el servidor

```bash
cd <carpeta del ERP>
nano .env
```

Añadir la línea (sin comillas ni espacios):

```
ODOO_SECRETS_KEY=la_llave_de_44_caracteres=
```

Proteger el archivo:

```bash
chmod 600 .env
```

Así solo lo lee el usuario que lanza `docker compose` (no cambies el propietario: si no puede leerlo, `docker compose` no arranca).

## 4. Desplegar

Cuando la rama `hardening-secretos` esté en `main`:

```bash
git pull
docker compose up -d web
docker exec incoespacio_web odoo -u incoespacio_ai_core,incoespacio_invoice_ocr_async -d incoespacio --stop-after-init --workers=0 --max-cron-threads=0 --http-port=8098
docker compose restart web
```

- `up -d web` recrea el contenedor para que lea la variable nueva del `.env`.
- Comprobar que la tiene sin imprimirla: `docker exec incoespacio_web sh -c 'test -n "$ODOO_SECRETS_KEY" && echo OK'`.
- Si ya había una clave en claro, la actualización la cifra sola.

## 5. Comprobar en Odoo

1. *Ajustes → Facturación → Digitalización OCR de Facturas con IA*. Debe poner «Configurada · termina en …XXXX».
   - Si pone «Falta la llave maestra en el servidor»: el contenedor no tiene la variable. Revisar `.env` y repetir `docker compose up -d web`.
2. Modo desarrollador → *Ajustes → Técnico → Parámetros del sistema* → `incoespacio_invoice_ocr.gemini_api_key`: el valor empieza por `enc:v1:` y es ilegible.
3. Subir una factura de prueba y ver que el OCR la lee.

## 6. Rotar la clave de Google (sprint 2)

1. Crear la clave nueva en Google Cloud con sus restricciones (sprint 2) y guardarla en Vaultwarden.
2. Pegarla en *Ajustes* y guardar. El estado cambia a la nueva terminación.
3. Probar el OCR con una factura.
4. Borrar la clave antigua en Google Cloud.

# Estado (2026-11-26, tarde)

- En producción: la clave de Gemini va cifrada (PR #5), con el estado en Ajustes y el modelo `gemini-3.5-flash-lite` (rama `feat-gemini-modelo-y-estado`).
- Clave nueva en el proyecto `incoespacio-erp`, restringida a Gemini API y a la IP `35.43.198.227`, vinculada a la cuenta de servicio `erp-incoespacio-gemini` (sin roles). El OCR funciona y va más rápido que con 3.8 Flash.
- Pendiente:
  1. Borrar la clave antigua en el proyecto Incoluz (`gen-lang-client-0400527258`), comprobando antes que no la use el ERP de Incoluz.
  2. Presupuesto de 5 €/mes con alertas al 50, 90 y 100 % en `incoespacio-erp`.
  3. `ERP-INCOESPACIO-gemini-prod` en Vaultwarden, con proyecto, restricciones y fecha.
  4. ERP de Incoluz: usa `gemini-2.5-flash`, que se apaga el 2026-12-01 (Google lo redirige a `gemini-3.5-flash-lite`).
