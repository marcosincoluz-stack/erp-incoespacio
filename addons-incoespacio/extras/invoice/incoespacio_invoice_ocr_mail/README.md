# Facturas desde el correo

Un buzón (`facturas@`) entra por IMAP. Odoo lee la bandeja de entrada entera, esté el correo leído o no, y lo mueve a una carpeta según el resultado. Cada PDF se convierte en un borrador y pasa por la cola de OCR. Un XML Facturae se lee al momento, sin IA. Si el CIF emisor es el de la empresa, queda como factura de cliente. Si el CIF receptor es el de la empresa, como factura de proveedor. Si no se puede decidir o si el PDF ya estaba, el borrador se queda en **Contabilidad > Facturas por revisar**. Un correo sin PDF ni XML no crea borrador. Nada se contabiliza solo.

## Microsoft

Lo hace un administrador del inquilino. El buzón tiene que ser un usuario con licencia: Odoo inicia sesión como él y lee su bandeja de entrada.

1. Crear `facturas@` y, en el centro de administración de Exchange, activar IMAP y SMTP autenticado en las aplicaciones de correo de ese usuario. Sin SMTP autenticado el envío responde 535 5.7.3.
2. En Microsoft Entra, registrar una aplicación `Odoo`:
   - Cuentas de cualquier organización y cuentas personales de Microsoft. Odoo pide el token en `/common`; una aplicación de un solo inquilino falla.
   - Redirección Web: `https://<url-de-odoo>/microsoft_outlook/confirm`. Una por entorno (staging y producción). La URL es la de `web.base.url`.
   - Permisos delegados de Office 365 Exchange Online, recurso `00000002-0000-0ff1-ce00-000000000000`. Los de Microsoft Graph con el mismo nombre no valen. El selector del portal no los lista: se añaden en el manifiesto, dentro de `requiredResourceAccess`, y un administrador concede el consentimiento. `IMAP.AccessAsUser.All`: `195adc35-e27b-454b-a7ed-1ecdffa1c09f`. `SMTP.Send`: `76faac2a-0f20-42f1-928a-50de5b9dbe52`.
   - `User.Read` de Graph se queda. Renovar el secreto no pide repetir este paso.
   - En Certificados y secretos, crear un secreto de cliente con la caducidad más larga que permita el inquilino. Copiar el **valor** en ese momento y el Id. de aplicación. El identificador del secreto no se usa. Anotar la fecha de caducidad y poner un recordatorio un mes antes: cuando el secreto vence, el correo deja de entrar y de salir hasta crear otro y pegarlo en Odoo.
3. Si el inquilino bloquea el consentimiento, un administrador global lo concede en la aplicación. Si IMAP está cerrado para toda la organización, habilitarlo solo para `facturas@`.

## Odoo

1. Fijar el parámetro de sistema `web.base.url` en https y crear `web.base.url.freeze` con valor `True`.
2. Instalar **Incoespacio: Facturas desde el correo**. Trae el módulo Microsoft Outlook.
3. Ajustes → Ajustes generales → Discuss: activar servidores de correo personalizados. Ahí aparecen **Usar un servidor de Outlook** y los campos ID y Secreto. Pegar el Id. de aplicación y el valor del secreto.
4. Ajustes → Técnico → Correo electrónico → Dominios de alias. Crear el dominio (`incoespacio.com`) y poner **Alias Desde por defecto** en la parte local del buzón (`facturacion`, sin @). Odoo 17 no usa los parámetros `mail.catchall.domain` ni `mail.default.from`. En la tarjeta de facturas de proveedor, vaciar el alias de correo: al crear el dominio, Odoo muestra `facturas-de-proveedores@...` y ese buzón no existe. El tipo de factura lo decide el CIF, no el diario.
5. Activar el modo desarrollador. Ajustes → Técnico → Correo electrónico → Servidores de correo entrante → Nuevo.
   - Tipo: Outlook OAuth Authentication. Odoo rellena `imap.outlook.com`, puerto 993 y SSL.
   - Usuario: `facturas@`. Sin contraseña.
   - Conectar la cuenta de Outlook e iniciar sesión con ese buzón. Tiene que aparecer **Outlook Token Valid**.
   - Crear un nuevo registro: Asiento contable (`account.move`).
   - Conservar adjuntos: activado.
   - Probar y confirmar.
   - Servidor de salida, mismo usuario y autenticación OAuth de Outlook. Filtro Desde: la dirección completa. Conectar con ese buzón. El remitente cuadra con el alias del paso 4.
6. Decir a quien envía facturas que escriba a `facturas@`. Una regla de Outlook puede reenviar ahí el correo que llegue a otras direcciones: el enrutado no depende del destinatario.
7. Empezar con el buzón vacío. Aunque no lo esté, solo entra el correo recibido desde el alta del servidor en Odoo.
8. Si un remitente cae en Correo no deseado, permitirle. Solo se lee la bandeja de entrada.

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
- Un XML Facturae lo lee `incoespacio_invoice_xml` y el correo sigue yendo a Odoo-Procesadas. Otro XML queda en revisión.
- Una rectificativa en PDF entra como factura normal. Un Facturae con clase OR o CR entra como abono.
- Cada factura dentro de un PDF con varias se clasifica por su propio CIF.
- Un borrador sin clasificar también sale en la lista de facturas de proveedor, en borrador.
- El producto de cada línea lo sugiere `incoespacio_invoice_ocr_product` con las facturas ya contabilizadas de ese contacto. El precio y la etiqueta siguen siendo los del PDF.
- Un descuento en la línea se respeta. Un descuento global al pie, como el pronto pago, deja la factura en revisión porque el total no cuadra.
- Cada pase lee como mucho 50 correos. El resto espera al siguiente.

Posibles mejoras tras probar el buzón con correo real: [`docs/ocr-facturas-ideas.md`](../../../../docs/ocr-facturas-ideas.md).
