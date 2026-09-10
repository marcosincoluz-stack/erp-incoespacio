# Incoluz: OCR de Facturas con IA (Gemini) — Odoo 14

Port a Odoo 14 de la suite `incoespacio_invoice_ocr` de Odoo 17 (foto fija en el momento
del port; las mejoras posteriores de 17 NO se auto-portan).

## Qué hace
- Botón **Escanear con IA** en facturas borrador + asistente **Digitalizar facturas con IA**
  (menú Facturación) para subida multi-archivo.
- Extracción fiscal completa con Google Gemini (emisor, receptor, líneas, IVA/IRPF, IBAN, totales).
- Cortafuegos fiscal: detecta facturas de otra empresa del grupo o de tipo invertido y bloquea
  el procesado hasta confirmación manual ("Forzar procesado de todos modos").
- Alerta antifraude IBAN (mod-97 SEPA embebido, sin dependencias pip nuevas).
- Detección de duplicadas por proveedor + número.
- Cola en segundo plano (hilo post-commit) + cron de respaldo cada 2 min: inmune a cierres de sesión.
- Cajón flotante estilo Google Drive (OWL 1) con polling de 4 s: progreso en vivo sin longpolling.
- Multi-factura en un solo PDF: particiona páginas y crea un borrador por factura.

## Instalación
1. Copiar la carpeta `incoluz_invoice_ai_ocr` a un directorio del `addons_path` del servidor.
2. Reiniciar Odoo y actualizar la lista de apps.
3. Instalar el módulo (depende solo de `account` y `mail`; **no requiere pip install de nada**).
4. Ajustes → Facturación → *Digitalización OCR de Facturas con IA*: pegar la clave de Google
   Gemini y elegir modelo.
5. Probar: Facturación → *Digitalizar facturas con IA* → subir un PDF → seguir el cajón inferior.

## Requisitos
- Odoo 14.0 (community o enterprise), Python 3.7+ (el de la imagen oficial vale).
- PyPDF2: ya incluido en la imagen oficial odoo:14 (solo se usa para multi-factura).
- Salida HTTPS a `generativelanguage.googleapis.com` desde el servidor.

## Notas de operación
- El procesado crea **borradores**; nunca publica facturas automáticamente.
- Sin clave configurada, cualquier escaneo devuelve un error amable indicando dónde configurarla.
- El cajón inferior consulta cada 4 s solo mientras hay trabajo visible: coste despreciable.
- Multi-compañía: el cortafuegos usa `sudo()` sobre `res.company` a propósito (debe ver todo el
  grupo aunque el usuario no tenga permiso de esas compañías).
