# -*- coding: utf-8 -*-
import base64
import io
import json
import logging
import PyPDF2
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from odoo.exceptions import UserError
from odoo.tools.mimetypes import guess_mimetype

_logger = logging.getLogger(__name__)

GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

INVOICE_PROMPT_SYSTEM = """
Eres un asistente contable experto en fiscalidad española y procesamiento de facturas para ERP Odoo.
Analiza minuciosamente el documento adjunto (factura de compra/proveedor) y extrae todos los datos fiscales.

REGLAS DE FISCALIDAD Y EXTRACCIÓN (ESPAÑA):
1. EMISOR (PROVEEDOR):
   - Es la empresa o profesional que emite la factura (el vendedor). NUNCA confundir con el receptor/cliente.
   - Extrae con precisión: CIF / NIF / NIE, Razón Social o Nombre fiscal, Dirección (calle y número), Código Postal, Ciudad, País, Teléfono y Email si aparecen.
2. RECEPTOR (CLIENTE / COMPAÑÍA):
   - Es quien recibe la factura. Extrae CIF y Nombre fiscal.
3. NÚMERO Y FECHAS:
   - Número de factura: código o serie completo del emisor (ej: '2024/0145', 'B-1289').
   - Fecha de emisión: Formato obligatorio 'YYYY-MM-DD'.
   - Fecha de vencimiento: Formato 'YYYY-MM-DD' si está indicada; si no, null.
4. LÍNEAS DE FACTURA:
   - Extrae cada concepto desglosado con: descripción, cantidad (float), precio_unitario (float), porcentaje_iva (float, ej: 21.0, 10.0, 4.0, 0.0) e importe de línea (subtotal sin impuestos).
   - Si no hay líneas claras pero hay una base imponible general, crea una única línea con la descripción general o concepto.
5. IMPUESTOS (IVA E IRPF):
   - Desglosa las bases imponibles y cuotas por cada tipo de IVA.
   - Retención de IRPF: Si aplica retención (ej. profesionales -15%, -7% o alquileres -19%), extrae el porcentaje como número positivo (ej: 15.0) y la cuota retenida.
6. TOTALES:
   - Base imponible total, IVA total, cuota retención IRPF y Total factura a pagar.
7. DATOS BANCARIOS Y PAGO (IBAN SEPA):
   - Si en el documento figura una cuenta bancaria o IBAN para transferencias (ej: ES91 2100 ...), extráelo limpio en "pago.iban" (sin espacios ni guiones, todo en mayúsculas).
   - Extrae también la entidad o banco si aparece en "pago.banco".
8. DOCUMENTOS MULTIPÁGINA Y DETECCIÓN MULTI-FACTURA:
   - Si el archivo contiene 2 o más facturas distintas escaneadas o unidas en un solo archivo:
     * Marca "es_multifactura": true
     * Incluye en la lista "documentos_particionados" cada factura separada con sus propios campos (emisor, factura, lineas, pago) y el array "paginas": [p1, p2, ...] indicando las páginas (base 1) que pertenecen a esa factura concreta.
   - Si el documento contiene solo UNA factura (aunque tenga varias páginas de desglose):
     * Marca "es_multifactura": false y deja "documentos_particionados": []
9. VALIDACIÓN:
   - Si el documento no es una factura válida o es completamente ilegible, marca "es_factura_valida": false y explica el "motivo".

Debes responder ÚNICAMENTE un objeto JSON válido con la siguiente estructura exacta:
{
  "es_factura_valida": true,
  "es_multifactura": false,
  "motivo": "",
  "emisor": {
    "cif": "B12345678",
    "nombre": "Razón Social del Proveedor",
    "direccion": "Calle Ejemplo 12",
    "codigo_postal": "28001",
    "ciudad": "Madrid",
    "pais": "España",
    "telefono": "",
    "email": ""
  },
  "receptor": {
    "cif": "B99999999",
    "nombre": "Nombre del Cliente o Empresa Receptora"
  },
  "factura": {
    "numero": "FAC-2024-001",
    "fecha_emision": "2024-05-15",
    "fecha_vencimiento": "2024-06-15",
    "moneda": "EUR",
    "base_imponible_total": 100.0,
    "iva_total": 21.0,
    "retencion_irpf_porcentaje": 0.0,
    "retencion_irpf_cuota": 0.0,
    "total": 121.0
  },
  "lineas": [
    {
      "descripcion": "Descripción del producto o servicio",
      "cantidad": 1.0,
      "precio_unitario": 100.0,
      "porcentaje_iva": 21.0,
      "subtotal": 100.0
    }
  ],
  "pago": {
    "iban": "ES9121000418450200051332",
    "banco": "CaixaBank"
  },
  "documentos_particionados": []
}
"""


