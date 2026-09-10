# -*- coding: utf-8 -*-
import base64
import json
import logging
import re
import threading
from datetime import timedelta
from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .ai_ocr_service import AiOcrService

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    ocr_status = fields.Selection([
        ('pending', 'En cola'),
        ('processing', 'Digitalizando...'),
        ('done', 'Digitalizada con éxito'),
        ('mismatch', 'Discrepancia de empresa'),
        ('error', 'Error en extracción'),
    ], string="Estado OCR IA", default=False, copy=False, tracking=True)
    ocr_company_mismatch = fields.Boolean(
        string="Discrepancia de Empresa", default=False, copy=False,
        help="Indica si el emisor o receptor del documento no coincide con la compañía de la factura.")
    ocr_mismatch_details = fields.Text(string="Detalle de Discrepancia", copy=False, readonly=True)
    ocr_raw_extracted_json = fields.Text(string="JSON Extraído por IA", copy=False, readonly=True)
    ocr_error_message = fields.Text(string="Detalle Error OCR", copy=False, readonly=True)
    is_duplicate_detected = fields.Boolean(
        string="Posible Duplicada", default=False, copy=False,
        help="Marcado si el sistema detecta otra factura con mismo CIF, número o importe.")
    duplicate_move_id = fields.Many2one('account.move', string="Factura Duplicada Detectada", copy=False, readonly=True)
    ocr_extracted_iban = fields.Char(string="IBAN Extraído por IA", copy=False, readonly=True)
    ocr_iban_status = fields.Selection([
        ('verified', 'Coincide con proveedor'),
        ('new', 'Nueva cuenta dada de alta'),
        ('mismatch', '¡Alerta! No coincide con cuentas conocidas'),
        ('none', 'No detectado en factura'),
    ], string="Estado IBAN", default='none', copy=False, readonly=True)

    # ------------------------------------------------------------------ UI / entrada
    def _ocr_attachments(self):
        # Odoo 14 no tiene account.move.attachment_ids (llega en 15): busqueda directa
        return self.env['ir.attachment'].search([
            ('res_model', '=', 'account.move'),
            ('res_id', 'in', self.ids),
        ])

    def action_scan_with_ai(self):
        self.ensure_one()
        attachments = self._ocr_attachments().filtered(
            lambda a: a.mimetype in ('application/pdf', 'image/jpeg', 'image/png', 'image/webp')
                      or (a.name and a.name.lower().endswith(('.pdf', '.jpg', '.jpeg', '.png', '.webp')))
        )
        if not attachments:
            raise UserError(
                _("No se encontró ningún archivo PDF o imagen adjunto en esta factura.\n"
                  "Por favor, adjunta el documento antes de pulsar 'Escanear con IA'."))
        attachment = attachments[0]
        file_bytes = base64.b64decode(attachment.datas) if attachment.datas else b""
        if not file_bytes:
            raise UserError(_("El archivo adjunto está vacío."))
        self.write({'ocr_status': 'processing', 'ocr_error_message': False})
        return self._process_ai_ocr_content(file_bytes, attachment.name)

    def action_force_process_ocr(self):
        self.ensure_one()
        if self.ocr_raw_extracted_json:
            try:
                data = json.loads(self.ocr_raw_extracted_json)
                self._apply_ai_extracted_data(data, force=True)
                self.message_post(
                    body=Markup("<div class='alert alert-info'><b>OCR IA:</b> Se ha forzado el procesado contable manualmente a petición del usuario.</div>"),
                    subtype_xmlid='mail.mt_note')
                return True
            except Exception as e:
                _logger.exception("Error al forzar procesado con JSON almacenado: %s", e)
        return self.action_scan_with_ai()

    # ------------------------------------------------------------------ pipeline
    def _process_ai_ocr_content(self, file_bytes, filename, force=False):
        self.ensure_one()
        try:
            data = AiOcrService.analyze_invoice_document(self.env, file_bytes, filename)
            self.ocr_raw_extracted_json = json.dumps(data, ensure_ascii=False)
        except Exception as e:
            self.write({'ocr_status': 'error', 'ocr_error_message': str(e)})
            raise

        if not data.get('es_factura_valida', True):
            motivo = data.get('motivo') or 'El documento no parece ser una factura válida o es ilegible.'
            self.write({'ocr_status': 'error', 'ocr_error_message': motivo})
            self.message_post(
                body=Markup("<div class='alert alert-warning'><b>OCR IA:</b> %s</div>" % motivo),
                subtype_xmlid='mail.mt_note')
            return False

        if data.get('es_multifactura') and data.get('documentos_particionados'):
            return self._process_multi_invoice_partition(data, file_bytes, filename)

        return self._apply_ai_extracted_data(data, force=force)

    def _process_multi_invoice_partition(self, full_data, file_bytes, filename):
        sub_docs = full_data.get('documentos_particionados', [])
        if not sub_docs:
            return self._apply_ai_extracted_data(full_data)

        self._apply_ai_extracted_data(sub_docs[0])
        first_pages = sub_docs[0].get('paginas', [])
        if first_pages and file_bytes.startswith(b"%PDF-"):
            part_bytes = AiOcrService.split_pdf_pages(file_bytes, first_pages)
            own = self._ocr_attachments()
            if own:
                own[0].write({'datas': base64.b64encode(part_bytes).decode('utf-8')})

        for idx, sub_doc in enumerate(sub_docs[1:], start=2):
            pages = sub_doc.get('paginas', [])
            part_bytes = AiOcrService.split_pdf_pages(file_bytes, pages) if pages else file_bytes
            sub_name = "%s_parte_%d.pdf" % (filename or 'factura', idx)
            attach = self.env['ir.attachment'].create({
                'name': sub_name,
                'datas': base64.b64encode(part_bytes).decode('utf-8'),
                'mimetype': 'application/pdf',
                'res_model': 'account.move',
                'res_id': self.id,
            })
            new_move = self.create({'move_type': self.move_type, 'journal_id': self.journal_id.id, 'ocr_status': 'pending'})
            attach.write({'res_id': new_move.id})
            new_move.message_post(attachment_ids=[attach.id])
            new_move._apply_ai_extracted_data(sub_doc)
        return True

    # ------------------------------------------------------------------ cortafuegos fiscal
    @staticmethod
    def _clean_vat(vat_str):
        if not vat_str:
            return ''
        vat = re.sub(r'[^A-Za-z0-9]', '', str(vat_str)).upper()
        if vat.startswith('ES') and len(vat) > 2:
            vat = vat[2:]
        return vat

    def _matches_company(self, comp, vat, name):
        c_vat = self._clean_vat(comp.vat)
        if vat and c_vat and (c_vat == vat or c_vat.endswith(vat) or vat.endswith(c_vat)):
            return True
        c_name = (comp.name or '').strip().lower()
        if name and len(name) >= 4 and c_name:
            if c_name in name.lower() or name.lower() in c_name:
                return True
        return False

    def _match_other_company(self, vat, name):
        # sudo justificado: la ir.rule multi-compañía limita res.company a company_ids
        # del usuario, y el cortafuegos fiscal debe poder ver todo el grupo
        for comp in self.env['res.company'].sudo().search([]).filtered(lambda c: c.id != self.company_id.id):
            if self._matches_company(comp, vat, name):
                return comp
        return False

    def _check_fiscal_identity(self, emisor_data, receptor_data):
        """Retorna (is_mismatch, details_dict)."""
        self.ensure_one()
        is_customer = self.move_type in self.get_sale_types(include_receipts=True)
        my_company = self.company_id
        my_vat = self._clean_vat(my_company.vat)
        emisor_vat = self._clean_vat(emisor_data.get('cif'))
        emisor_name = (emisor_data.get('nombre') or '').strip()
        receptor_vat = self._clean_vat(receptor_data.get('cif'))
        receptor_name = (receptor_data.get('nombre') or '').strip()

        if is_customer:
            if emisor_vat or emisor_name:
                if self._matches_company(my_company, emisor_vat, emisor_name):
                    return False, {}
                if self._matches_company(my_company, receptor_vat, receptor_name):
                    return True, {
                        'title': 'Factura de Proveedor detectada en Clientes',
                        'msg': ("Este documento es una factura de gasto recibida de '%s', donde tu empresa '%s' "
                                "figura como cliente receptor. Debes registrarla en 'Facturas de Proveedor'."
                                % (emisor_name or emisor_vat, my_company.name))}
                other_comp = self._match_other_company(emisor_vat, emisor_name)
                if other_comp:
                    return True, {
                        'title': 'Factura de otra empresa (%s)' % other_comp.name,
                        'msg': ("El documento fue emitido por '%s' (CIF: %s), pero tu compañía activa en la factura "
                                "es '%s'. Cambia al entorno de %s para gestionarla."
                                % (other_comp.name, emisor_vat or other_comp.vat, my_company.name, other_comp.name))}
                return True, {
                    'title': 'Emisor no coincide con la empresa',
                    'msg': ("El emisor de la factura '%s' (%s) no coincide con tu empresa '%s' (%s)."
                            % (emisor_name, emisor_vat, my_company.name, my_vat))}
        else:
            if (emisor_vat or emisor_name) and self._matches_company(my_company, emisor_vat, emisor_name):
                return True, {
                    'title': 'Factura de Cliente detectada en Proveedores',
                    'msg': ("Este documento fue emitido por tu propia empresa '%s'. "
                            "Es una factura de cliente y debe subirse en 'Facturas de Clientes'." % my_company.name)}
            if receptor_vat or receptor_name:
                if self._matches_company(my_company, receptor_vat, receptor_name):
                    return False, {}
                other_comp = self._match_other_company(receptor_vat, receptor_name)
                if other_comp:
                    return True, {
                        'title': 'Factura dirigida a otra empresa (%s)' % other_comp.name,
                        'msg': ("Esta factura de gasto está dirigida a '%s' (CIF: %s), pero tu compañía activa es "
                                "'%s'. Cambia al entorno de %s para registrar este gasto."
                                % (other_comp.name, receptor_vat or other_comp.vat, my_company.name, other_comp.name))}
        return False, {}

    # ------------------------------------------------------------------ aplicación de datos
    def _apply_ai_extracted_data(self, data, force=False):
        self.ensure_one()
        factura_data = data.get('factura', {})
        emisor_data = data.get('emisor', {})
        receptor_data = data.get('receptor', {})
        lineas_data = data.get('lineas', [])
        pago_data = data.get('pago', {})
        is_customer = self.move_type in self.get_sale_types(include_receipts=True)

        if not force:
            is_mismatch, details = self._check_fiscal_identity(emisor_data, receptor_data)
            if is_mismatch:
                self.write({
                    'ocr_status': 'mismatch',
                    'ocr_company_mismatch': True,
                    'ocr_mismatch_details': details.get('msg', ''),
                    'ocr_error_message': False,
                })
                title = details.get('title', 'Discrepancia de Empresa')
                msg = details.get('msg', '')
                body = Markup(
                    "<div class='alert alert-warning'><b>%s:</b> %s<br/>"
                    "<b>Cómo resolverlo:</b> Cambia de empresa en el selector superior de Odoo antes de registrar "
                    "esta factura. Si deseas procesarla en esta empresa de todos modos, pulsa el botón "
                    "<b>\"Forzar procesado de todos modos\"</b>.</div>" % (title, msg))
                self.message_post(body=body, subtype_xmlid='mail.mt_note')
                return False

        self.write({'ocr_company_mismatch': False, 'ocr_mismatch_details': False})

        if not is_customer:
            partner, was_created = self._find_or_create_partner(emisor_data, is_supplier=True)
        else:
            partner, was_created = self._find_or_create_partner(
                receptor_data if receptor_data.get('cif') else emisor_data, is_supplier=False)
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
            account = self._get_ocr_default_account(is_customer)
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
                vals = {
                    'name': desc,
                    'quantity': qty,
                    'price_unit': price,
                    'tax_ids': [(6, 0, taxes.ids)],
                }
                if account:
                    vals['account_id'] = account.id
                new_lines.append((0, 0, vals))
            self.invoice_line_ids = new_lines

        raw_iban = pago_data.get('iban', '') if pago_data else ''
        bank_name = pago_data.get('banco', '') if pago_data else ''
        self._process_iban_verification(partner, raw_iban, bank_name)

        total_factura = float(factura_data.get('total') or 0.0)
        self._check_invoice_duplicate(partner, num_factura, total_factura)

        self.write({'ocr_status': 'done', 'ocr_error_message': False})
        self._post_ai_chatter_summary(data, was_created, partner)
        return True

    def _get_ocr_default_account(self, is_customer):
        acc = self.journal_id.default_account_id
        if acc:
            return acc
        user_type = 'income' if is_customer else 'expense'
        return self.env['account.account'].search([
            ('user_type_id.type', '=', user_type),
            ('company_id', '=', (self.company_id or self.env.company).id),
        ], limit=1)

    def _find_or_create_partner(self, data, is_supplier):
        cif = (data.get('cif') or '').strip().upper()
        nombre = (data.get('nombre') or '').strip()
        partner_obj = self.env['res.partner']
        if cif:
            cif_clean = re.sub(r'[^A-Za-z0-9]', '', cif)
            partner = partner_obj.search(['|', ('vat', '=ilike', cif), ('vat', '=ilike', cif_clean)], limit=1)
            if partner:
                return partner, False
        if nombre:
            partner = partner_obj.search([('name', '=ilike', nombre)], limit=1)
            if partner:
                return partner, False
        vals = {
            'name': nombre or cif or (_("Proveedor Nuevo (OCR IA)") if is_supplier else _("Cliente Nuevo (OCR IA)")),
            'vat': cif or False,
            'is_company': True,
            'customer_rank': 0 if is_supplier else 1,
            'supplier_rank': 1 if is_supplier else 0,
        }
        if is_supplier:
            vals.update({
                'street': (data.get('direccion') or '').strip() or False,
                'zip': (data.get('codigo_postal') or '').strip() or False,
                'city': (data.get('ciudad') or '').strip() or False,
                'phone': (data.get('telefono') or '').strip() or False,
                'email': (data.get('email') or '').strip() or False,
            })
            country_name = (data.get('pais') or '').strip()
            if country_name:
                country = self.env['res.country'].search([('name', '=ilike', country_name)], limit=1)
                if country:
                    vals['country_id'] = country.id
        return partner_obj.create(vals), True

    def _find_matching_purchase_taxes(self, pct_iva, pct_irpf=0.0):
        Tax = self.env['account.tax']
        comp = self.company_id or self.env.company
        iva_tax = Tax.search([('type_tax_use', '=', 'purchase'), ('amount', '=', pct_iva), ('company_id', '=', comp.id)], limit=1)
        result_taxes = iva_tax or Tax
        if pct_irpf and pct_irpf > 0:
            irpf_tax = Tax.search([('type_tax_use', '=', 'purchase'), ('amount', '=', -abs(pct_irpf)), ('company_id', '=', comp.id)], limit=1)
            if irpf_tax:
                result_taxes |= irpf_tax
        return result_taxes

    def _find_matching_sale_taxes(self, pct_iva):
        Tax = self.env['account.tax']
        comp = self.company_id or self.env.company
        return Tax.search([('type_tax_use', '=', 'sale'), ('amount', '=', pct_iva), ('company_id', '=', comp.id)], limit=1)

    def _check_invoice_duplicate(self, partner, ref, total_amount):
        self.ensure_one()
        if not partner or not ref:
            self.is_duplicate_detected = False
            self.duplicate_move_id = False
            return
        match = self.search([
            ('id', '!=', self.id),
            ('partner_id', '=', partner.id),
            ('ref', '=ilike', ref.strip()),
            ('move_type', '=', self.move_type),
            ('state', '!=', 'cancel'),
        ], limit=1)
        self.is_duplicate_detected = bool(match)
        self.duplicate_move_id = match.id if match else False

    # ------------------------------------------------------------------ IBAN
    # ponytail: mod-97 SEPA embebido (4 lineas) en vez de schwifty: cero deps pip
    # en el servidor de produccion. Upgrade: pasar a schwifty si algun dia ya
    # esta en el requirements de produccion por otro modulo.
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
        if self._validate_iban_checksum(clean_iban):
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

    # ------------------------------------------------------------------ chatter
    def _post_ai_chatter_summary(self, data, was_created, partner):
        fac = data.get('factura', {})
        emi = data.get('emisor', {})
        rec = data.get('receptor', {})
        is_customer = self.move_type in self.get_sale_types(include_receipts=True)

        def eur(v):
            return "{:,.2f} €".format(float(v or 0.0)).replace(',', 'X').replace('.', ',').replace('X', '.')

        dup_badge = "<div class='alert alert-danger p-2 mb-2'><b>Posible factura duplicada</b></div>" if self.is_duplicate_detected else ""
        iban_badge = "<div class='alert alert-danger p-2 mb-2'><b>Discrepancia de IBAN con el proveedor</b></div>" if self.ocr_iban_status == 'mismatch' else ""
        new_partner_badge = "<div class='alert alert-info p-2 mb-2'><b>Nuevo contacto creado:</b> %s</div>" % partner.name if was_created and partner else ""
        partner_label = "Cliente:" if is_customer else "Proveedor:"
        partner_name = (rec.get('nombre') if is_customer else emi.get('nombre')) or (partner and partner.name) or ''
        partner_vat = (rec.get('cif') if is_customer else emi.get('cif')) or (partner and partner.vat) or ''

        html = """
        <div style="font-size: 13px; max-width: 500px;">
            <p class="mb-1 text-primary fw-bold">Factura digitalizada con IA</p>
            %s%s%s
            <table class="table table-sm table-bordered mb-1">
                <tr><td><b>%s</b></td><td>%s (%s)</td></tr>
                <tr><td><b>Nº Factura:</b></td><td><code>%s</code></td></tr>
                <tr><td><b>Fecha Emisión:</b></td><td>%s</td></tr>
                <tr><td><b>Base Imponible:</b></td><td>%s</td></tr>
                <tr><td><b>IVA:</b></td><td>%s</td></tr>
                <tr class="table-light"><td><b>Total Factura:</b></td><td><b>%s</b></td></tr>
            </table>
            <small class="text-muted"><i class="fa fa-check text-success"/> Borrador generado y listo para revisión contable.</small>
        </div>
        """ % (dup_badge, iban_badge, new_partner_badge, partner_label, partner_name, partner_vat,
               fac.get('numero') or self.ref or 'N/A', fac.get('fecha_emision') or 'N/A',
               eur(fac.get('base_imponible_total')), eur(fac.get('iva_total')), eur(fac.get('total')))
        self.message_post(body=Markup(html), subtype_xmlid='mail.mt_note')

    # ------------------------------------------------------------------ cola en segundo plano
    @api.model
    def _create_move_with_attachment(self, attachment, move_type, journal_id, ctx=None):
        move = self.with_context(ctx or {}).create({
            'move_type': move_type,
            'ocr_status': 'pending',
            'journal_id': journal_id,
        })
        attachment.write({'res_model': 'account.move', 'res_id': move.id})
        move.with_context(
            account_predictive_bills_disable_prediction=True,
            no_new_invoice=True,
        ).message_post(attachment_ids=attachment.ids)
        return move

    @api.model
    def upload_bills_batch(self, files, context_vals=None):
        if not files:
            return []
        ctx = dict(self._context)
        if context_vals:
            ctx.update(context_vals)
        move_type = ctx.get('default_move_type') or 'in_invoice'
        journal_id = ctx.get('default_journal_id')
        if not journal_id:
            journal_type = 'purchase' if move_type in self.get_purchase_types(include_receipts=True) else 'sale'
            journal = self.env['account.journal'].search([
                ('company_id', '=', self.env.company.id),
                ('type', '=', journal_type),
            ], limit=1)
            journal_id = journal.id if journal else False
        created_moves = []
        move_ids_to_process = []
        for f in files:
            filename = f.get('name') or 'factura.pdf'
            attachment = self.env['ir.attachment'].create({
                'name': filename,
                'datas': f.get('data') or '',
                'mimetype': f.get('mimetype') or 'application/pdf',
            })
            move = self._create_move_with_attachment(attachment, move_type, journal_id, ctx)
            created_moves.append({'id': move.id, 'filename': filename, 'status': 'pending'})
            move_ids_to_process.append(move.id)
        if move_ids_to_process:
            self._trigger_background_ocr_worker(move_ids_to_process)
        return created_moves

    @api.model
    def get_active_ocr_batch(self, move_ids=None):
        if move_ids:
            domain = [('id', 'in', move_ids)]
        else:
            limit_time = fields.Datetime.now() - timedelta(minutes=30)
            domain = [
                ('ocr_status', 'in', ('pending', 'processing', 'done', 'error', 'mismatch')),
                ('create_uid', '=', self.env.uid),
                ('create_date', '>=', limit_time),
            ]
        moves = self.search(domain, order='id desc', limit=50)
        result = []
        for m in moves:
            fname = 'Factura'
            mown = m._ocr_attachments()
            if mown:
                fname = mown[0].name or 'Factura'
            result.append({
                'id': m.id,
                'name': m.name or "Borrador #%d" % m.id,
                'filename': fname,
                'status': 'failed' if m.ocr_status == 'error' else m.ocr_status,
                'error': m.ocr_error_message or '',
                'mismatch': m.ocr_company_mismatch,
                'mismatch_details': m.ocr_mismatch_details or '',
                'partner': m.partner_id.name if m.partner_id else '',
                'ref': m.ref or '',
                'amount_total': m.amount_total,
                'is_duplicate': m.is_duplicate_detected,
            })
        return result

    @api.model
    def _trigger_background_ocr_worker(self, move_ids):
        if not move_ids:
            return
        db_name = self.env.cr.dbname
        user_id = self.env.uid

        def _start_worker_thread():
            thread = threading.Thread(
                target=self._run_background_ocr,
                args=(db_name, user_id, list(move_ids)),
                daemon=True,
                name="ocr_worker_%s" % db_name)
            thread.start()
            _logger.info("Worker OCR lanzado en hilo (post-commit) para facturas %s", move_ids)

        if hasattr(self.env.cr, 'postcommit'):
            self.env.cr.postcommit.add(_start_worker_thread)
        else:
            _start_worker_thread()

    @classmethod
    def _run_background_ocr(cls, db_name, user_id, move_ids):
        import concurrent.futures
        import odoo
        registry = odoo.registry(db_name)

        def _process_single_move(mid):
            with registry.cursor() as worker_cr:
                worker_env = api.Environment(worker_cr, user_id, {})
                try:
                    move = worker_env['account.move'].browse(mid)
                    if not move.exists() or move.ocr_status == 'done':
                        return
                    move.ocr_status = 'processing'
                    worker_cr.commit()
                    move.action_scan_with_ai()
                    worker_cr.commit()
                except Exception as e:
                    worker_cr.rollback()
                    _logger.exception("Error en worker OCR para factura ID %s: %s", mid, e)
                    try:
                        move = worker_env['account.move'].browse(mid)
                        if move.exists():
                            move.write({'ocr_status': 'error', 'ocr_error_message': str(e)})
                            worker_cr.commit()
                    except Exception:
                        pass

        if len(move_ids) <= 1:
            for mid in move_ids:
                _process_single_move(mid)
        else:
            max_workers = min(3, len(move_ids))
            _logger.info("Iniciando procesamiento paralelo de %d facturas con %d workers", len(move_ids), max_workers)
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                list(executor.map(_process_single_move, move_ids))

    @api.model
    def _cron_process_pending_ocr(self):
        pending_moves = self.search([
            ('ocr_status', 'in', ('pending', 'processing')),
            ('move_type', 'in', self.get_purchase_types(include_receipts=True) + self.get_sale_types(include_receipts=True)),
        ], limit=10)
        if pending_moves:
            self._trigger_background_ocr_worker(pending_moves.ids)
