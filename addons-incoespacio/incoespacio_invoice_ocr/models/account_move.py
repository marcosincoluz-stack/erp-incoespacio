# -*- coding: utf-8 -*-
import base64
import json
import logging
import re
from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    ai_ocr_processed = fields.Boolean(
        string="Procesado por IA",
        default=False,
        copy=False,
        help="Indica si esta factura ha sido digitalizada automáticamente con Gemini Flash."
    )
    ocr_status = fields.Selection([
        ('pending', 'En cola'),
        ('processing', 'Digitalizando...'),
        ('done', 'Digitalizada con éxito'),
        ('mismatch', 'Discrepancia de empresa'),
        ('error', 'Error en extracción'),
    ], string="Estado OCR IA", default=False, copy=False, tracking=True)

    ocr_company_mismatch = fields.Boolean(
        string="Discrepancia de Empresa",
        default=False,
        copy=False,
        help="Indica si el emisor o receptor del documento no coincide con la compañía de la factura."
    )
    ocr_mismatch_type = fields.Selection([
        ('other_company', 'Pertenece a otra empresa del grupo'),
        ('unknown_company', 'Emisor/Receptor desconocido'),
        ('inverted_type', 'Tipo invertido (compra en ventas o venta en compras)'),
    ], string="Tipo de Discrepancia", copy=False, readonly=True)
    ocr_mismatch_details = fields.Text(string="Detalle de Discrepancia", copy=False, readonly=True)
    ocr_raw_extracted_json = fields.Text(string="JSON Extraído por IA", copy=False, readonly=True)

    ocr_error_message = fields.Text(string="Detalle Error OCR", copy=False, readonly=True)

    is_duplicate_detected = fields.Boolean(
        string="Posible Duplicada",
        default=False,
        copy=False,
        help="Marcado si la IA o el sistema detecta otra factura con mismo CIF, número o importe."
    )
    duplicate_move_id = fields.Many2one(
        'account.move',
        string="Factura Duplicada Detectada",
        copy=False,
        readonly=True
    )

    ocr_extracted_iban = fields.Char(string="IBAN Extraído por IA", copy=False, readonly=True)
    ocr_iban_status = fields.Selection([
        ('verified', 'Coincide con proveedor'),
        ('new', 'Nueva cuenta dada de alta'),
        ('mismatch', '¡Alerta! No coincide con cuentas conocidas'),
        ('none', 'No detectado en factura'),
    ], string="Estado IBAN", default='none', copy=False, readonly=True)

    def _get_edi_decoder(self, file_data, filename=None):
        def _gemini_decoder(move):
            success = move._decode_with_gemini_ai(file_data, filename)
            return bool(success)
        return _gemini_decoder

    def _decode_with_gemini_ai(self, file_data, filename=None):
        self.ensure_one()
        try:
            content_bytes = file_data
            if isinstance(content_bytes, str):
                content_bytes = base64.b64decode(content_bytes)
            self._process_ai_ocr_content(content_bytes, filename or self.name or "factura.pdf")
            return True
        except Exception as e:
            _logger.exception("Error en _decode_with_gemini_ai para factura %s: %s", self.id, e)
            self.write({
                'ocr_status': 'error',
                'ocr_error_message': str(e)
            })
            return False

    def action_scan_with_ai(self):
        self.ensure_one()
        attachments = self.attachment_ids.filtered(
            lambda a: a.mimetype in ('application/pdf', 'image/jpeg', 'image/png', 'image/webp')
                      or (a.name and a.name.lower().endswith(('.pdf', '.jpg', '.jpeg', '.png', '.webp')))
        )
        if not attachments:
            msg = self.message_ids.filtered(lambda m: m.attachment_ids)
            if msg:
                attachments = msg.mapped('attachment_ids').filtered(
                    lambda a: a.mimetype in ('application/pdf', 'image/jpeg', 'image/png', 'image/webp')
                              or (a.name and a.name.lower().endswith(('.pdf', '.jpg', '.jpeg', '.png', '.webp')))
                )

            raise UserError(
                _("No se encontró ningún archivo PDF o imagen adjunto en esta factura.\n"
                  "Por favor, adjunta el documento antes de pulsar 'Escanear con IA'.")
            )

        attachment = attachments[0]
        file_bytes = base64.b64decode(attachment.datas) if attachment.datas else b""
        if not file_bytes:
            raise UserError(_("El archivo adjunto está vacío."))

        self.write({'ocr_status': 'processing', 'ocr_error_message': False})
        return self._process_ai_ocr_content(file_bytes, attachment.name)

    def _process_ai_ocr_content(self, file_bytes, filename, force=False):
        self.ensure_one()
        # Llamar al servicio centralizado de IA en incoespacio_ai_core
        from odoo.addons.incoespacio_ai_core.models.ai_ocr_service import AiOcrService

        try:
            data = AiOcrService.analyze_invoice_document(self.env, file_bytes, filename)
            self.ocr_raw_extracted_json = json.dumps(data, ensure_ascii=False)
        except Exception as e:
            self.write({
                'ocr_status': 'error',
                'ocr_error_message': str(e)
            })
            raise

        if not data.get('es_factura_valida', True):
            motivo = data.get('motivo') or 'El documento no parece ser una factura válida o es ilegible.'
            self.write({
                'ocr_status': 'error',
                'ocr_error_message': motivo,
            })
            self.message_post(
                body=Markup(f"<div class='alert alert-warning'><b>OCR IA:</b> {motivo}</div>"),
                subtype_xmlid='mail.mt_note'
            )
            return False

        if data.get('es_multifactura') and data.get('documentos_particionados'):
            return self._process_multi_invoice_partition(data, file_bytes, filename)

        return self._apply_ai_extracted_data(data, force=force)

    def action_force_process_ocr(self):
        """Permite al usuario forzar el procesado saltándose la alerta de discrepancia de empresa."""
        self.ensure_one()
        if self.ocr_raw_extracted_json:
            try:
                data = json.loads(self.ocr_raw_extracted_json)
                self._apply_ai_extracted_data(data, force=True)
                self.message_post(
                    body=Markup("<div class='alert alert-info'><b>OCR IA:</b> Se ha forzado el procesado contable manualmente a petición del usuario.</div>"),
                    subtype_xmlid='mail.mt_note'
                )
                return True
            except Exception as e:
                _logger.exception("Error al forzar procesado con JSON almacenado: %s", e)
        return self.action_scan_with_ai()

    def _process_multi_invoice_partition(self, full_data, file_bytes, filename):
        from odoo.addons.incoespacio_ai_core.models.ai_ocr_service import AiOcrService
        sub_docs = full_data.get('documentos_particionados', [])
        if not sub_docs:
            return self._apply_ai_extracted_data(full_data)

        self._apply_ai_extracted_data(sub_docs[0])
        first_pages = sub_docs[0].get('paginas', [])
        if first_pages and file_bytes.startswith(b"%PDF-"):
            part_bytes = AiOcrService.split_pdf_pages(file_bytes, first_pages)
            if self.attachment_ids:
                self.attachment_ids[0].write({'datas': base64.b64encode(part_bytes).decode('utf-8')})

        created_invoices = self
        for idx, sub_doc in enumerate(sub_docs[1:], start=2):
            pages = sub_doc.get('paginas', [])
            part_bytes = AiOcrService.split_pdf_pages(file_bytes, pages) if pages else file_bytes
            sub_name = f"{filename or 'factura'}_parte_{idx}.pdf"
            b64_part = base64.b64encode(part_bytes).decode('utf-8')

            new_move = self.create({
                'move_type': self.move_type,
                'journal_id': self.journal_id.id,
                'ocr_status': 'pending',
            })
            attach = self.env['ir.attachment'].create({
                'name': sub_name,
                'datas': b64_part,
                'mimetype': 'application/pdf',
                'res_model': 'account.move',
                'res_id': new_move.id,
            })
            new_move.message_post(attachment_ids=[attach.id])
            new_move._apply_ai_extracted_data(sub_doc)
            created_invoices |= new_move

        return True

    @staticmethod
    def _clean_vat(vat_str):
        if not vat_str:
            return ''
        vat = re.sub(r'[^A-Za-z0-9]', '', str(vat_str)).upper()
        if vat.startswith('ES') and len(vat) > 2:
            vat = vat[2:]
        return vat

    def _check_fiscal_identity(self, emisor_data, receptor_data):
        """Valida que la factura pertenezca a la empresa activa y al tipo contable correcto.
        
        Retorna (is_mismatch, mismatch_type, details_dict)
        """
        self.ensure_one()
        is_customer = self.move_type in ('out_invoice', 'out_refund', 'out_receipt')

        my_company = self.company_id
        my_vat = self._clean_vat(my_company.vat)
        my_name = (my_company.name or '').strip().lower()

        emisor_vat = self._clean_vat(emisor_data.get('cif'))
        emisor_name = (emisor_data.get('nombre') or '').strip()

        receptor_vat = self._clean_vat(receptor_data.get('cif'))
        receptor_name = (receptor_data.get('nombre') or '').strip()

        all_companies = self.env['res.company'].sudo().search([])

        def _matches_company(comp, vat, name):
            c_vat = self._clean_vat(comp.vat)
            if vat and c_vat and (c_vat == vat or c_vat.endswith(vat) or vat.endswith(c_vat)):
                return True
            c_name = (comp.name or '').strip().lower()
            if name and len(name) >= 4 and c_name:
                if c_name in name.lower() or name.lower() in c_name:
                    return True
            return False

        # 1. Facturas de Clientes (out_invoice): El emisor DEBE ser nuestra empresa
        if is_customer:
            if emisor_vat or emisor_name:
                if _matches_company(my_company, emisor_vat, emisor_name):
                    return False, False, {}

                # Caso Inversión: Si el receptor somos nosotros y el emisor no, es una factura de proveedor
                if _matches_company(my_company, receptor_vat, receptor_name):
                    return True, 'inverted_type', {
                        'title': 'Factura de Proveedor detectada en Clientes',
                        'detected_company': my_company,
                        'msg': f"Este documento es una factura de gasto recibida de '{emisor_name or emisor_vat}', "
                               f"donde tu empresa '{my_company.name}' figura como cliente receptor. "
                               f"Debes registrarla en 'Facturas de Proveedor'."
                    }

                # ¿Coincide el emisor con otra empresa registrada en Odoo (ej. Incoluz)?
                for other_comp in all_companies.filtered(lambda c: c.id != my_company.id):
                    if _matches_company(other_comp, emisor_vat, emisor_name):
                        return True, 'other_company', {
                            'title': f'Factura de otra empresa ({other_comp.name})',
                            'detected_company': other_comp,
                            'msg': f"El documento fue emitido por '{other_comp.name}' (CIF: {emisor_vat or other_comp.vat}), "
                                   f"pero tu compañía activa en la factura es '{my_company.name}'. "
                                   f"Cambia al entorno de {other_comp.name} para gestionarla."
                        }

                # Si no coincide con ninguna empresa conocida:
                return True, 'unknown_company', {
                    'title': 'Emisor no coincide con la empresa',
                    'detected_company': False,
                    'msg': f"El emisor de la factura '{emisor_name}' ({emisor_vat}) no coincide con tu empresa '{my_company.name}' ({my_vat})."
                }

        # 2. Facturas de Proveedores (in_invoice): El receptor DEBE ser nuestra empresa (si viene especificado)
        else:
            # Caso Inversión: Si el emisor somos nosotros, es una factura de cliente
            if emisor_vat or emisor_name:
                if _matches_company(my_company, emisor_vat, emisor_name):
                    return True, 'inverted_type', {
                        'title': 'Factura de Cliente detectada en Proveedores',
                        'detected_company': my_company,
                        'msg': f"Este documento fue emitido por tu propia empresa '{my_company.name}'. "
                               f"Es una factura de cliente y debe subirse en 'Facturas de Clientes'."
                    }

            # Si viene receptor en la factura, comprobar que pertenezca a nuestra empresa
            if receptor_vat or receptor_name:
                if _matches_company(my_company, receptor_vat, receptor_name):
                    return False, False, {}

                # ¿Coincide el receptor con otra empresa de Odoo (ej. Incoluz)?
                for other_comp in all_companies.filtered(lambda c: c.id != my_company.id):
                    if _matches_company(other_comp, receptor_vat, receptor_name):
                        return True, 'other_company', {
                            'title': f'Factura dirigida a otra empresa ({other_comp.name})',
                            'detected_company': other_comp,
                            'msg': f"Esta factura de gasto está dirigida a '{other_comp.name}' (CIF: {receptor_vat or other_comp.vat}), "
                                   f"pero tu compañía activa es '{my_company.name}'. "
                                   f"Cambia al entorno de {other_comp.name} para registrar este gasto."
                        }

        return False, False, {}

    def _apply_ai_extracted_data(self, data, force=False):
        self.ensure_one()
        factura_data = data.get('factura', {})
        emisor_data = data.get('emisor', {})
        receptor_data = data.get('receptor', {})
        lineas_data = data.get('lineas', [])
        pago_data = data.get('pago', {})

        is_customer = self.move_type in ('out_invoice', 'out_refund', 'out_receipt')

        # Cortafuegos Fiscal: Comprobar identidad de emisor/receptor antes de crear registros
        if not force:
            is_mismatch, mismatch_type, details = self._check_fiscal_identity(emisor_data, receptor_data)
            if is_mismatch:
                self.write({
                    'ocr_status': 'mismatch',
                    'ocr_company_mismatch': True,
                    'ocr_mismatch_type': mismatch_type,
                    'ocr_mismatch_details': details.get('msg', ''),
                    'ai_ocr_processed': False,
                    'ocr_error_message': False,
                })
                title = details.get('title', 'Discrepancia de Empresa')
                msg = details.get('msg', '')
                body = Markup(f"""
<div style="background-color: #fffbeb; border: 1px solid #fef3c7; border-left: 5px solid #f59e0b; padding: 12px 16px; border-radius: 4px; margin-bottom: 8px;">
    <div style="display: flex; align-items: center; margin-bottom: 6px;">
        <span style="font-size: 15px; font-weight: bold; color: #b45309;">{title}</span>
    </div>
    <div style="color: #92400e; font-size: 13px; line-height: 1.5; margin-bottom: 8px;">
        {msg}
    </div>
    <div style="background-color: #fef3c7; padding: 6px 10px; border-radius: 4px; font-size: 12px; color: #78350f;">
        <b>Cómo resolverlo:</b> Cambia de empresa en el selector superior de Odoo antes de registrar esta factura. Si deseas procesarla en esta empresa de todos modos, pulsa el botón <b>"Forzar procesado de todos modos"</b>.
    </div>
</div>
""")
                self.message_post(body=body, subtype_xmlid='mail.mt_note')
                return False

        # Si no hay discrepancia o se ha forzado manualmente, limpiar estados de discrepancia
        self.write({
            'ocr_company_mismatch': False,
            'ocr_mismatch_type': False,
            'ocr_mismatch_details': False,
        })

        if not is_customer:
            partner, was_created = self._find_or_create_supplier(emisor_data)
        else:
            partner, was_created = self._find_or_create_customer(receptor_data if receptor_data.get('cif') else emisor_data)

        if not self.partner_id and partner:
            self.partner_id = partner.id

        num_factura = (factura_data.get('numero') or '').strip()
        if num_factura:
            if not is_customer:
                self.ref = num_factura
            elif self.name in (False, '/', 'Draft', _('Draft')):
                self.name = num_factura

        fecha_emision = factura_data.get('fecha_emision')
        if fecha_emision and isinstance(fecha_emision, str) and re.match(r'^\d{4}-\d{2}-\d{2}$', fecha_emision.strip()):
            self.invoice_date = fecha_emision.strip()

        fecha_venc = factura_data.get('fecha_vencimiento')
        if fecha_venc and isinstance(fecha_venc, str) and re.match(r'^\d{4}-\d{2}-\d{2}$', fecha_venc.strip()):
            self.invoice_date_due = fecha_venc.strip()

        currency_code = (factura_data.get('moneda') or 'EUR').strip().upper()
        if currency_code:
            curr = self.env['res.currency'].search([('name', '=ilike', currency_code)], limit=1)
            if curr:
                self.currency_id = curr.id

        if lineas_data:
            self.invoice_line_ids = [(5, 0, 0)]
            account_id = self._get_default_income_account() if is_customer else self._get_default_expense_account()
            new_lines = []

            for line in lineas_data:
                desc = (line.get('descripcion') or 'Servicio / Mercancía').strip()
                qty = float(line.get('cantidad') or 1.0)
                price = float(line.get('precio_unitario') or 0.0)
                pct_iva = float(line.get('porcentaje_iva') or 0.0)
                pct_irpf = float(factura_data.get('retencion_irpf_porcentaje') or 0.0)

                if is_customer:
                    taxes = self._find_matching_sale_taxes(pct_iva)
                else:
                    taxes = self._find_matching_purchase_taxes(pct_iva, pct_irpf)

                line_vals = {
                    'name': desc,
                    'quantity': qty,
                    'price_unit': price,
                    'tax_ids': [(6, 0, taxes.ids)],
                }
                if account_id:
                    line_vals['account_id'] = account_id.id
                new_lines.append((0, 0, line_vals))

            self.invoice_line_ids = new_lines

        # Verificación IBAN
        raw_iban = pago_data.get('iban', '') if pago_data else ''
        bank_name = pago_data.get('banco', '') if pago_data else ''
        self._process_iban_verification(partner, raw_iban, bank_name)

        # Detección de duplicados
        total_factura = float(factura_data.get('total') or 0.0)
        self._check_invoice_duplicate(partner, num_factura, total_factura)

        self.write({'ocr_status': 'done', 'ai_ocr_processed': True, 'ocr_error_message': False})
        self._post_ai_chatter_summary(data, was_created, partner)
        return True

    def _find_or_create_supplier(self, emisor_data):
        cif = (emisor_data.get('cif') or '').strip().upper()
        nombre = (emisor_data.get('nombre') or '').strip()
        partner_obj = self.env['res.partner']

        if cif:
            cif_clean = re.sub(r'[^A-Za-z0-9]', '', cif)
            domain = ['|', ('vat', '=ilike', cif), ('vat', '=ilike', cif_clean)]
            partner = partner_obj.search(domain, limit=1)
            if partner:
                return partner, False

        if nombre:
            partner = partner_obj.search([('name', '=ilike', nombre)], limit=1)
            if partner:
                return partner, False

        vals = {
            'name': nombre or cif or _("Proveedor Nuevo (OCR IA)"),
            'vat': cif or False,
            'is_company': True,
            'customer_rank': 0,
            'supplier_rank': 1,
            'street': (emisor_data.get('direccion') or '').strip() or False,
            'zip': (emisor_data.get('codigo_postal') or '').strip() or False,
            'city': (emisor_data.get('ciudad') or '').strip() or False,
            'phone': (emisor_data.get('telefono') or '').strip() or False,
            'email': (emisor_data.get('email') or '').strip() or False,
        }
        country_name = (emisor_data.get('pais') or '').strip()
        if country_name:
            country = self.env['res.country'].search([('name', '=ilike', country_name)], limit=1)
            if country:
                vals['country_id'] = country.id

        new_partner = partner_obj.create(vals)
        return new_partner, True

    def _find_or_create_customer(self, receptor_data):
        cif = (receptor_data.get('cif') or '').strip().upper()
        nombre = (receptor_data.get('nombre') or '').strip()
        partner_obj = self.env['res.partner']

        if cif:
            partner = partner_obj.search([('vat', '=ilike', cif)], limit=1)
            if partner:
                return partner, False
        if nombre:
            partner = partner_obj.search([('name', '=ilike', nombre)], limit=1)
            if partner:
                return partner, False

        vals = {
            'name': nombre or cif or _("Cliente Nuevo (OCR IA)"),
            'vat': cif or False,
            'is_company': True,
            'customer_rank': 1,
            'supplier_rank': 0,
        }
        return partner_obj.create(vals), True

    def _get_default_expense_account(self):
        Account = self.env['account.account']
        comp = self.company_id or self.env.company
        acc = Account.search([('code', '=like', '600%'), ('company_id', '=', comp.id)], limit=1)
        if not acc:
            acc = Account.search([('account_type', '=', 'expense'), ('company_id', '=', comp.id)], limit=1)
        return acc

    def _get_default_income_account(self):
        Account = self.env['account.account']
        comp = self.company_id or self.env.company
        acc = Account.search([('code', '=like', '700%'), ('company_id', '=', comp.id)], limit=1)
        if not acc:
            acc = Account.search([('account_type', '=', 'income'), ('company_id', '=', comp.id)], limit=1)
        return acc

    def _find_matching_purchase_taxes(self, pct_iva, pct_irpf=0.0):
        Tax = self.env['account.tax']
        comp = self.company_id or self.env.company
        iva_tax = Tax.search([
            ('type_tax_use', '=', 'purchase'),
            ('amount', '=', pct_iva),
            ('company_id', '=', comp.id),
        ], limit=1)

        result_taxes = iva_tax or Tax
        if pct_irpf and pct_irpf > 0:
            irpf_tax = Tax.search([
                ('type_tax_use', '=', 'purchase'),
                ('amount', '=', -abs(pct_irpf)),
                ('company_id', '=', comp.id),
            ], limit=1)
            if irpf_tax:
                result_taxes |= irpf_tax
        return result_taxes

    def _find_matching_sale_taxes(self, pct_iva):
        Tax = self.env['account.tax']
        comp = self.company_id or self.env.company
        return Tax.search([
            ('type_tax_use', '=', 'sale'),
            ('amount', '=', pct_iva),
            ('company_id', '=', comp.id),
        ], limit=1)

    def _check_invoice_duplicate(self, partner, ref, total_amount):
        self.ensure_one()
        if not partner or not ref:
            self.is_duplicate_detected = False
            self.duplicate_move_id = False
            return

        domain = [
            ('id', '!=', self.id),
            ('partner_id', '=', partner.id),
            ('ref', '=ilike', ref.strip()),
            ('move_type', '=', self.move_type),
            ('state', '!=', 'cancel'),
        ]
        match = self.search(domain, limit=1)
        if match:
            self.is_duplicate_detected = True
            self.duplicate_move_id = match.id
        else:
            self.is_duplicate_detected = False
            self.duplicate_move_id = False

    # Ponytail: 4-line standard ISO 7064 Modulo 97 SEPA check
    @staticmethod
    def _validate_iban_checksum(iban):
        if not iban or len(iban) < 15:
            return False
        clean = re.sub(r'[^A-Z0-9]', '', iban.upper())
        rearranged = clean[4:] + clean[:4]
        num_str = ''.join(str(ord(c) - 55) if c.isalpha() else c for c in rearranged)
        return num_str.isdigit() and int(num_str) % 97 == 1

    def _process_iban_verification(self, partner, raw_iban, bank_name=None):
        self.ensure_one()
        if not partner or not raw_iban:
            self.ocr_extracted_iban = False
            self.ocr_iban_status = 'none'
            return

        clean_iban = re.sub(r'[^A-Z0-9]', '', str(raw_iban).upper())
        self.ocr_extracted_iban = clean_iban

        partner_ibans = [re.sub(r'[^A-Z0-9]', '', (b.acc_number or '').upper()) for b in partner.bank_ids]
        if clean_iban in partner_ibans:
            self.ocr_iban_status = 'verified'
            return

        if partner_ibans:
            self.ocr_iban_status = 'mismatch'
            _logger.warning("Alerta IBAN factura %s: %s no coincide con cuentas de %s: %s", self.id, clean_iban, partner.name, partner_ibans)
            return

        if self._validate_iban_checksum(clean_iban) or (clean_iban.startswith('ES') and len(clean_iban) == 24):
            try:
                self.env['res.partner.bank'].create({
                    'acc_number': clean_iban,
                    'partner_id': partner.id,
                    'company_id': self.company_id.id if self.company_id else False,
                })
                self.ocr_iban_status = 'new'
            except Exception:
                self.ocr_iban_status = 'none'
        else:
            self.ocr_iban_status = 'none'

    # Ponytail: Compact chatter summary (~35 lines) replacing 150 lines of boilerplate HTML
    def _post_ai_chatter_summary(self, data, was_created, partner):
        fac = data.get('factura', {})
        emi = data.get('emisor', {})
        rec = data.get('receptor', {})
        is_customer = self.move_type in ('out_invoice', 'out_refund', 'out_receipt')

        total_eur = f"{float(fac.get('total') or 0.0):,.2f} €".replace(',', 'X').replace('.', ',').replace('X', '.')
        base_eur = f"{float(fac.get('base_imponible_total') or 0.0):,.2f} €".replace(',', 'X').replace('.', ',').replace('X', '.')
        iva_eur = f"{float(fac.get('iva_total') or 0.0):,.2f} €".replace(',', 'X').replace('.', ',').replace('X', '.')

        dup_badge = "<div class='alert alert-danger p-2 mb-2'><b>Posible factura duplicada</b></div>" if self.is_duplicate_detected else ""
        iban_badge = "<div class='alert alert-danger p-2 mb-2'><b>Discrepancia de IBAN con el proveedor</b></div>" if self.ocr_iban_status == 'mismatch' else ""
        new_partner_badge = f"<div class='alert alert-info p-2 mb-2'><b>Nuevo contacto creado:</b> {partner.name}</div>" if was_created and partner else ""

        partner_label = "Cliente:" if is_customer else "Proveedor:"
        partner_name = (rec.get('nombre') if is_customer else emi.get('nombre')) or (partner and partner.name) or ''
        partner_vat = (rec.get('cif') if is_customer else emi.get('cif')) or (partner and partner.vat) or ''

        html = f"""
        <div style="font-size: 13px; max-width: 500px;">
            <p class="mb-1 text-primary fw-bold">Factura digitalizada con IA</p>
            {dup_badge}
            {iban_badge}
            {new_partner_badge}
            <table class="table table-sm table-bordered mb-1">
                <tr><td><b>{partner_label}</b></td><td>{partner_name} ({partner_vat})</td></tr>
                <tr><td><b>Nº Factura:</b></td><td><code>{fac.get('numero') or self.ref or 'N/A'}</code></td></tr>
                <tr><td><b>Fecha Emisión:</b></td><td>{fac.get('fecha_emision') or 'N/A'}</td></tr>
                <tr><td><b>Base Imponible:</b></td><td>{base_eur}</td></tr>
                <tr><td><b>IVA:</b></td><td>{iva_eur}</td></tr>
                <tr class="table-light"><td><b>Total Factura:</b></td><td><b>{total_eur}</b></td></tr>
            </table>
            <small class="text-muted"><i class="fa fa-check text-success"/> Borrador generado y listo para revisión contable.</small>
        </div>
        """
        self.message_post(body=Markup(html), subtype_xmlid='mail.mt_note')
