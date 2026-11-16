# Facturas desde el correo

Un buzón (`facturas@`) entra por IMAP. Odoo lee la bandeja de entrada entera, esté el correo leído o no, y lo mueve a una carpeta según el resultado. Cada PDF o XML se convierte en un borrador y pasa por la cola de OCR. Si el CIF emisor es el de la empresa, queda como factura de cliente. Si el CIF receptor es el de la empresa, como factura de proveedor. Si no se puede decidir o si el PDF ya estaba, el borrador se queda en **Contabilidad > Facturas por revisar**. Un correo sin PDF ni XML no crea borrador. Nada se contabiliza solo.

## Microsoft

Lo hace un administrador del inquilino. El buzón tiene que ser un usuario con licencia: Odoo inicia sesión como él y lee su bandeja de entrada.

1. Crear `facturas@` y, en el centro de administración de Exchange, activar IMAP en las aplicaciones de correo de ese usuario.
2. En Microsoft Entra, registrar una aplicación `Odoo`:
   - Cuentas de cualquier organización y cuentas personales de Microsoft.
   - Redirección Web: `https://<url-de-odoo>/microsoft_outlook/confirm`. Una por entorno (staging y producción). La URL es la de `web.base.url`.
   - Permiso delegado de Microsoft Graph: `IMAP.AccessAsUser.All`. `User.Read` se añade solo.
   - Asignar el usuario `facturas@` a la aplicación.
   - En Certificados y secretos, crear un secreto de cliente con la caducidad más larga que permita el inquilino. Copiar el **valor** en ese momento y el Id. de aplicación. Anotar la fecha de caducidad y poner un recordatorio un mes antes: cuando el secreto vence, el correo deja de entrar hasta crear otro y pegarlo en Odoo.
3. Si el inquilino bloquea el consentimiento, un administrador global lo concede en la aplicación. Si IMAP está cerrado para toda la organización, habilitarlo solo para `facturas@`.

## Odoo

1. Fijar el parámetro de sistema `web.base.url` en https y crear `web.base.url.freeze` con valor `True`.
2. Instalar **Incoespacio: Facturas desde el correo**. Trae el módulo Microsoft Outlook.
3. Ajustes → Ajustes generales → Discuss: activar servidores de correo personalizados y pegar el Id. de aplicación y el valor del secreto.
4. Activar el modo desarrollador. Ajustes → Técnico → Correo electrónico → Servidores de correo entrante → Nuevo.
   - Tipo: Outlook OAuth Authentication. Odoo rellena `imap.outlook.com`, puerto 993 y SSL.
   - Usuario: `facturas@`. Sin contraseña.
   - Conectar la cuenta de Outlook e iniciar sesión con ese buzón. Tiene que aparecer **Outlook Token Valid**.
   - Crear un nuevo registro: Asiento contable (`account.move`).
   - Conservar adjuntos: activado.
   - Probar y confirmar.
5. Decir a quien envía facturas que escriba a `facturas@`. Una regla de Outlook puede reenviar ahí el correo que llegue a otras direcciones: el enrutado no depende del destinatario.
6. Empezar con el buzón vacío. Aunque no lo esté, solo entra el correo recibido desde el alta del servidor en Odoo.
7. Si un remitente cae en Correo no deseado, permitirle. Solo se lee la bandeja de entrada.

Abrir el buzón en Outlook no impide que Odoo lo procese. Cada correo sale de la bandeja de entrada:

- **Odoo-Procesadas**: traía un PDF o XML y se creó el borrador (o el correo ya se había procesado).
- **Odoo-Ignorados**: no traía PDF ni XML.
- **Odoo-Errores**: el procesado falló. No se reintenta solo; hay que mirarlo.

La cola de OCR digitaliza el PDF en los 2 minutos siguientes. Si la IA falla, se reintenta hasta tres veces, con media hora entre intentos. Un documento que no es una factura no se reintenta: queda en revisión.

## Revisión

Contabilidad → Facturas por revisar. Entran los borradores con un PDF ilegible, con un PDF repetido, con un CIF que no decide el tipo, con un documento que no es factura, con discrepancia de empresa o con error de OCR, y también las marcadas como duplicadas por número.

- **Es de proveedor** / **Es de cliente**: aplica el JSON ya leído, sin otra llamada a la IA. Si todavía no hay JSON, lo vuelve a encolar.
- **Procesar igualmente**: el PDF repetido no lo era; lo manda a la cola.

Publicar sigue bloqueado mientras el contacto lo haya creado el OCR y nadie haya pulsado **Contacto revisado**.

## Vigilancia

Una vez al día Odoo comprueba que el buzón conecta y que **Odoo-Errores** está vacía. Si el secreto de Entra ha caducado o hay correos en esa carpeta, los responsables de contabilidad reciben un aviso en Discuss.

- En el log: `OCR mail: no se pudo leer el buzón` y `OCR mail: fallo al procesar`.
- El contador de Facturas por revisar, a diario.

## Marcha atrás

Desactivar el servidor de entrada. Deja de entrar correo. Los borradores ya creados no se confirman solos y se pueden borrar. Desinstalar el módulo no toca facturas contabilizadas.

## Límites

- Un JPEG o PNG suelto no se procesa: se mueve a Odoo-Ignorados.
- Una rectificativa entra como factura normal.
- Cada factura dentro de un PDF con varias se clasifica por su propio CIF.
- Un borrador sin clasificar también sale en la lista de facturas de proveedor, en borrador.
- Cada pase lee como mucho 50 correos. El resto espera al siguiente.

Posibles mejoras tras probar el buzón con correo real: [`docs/ocr-facturas-ideas.md`](../../../../docs/ocr-facturas-ideas.md).