class AiOcrService:
    """Servicio para interactuar con la API de Google Gemini para extracción de facturas."""
    _session = None

    @classmethod
    def get_session(cls):
        if cls._session is None:
            session = requests.Session()
            session.mount("https://", HTTPAdapter(max_retries=Retry(
                total=3,
                backoff_factor=2,
                status_forcelist=(429, 500, 502, 503, 504),
                allowed_methods=["POST"],
                raise_on_status=False,
            )))
            cls._session = session
        return cls._session

    @staticmethod
    def is_pdf_encrypted(file_bytes):
        """Comprueba si un archivo PDF está protegido con contraseña mediante PyPDF2."""
        if not file_bytes or not file_bytes.startswith(b"%PDF-"):
            return False
        try:
            reader = PyPDF2.PdfFileReader(io.BytesIO(file_bytes), strict=False)
            return bool(getattr(reader, 'isEncrypted', False))
        except Exception as e:
            _logger.warning("No se pudo inspeccionar el cifrado del PDF: %s", e)
            return False

    @staticmethod
    def split_pdf_pages(file_bytes, page_numbers):
        """Extrae un subconjunto de páginas (1-indexadas) de un PDF binario.
        
        :param file_bytes: Bytes del PDF original
        :param page_numbers: lista de enteros [1, 2, ...]
        :return: bytes del nuevo PDF particionado
        """
        if not file_bytes or not file_bytes.startswith(b"%PDF-") or not page_numbers:
            return file_bytes
        try:
            reader = PyPDF2.PdfFileReader(io.BytesIO(file_bytes), strict=False)
            total_pages = reader.getNumPages()
            writer = PyPDF2.PdfFileWriter()
            added = 0
            for p in page_numbers:
                p_idx = int(p) - 1
                if 0 <= p_idx < total_pages:
                    writer.addPage(reader.getPage(p_idx))
                    added += 1

            if added == 0:
                return file_bytes

            out_stream = io.BytesIO()
            writer.write(out_stream)
            return out_stream.getvalue()
        except Exception as e:
            _logger.exception("Error extrayendo páginas %s del PDF: %s", page_numbers, e)
            return file_bytes

    @classmethod
    def analyze_invoice_document(cls, env, file_bytes, filename=""):
        """Envía el documento a la API de Gemini Flash y retorna los datos extraídos en JSON.
        
        :param env: Odoo Environment
        :param file_bytes: Bytes del archivo PDF o imagen
        :param filename: Nombre original del archivo
        :return: dict con los datos fiscales de la factura
        """
        icp = env['ir.config_parameter'].sudo()
        api_key = icp.get_param('incoespacio_invoice_ocr.gemini_api_key', default='').strip()
        if not api_key:
            raise UserError(
                "No se ha configurado la clave API de Gemini.\n\n"
                "Por favor, ve a Ajustes > Facturación > sección 'OCR con IA' "
                "e introduce tu clave de Google Gemini para activar la lectura automática."
            )

        # Validación temprana de documento protegido con contraseña
        if cls.is_pdf_encrypted(file_bytes):
            raise UserError("El archivo PDF está protegido con contraseña. Debe desprotegerse antes de ser procesado por la IA.")

        model = icp.get_param('incoespacio_invoice_ocr.gemini_model', default='gemini-2.5-flash').strip() or 'gemini-2.5-flash'
        mimetype = guess_mimetype(file_bytes, default="application/pdf")
        b64_data = base64.b64encode(file_bytes).decode('utf-8')

        url = GEMINI_API_BASE_URL.format(model=model, api_key=api_key)
        headers = {
            "Content-Type": "application/json"
        }

        # Optimizaciones de velocidad:
        # 1. Desactivar thinkingBudget en Gemini 2.5 para eliminar la latencia de 'reflexión' innecesaria
        gen_config = {
            "temperature": 0.1,
            "response_mime_type": "application/json",
        }
        if "gemini-2.5" in model:
            gen_config["thinkingConfig"] = {"thinkingBudget": 0}

        # 2. Utilizar systemInstruction nativo de Google para aprovechar la caché de atención
        payload = {
            "systemInstruction": {
                "parts": [{"text": INVOICE_PROMPT_SYSTEM}]
            },
            "contents": [
                {
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": mimetype,
                                "data": b64_data
                            }
                        },
                        {
                            "text": "Analiza minuciosamente el documento adjunto y extrae todos los datos fiscales en JSON."
                        }
                    ]
                }
            ],
            "generationConfig": gen_config
        }

        try:
            _logger.info("Enviando documento %s (%s) a Gemini Flash (%s)...", filename, mimetype, model)
            response = cls.get_session().post(url, json=payload, headers=headers, timeout=45)
        except requests.exceptions.RequestException as e:
            _logger.exception("Error de conexión con Gemini API tras reintentos: %s", e)
            raise UserError(f"Error de conexión con la IA de Google tras reintentos: {str(e)}")

        if response is None or response.status_code != 200:
            status = response.status_code if response is not None else "Sin respuesta"
            body_text = response.text if response is not None else ""
            _logger.error("Error devuelto por Gemini API (%s): %s", status, body_text)
            err_msg = f"Error al procesar la factura con Gemini (Código {status})"
            try:
                err_json = response.json()
                if "error" in err_json and "message" in err_json["error"]:
                    err_msg += f": {err_json['error']['message']}"
            except Exception:
                err_msg += f": {body_text[:200]}"
            raise UserError(err_msg)

        try:
            res_data = response.json()
            candidates = res_data.get("candidates", [])
            if not candidates:
                raise ValueError("La respuesta de Gemini no contiene candidatos.")

            text_content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            # Limpiar posibles bloques de markdown si vinieran
            clean_text = text_content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

            parsed_data = json.loads(clean_text.strip())
            _logger.info("Datos extraídos exitosamente por Gemini para %s: %s", filename, parsed_data.get('factura', {}).get('numero'))
            return parsed_data
        except Exception as e:
            _logger.exception("Error parseando el JSON devuelto por Gemini: %s", e)
            raise UserError(f"No se pudo interpretar el resultado de la IA: {str(e)}")
