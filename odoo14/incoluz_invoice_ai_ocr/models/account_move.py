# -*- coding: utf-8 -*-
import base64
import json
import logging
import re
import threading
import unicodedata
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
    ocr_has_pdf = fields.Boolean(compute='_compute_ocr_pdf_file', string="Tiene PDF")
    ocr_pdf_file = fields.Binary(compute='_compute_ocr_pdf_file', string="Archivo PDF Factura")
    ocr_show_split_view = fields.Boolean(
        string="Modo Pantalla Dividida",
        default=False,
        help="Muestra el PDF original de la factura al lado del formulario."
    )
    ocr_auto_classified_reason = fields.Char(
        string="Motivo de Clasificación IA",
        copy=False
    )

    # ------------------------------------------------------------------ UI / entrada
    def _ocr_attachments(self):
        self.ensure_one()
        atts = self.env['ir.attachment'].search([
            ('res_model', '=', 'account.move'),
            ('res_id', '=', self.id),
        ])
        if not atts and self.message_main_attachment_id:
            atts = self.message_main_attachment_id
        if not atts:
            msg_atts = self.message_ids.mapped('attachment_ids')
            if msg_atts:
                atts = msg_atts
        return atts

    def _compute_ocr_pdf_file(self):
        for move in self:
            atts = move._ocr_attachments().filtered(
                lambda a: a.mimetype == 'application/pdf' or (a.name and a.name.lower().endswith('.pdf'))
            )
            if atts:
                move.ocr_has_pdf = True
                move.ocr_pdf_file = atts[0].datas
            else:
                move.ocr_has_pdf = False
                move.ocr_pdf_file = False

    def action_toggle_split_view(self):
        self.ensure_one()
        self.ocr_show_split_view = not self.ocr_show_split_view
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_scan_with_ai(self, run_sync=False):
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

        if run_sync or self._context.get('sync_ocr'):
            return self._process_ai_ocr_content(file_bytes, attachment.name)
        else:
            self._trigger_background_ocr_worker([self.id])
            return True

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
    _GENERIC_COMPANY_NAMES = frozenset({
        'my company', 'your company', 'mi empresa', 'tu empresa',
        'company', 'compania', 'mycompany',
    })
    _NAME_STOPWORDS = frozenset({
        'de', 'del', 'la', 'el', 'los', 'las', 'the', 'of', 'y', 'and',
        'sl', 'sa', 'slu', 'sau',
    })

    @staticmethod
    def _clean_vat(vat_str):
        if not vat_str:
            return ''
        vat = re.sub(r'[^A-Za-z0-9]', '', str(vat_str)).upper()
        if vat.startswith('ES') and len(vat) > 2:
            vat = vat[2:]
        return vat

    def _vat_matches(self, a, b):
        a, b = self._clean_vat(a), self._clean_vat(b)
        return bool(a and b and (a == b or a.endswith(b) or b.endswith(a)))

    @classmethod
    def _norm_company_name(cls, name):
        s = unicodedata.normalize('NFKD', name or '').encode('ascii', 'ignore').decode('ascii').lower()
        s = re.sub(r'\b(s\.?\s*l\.?\s*u?|s\.?\s*a\.?\s*u?|sociedad limitada|sociedad anonima)\b', ' ', s)
        s = re.sub(r'[^a-z0-9]+', ' ', s)
        return ' '.join(s.split())

    def _names_alike(self, pdf_name, erp_name):
        """True si el nombre del PDF y el del ERP son el mismo negocio (no 'My Company')."""
        a, b = self._norm_company_name(pdf_name), self._norm_company_name(erp_name)
        if not a or not b or a in self._GENERIC_COMPANY_NAMES or b in self._GENERIC_COMPANY_NAMES:
            return False
        if a in b or b in a:
            return len(min(a, b, key=len)) >= 6
        # ponytail: overlap de tokens, no distancia fuzzy; subir si el OCR deja un solo token
        wa = {w for w in a.split() if w not in self._NAME_STOPWORDS and len(w) > 2}
        wb = {w for w in b.split() if w not in self._NAME_STOPWORDS and len(w) > 2}
        return len(wa) >= 2 and len(wb) >= 2 and len(wa & wb) >= 2

    def _company_match(self, comp, vat, name):
        vat_ok = self._vat_matches(comp.vat, vat)
        name_ok = self._names_alike(name, comp.name) or self._names_alike(name, comp.partner_id.name)
        return vat_ok, name_ok

    def _matches_company(self, comp, vat, name):
        vat_ok, name_ok = self._company_match(comp, vat, name)
        if vat_ok:
            return True
        if self._clean_vat(vat) and self._clean_vat(comp.vat):
            return False
        return name_ok

    def _match_other_company(self, vat, name):
        # sudo justificado: la ir.rule multi-compañía limita res.company a company_ids
        # del usuario, y el cortafuegos fiscal debe poder ver todo el grupo
        for comp in self.env['res.company'].sudo().search([]).filtered(lambda c: c.id != self.company_id.id):
            if self._matches_company(comp, vat, name):
                return comp
        return False

    def _detect_document_move_type(self, emisor_data, receptor_data, factura_data):
        """
        Determina de forma automática el move_type adecuado:
        - out_invoice / out_refund (Cliente / Venta)
        - in_invoice / in_refund (Proveedor / Compra)
        Retorna (target_move_type, reason, is_other_company, other_company).
        """
        self.ensure_one()
        my_company = self.company_id or self.env.company
        emisor_vat = self._clean_vat(emisor_data.get('cif'))
        emisor_name = (emisor_data.get('nombre') or '').strip()
        receptor_vat = self._clean_vat(receptor_data.get('cif'))
        receptor_name = (receptor_data.get('nombre') or '').strip()

        tipo_doc = (factura_data.get('tipo_documento') or '').strip().lower()
        total_val = float(factura_data.get('total') or 0.0)
        is_refund = (tipo_doc == 'factura_rectificativa' or total_val < 0)
        is_ticket = tipo_doc == 'ticket_simplificado'

        def _pdf_party(vat, name):
            if name and vat:
                return "%s, CIF %s" % (name, vat)
            return vat or name or ''

        def _reason(role, pdf_vat, pdf_name, tipo_txt):
            vat_ok, name_ok = self._company_match(my_company, pdf_vat, pdf_name)
            party = _pdf_party(pdf_vat, pdf_name)
            if vat_ok and name_ok:
                return _("El %s del PDF (%s) coincide por CIF y nombre con tu empresa. Clasificada como %s.") % (
                    role, party, tipo_txt
                )
            if vat_ok:
                return _("El %s del PDF (%s) coincide por CIF. El nombre no coincide con el del ERP (%s). Clasificada como %s.") % (
                    role, party, my_company.name, tipo_txt
                )
            return _("El %s del PDF (%s) coincide por nombre con tu empresa. Clasificada como %s.") % (
                role, party, tipo_txt
            )

        # 1. Comprobar si el emisor coincide con nuestra empresa -> Factura de Cliente (Venta)
        if (emisor_vat or emisor_name) and self._matches_company(my_company, emisor_vat, emisor_name):
            target = 'out_refund' if is_refund else 'out_invoice'
            tipo_txt = _("Abono de Cliente (Venta)") if is_refund else _("Factura de Cliente (Venta)")
            return target, _reason(_("emisor"), emisor_vat, emisor_name, tipo_txt), False, None

        # 2. Comprobar si el receptor coincide con nuestra empresa -> Factura de Proveedor (Gasto)
        if (receptor_vat or receptor_name) and self._matches_company(my_company, receptor_vat, receptor_name):
            target = 'in_refund' if is_refund else 'in_invoice'
            tipo_txt = _("Abono de Proveedor (Compra)") if is_refund else _("Factura de Proveedor (Compra)")
            return target, _reason(_("receptor"), receptor_vat, receptor_name, tipo_txt), False, None

        # 3. Comprobar si corresponde a otra empresa del grupo (multi-compañía)
        other_comp_emisor = self._match_other_company(emisor_vat, emisor_name)
        if other_comp_emisor:
            target = 'out_refund' if is_refund else 'out_invoice'
            reason = _("Emitida por otra empresa del grupo (CIF: %s).") % (
                other_comp_emisor.vat or emisor_vat
            )
            return target, reason, True, other_comp_emisor

        other_comp_receptor = self._match_other_company(receptor_vat, receptor_name)
        if other_comp_receptor:
            target = 'in_refund' if is_refund else 'in_invoice'
            reason = _("Dirigida a otra empresa del grupo (CIF: %s).") % (
                other_comp_receptor.vat or receptor_vat
            )
            return target, reason, True, other_comp_receptor

        # 4. Ticket / factura simplificada (sin receptor, o marcado por la IA) -> Compra / Proveedor
        if is_ticket or (not receptor_vat and not receptor_name):
            target = 'in_refund' if is_refund else 'in_invoice'
            tipo_txt = _("Abono de Proveedor") if is_refund else _("Gasto / Ticket de Proveedor")
            reason = _("Documento o ticket simplificado sin receptor fiscal. Clasificado como %s.") % tipo_txt
            return target, reason, False, None

        # 5. Por defecto: si el emisor no es nuestra empresa, se asume gasto de proveedor
        target = 'in_refund' if is_refund else 'in_invoice'
        tipo_txt = _("Abono de Proveedor") if is_refund else _("Factura de Proveedor")
        reason = _("Emisor externo detectado. Clasificado como %s.") % tipo_txt
        return target, reason, False, None

    def _reclassify_move_type(self, target_move_type, reason=None):
        """Reclasifica el tipo de factura en borrador y su diario correspondiente."""
        self.ensure_one()
        if self.state != 'draft':
            return False
        if self.move_type == target_move_type:
            return False

        journal_type = 'purchase' if target_move_type in self.get_purchase_types(include_receipts=True) else 'sale'
        journal = self.env['account.journal'].search([
            ('company_id', '=', self.company_id.id),
            ('type', '=', journal_type),
        ], limit=1)

        vals = {
            'move_type': target_move_type,
            'ocr_auto_classified_reason': reason or '',
        }
        if journal:
            vals['journal_id'] = journal.id

        self.write(vals)
        _logger.info("Factura ID %s reclasificada a %s (Diario: %s). Motivo: %s",
                     self.id, target_move_type, journal.name if journal else 'N/A', reason)
        return True

    # ------------------------------------------------------------------ aplicación de datos
    def _apply_ai_extracted_data(self, data, force=False):
        self.ensure_one()
        factura_data = data.get('factura', {})
        emisor_data = data.get('emisor', {})
        receptor_data = data.get('receptor', {})
        lineas_data = data.get('lineas', [])
        pago_data = data.get('pago', {})

        # 1. Auto-detección del tipo fiscal de documento
        target_type, reason, is_other_comp, other_comp = self._detect_document_move_type(
            emisor_data, receptor_data, factura_data
        )

        # 2. Cortafuegos multi-empresa
        if is_other_comp and not force:
            self.write({
                'ocr_status': 'mismatch',
                'ocr_company_mismatch': True,
                'ocr_mismatch_details': _("Documento de otra compañía del grupo (CIF: %s). Tu compañía activa tiene CIF %s.") % (
                    other_comp.vat or '', self.company_id.vat or ''
                ),
                'ocr_error_message': False,
            })
            title = _('Factura de otra empresa (CIF %s)') % (other_comp.vat or '')
            msg = _("El documento corresponde al CIF %s, pero esta factura está en la compañía con CIF %s. "
                    "Cambia de empresa en el selector de Odoo para gestionarla.") % (
                other_comp.vat or '', self.company_id.vat or ''
            )
            body = Markup(
                "<div class='alert alert-warning'><b>%s:</b> %s<br/>"
                "<b>Cómo resolverlo:</b> Cambia de empresa en el selector superior de Odoo antes de registrar "
                "esta factura. Si deseas procesarla en esta empresa de todos modos, pulsa el botón "
                "<b>\"Forzar procesado de todos modos\"</b>.</div>" % (title, msg))
            self.message_post(body=body, subtype_xmlid='mail.mt_note')
            return False

        # 3. Reclasificación automática del tipo de asiento (si difiere del actual)
        if self.move_type != target_type and self.state == 'draft':
            self._reclassify_move_type(target_type, reason)
        elif not self.ocr_auto_classified_reason and reason:
            self.ocr_auto_classified_reason = reason

        self.write({'ocr_company_mismatch': False, 'ocr_mismatch_details': False})
        is_customer = self.move_type in self.get_sale_types(include_receipts=True)

        counterpart = receptor_data if is_customer else emisor_data
        partner, was_created = self._find_or_create_partner(counterpart, is_supplier=not is_customer)
        if partner and self.state == 'draft':
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
                taxes = self._find_matching_taxes(
                    'sale' if is_customer else 'purchase', pct_iva,
                    0.0 if is_customer else pct_irpf)
                vals = {
                    'name': desc,
                    'quantity': qty,
                    'price_unit': price,
                    'tax_ids': [(6, 0, taxes.ids)],
                }
                product = self._find_ocr_product(desc, line.get('codigo'), is_customer)
                if product:
                    vals['product_id'] = product.id
                if account:
                    vals['account_id'] = account.id
                new_lines.append((0, 0, vals))
            self.invoice_line_ids = new_lines

        self._process_iban_verification(partner, pago_data.get('iban', '') if pago_data else '')
        self._check_invoice_duplicate(partner, num_factura)

        self.write({'ocr_status': 'done', 'ocr_error_message': False})
        self._post_ai_chatter_summary(data, was_created, partner)
        return True

    def _find_ocr_product(self, desc, code, is_customer):
        """Enlaza un producto existente. No crea: en Incoluz los altas son almacenable + categoría fija."""
        Product = self.env['product.product']
        code = (code or '').strip()
        desc = (desc or '').strip()
        flag = 'sale_ok' if is_customer else 'purchase_ok'
        if code:
            prod = Product.search(['|', ('default_code', '=ilike', code), ('barcode', '=', code)], limit=1)
            if prod:
                return prod
            if not is_customer and self.partner_id:
                info = self.env['product.supplierinfo'].search([
                    ('name', '=', self.partner_id.commercial_partner_id.id),
                    ('product_code', '=ilike', code),
                ], limit=1)
                if info:
                    return info.product_id or info.product_tmpl_id.product_variant_id
        if len(desc) < 6:
            return Product.browse()
        prod = Product.search([(flag, '=', True), ('name', '=ilike', desc)], limit=1)
        if prod:
            return prod
        token = next((w for w in re.findall(r'[A-Za-zÁÉÍÓÚÜáéíóúü0-9]{4,}', desc) if w.lower() not in self._NAME_STOPWORDS), '')
        if not token:
            return Product.browse()
        cands = Product.search([(flag, '=', True), ('name', 'ilike', token)], limit=40)
        return cands.filtered(lambda p: self._names_alike(desc, p.name))[:1]

    def _get_ocr_default_account(self, is_customer):
        acc = self.journal_id.default_account_id
        if acc:
            return acc
        user_type = 'income' if is_customer else 'expense'
        return self.env['account.account'].search([
            ('user_type_id.internal_group', '=', user_type),
            ('company_id', '=', (self.company_id or self.env.company).id),
        ], limit=1)

    def _find_or_create_partner(self, data, is_supplier):
        cif = (data.get('cif') or '').strip().upper()
        nombre = (data.get('nombre') or '').strip()
        partner_obj = self.env['res.partner']
        own = self.company_id.partner_id
        cif_clean = self._clean_vat(cif)
        if cif_clean:
            partners = partner_obj.search([('vat', '!=', False), ('id', '!=', own.id)])
            partner = partners.filtered(lambda p: self._clean_vat(p.vat) == cif_clean)[:1]
            if partner:
                return partner, False
        if nombre:
            candidates = partner_obj.search([
                ('id', '!=', own.id),
                '|', '|',
                ('is_company', '=', True),
                ('customer_rank', '>', 0),
                ('supplier_rank', '>', 0),
            ])
            partner = candidates.filtered(lambda p: self._names_alike(nombre, p.name))[:1]
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

    def _find_matching_taxes(self, tax_use, pct_iva, pct_irpf=0.0):
        Tax = self.env['account.tax']
        cid = (self.company_id or self.env.company).id
        taxes = Tax.search([('type_tax_use', '=', tax_use), ('amount', '=', pct_iva), ('company_id', '=', cid)], limit=1)
        if tax_use == 'purchase' and pct_irpf:
            taxes |= Tax.search([('type_tax_use', '=', 'purchase'), ('amount', '=', -abs(pct_irpf)), ('company_id', '=', cid)], limit=1)
        return taxes

    def _check_invoice_duplicate(self, partner, ref):
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

    def _process_iban_verification(self, partner, raw_iban):
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

        classify_badge = ""
        if self.ocr_auto_classified_reason:
            classify_badge = (
                "<div class='alert alert-info p-2 mb-2'>"
                "<b>🤖 IncoBot:</b> %s"
                "</div>"
            ) % self.ocr_auto_classified_reason
        dup_badge = "<div class='alert alert-danger p-2 mb-2'><b>Posible factura duplicada</b></div>" if self.is_duplicate_detected else ""
        iban_badge = "<div class='alert alert-danger p-2 mb-2'><b>Discrepancia de IBAN con el proveedor</b></div>" if self.ocr_iban_status == 'mismatch' else ""
        new_partner_badge = "<div class='alert alert-info p-2 mb-2'><b>Nuevo contacto creado:</b> %s</div>" % partner.name if was_created and partner else ""
        partner_label = "Cliente:" if is_customer else "Proveedor:"
        partner_name = (rec.get('nombre') if is_customer else emi.get('nombre')) or (partner and partner.name) or ''
        partner_vat = (rec.get('cif') if is_customer else emi.get('cif')) or (partner and partner.vat) or ''

        html = """
        <div style="font-size: 13px; max-width: 500px;">
            <p class="mb-1 text-primary fw-bold">🤖 IncoBot: Factura digitalizada con IA</p>
            %s%s%s%s
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
        """ % (classify_badge, dup_badge, iban_badge, new_partner_badge, partner_label, partner_name, partner_vat,
               fac.get('numero') or self.ref or 'N/A', fac.get('fecha_emision') or 'N/A',
               eur(fac.get('base_imponible_total')), eur(fac.get('iva_total')), eur(fac.get('total')))
        self.message_post(body=Markup(html), subtype_xmlid='mail.mt_note')

    # ------------------------------------------------------------------ cola en segundo plano
    @api.model
    def _ocr_resolve_upload_type(self, ctx):
        """Convierte 'auto' a un move_type válido de account.move (placeholder hasta el OCR)."""
        ctx = dict(ctx or {})
        move_type = ctx.get('default_move_type') or 'in_invoice'
        auto = ctx.get('default_ocr_auto_classify') or move_type == 'auto'
        if auto or move_type == 'auto':
            move_type = 'in_invoice'
            ctx['default_ocr_auto_classify'] = True
            journal_id = False
        else:
            journal_id = ctx.get('default_journal_id')
        expected_type = 'purchase' if move_type in self.get_purchase_types(include_receipts=True) else 'sale'
        if journal_id:
            journal = self.env['account.journal'].browse(journal_id)
            if not journal.exists() or journal.type != expected_type:
                journal_id = False
        if not journal_id:
            journal = self.env['account.journal'].search([
                ('company_id', '=', self.env.company.id),
                ('type', '=', expected_type),
            ], limit=1)
            journal_id = journal.id if journal else False
        ctx.pop('default_journal_id', None)
        ctx['default_move_type'] = move_type
        if journal_id:
            ctx['default_journal_id'] = journal_id
        return move_type, journal_id, ctx

    @api.model
    def _create_move_with_attachment(self, attachment, move_type, journal_id, ctx=None):
        if move_type == 'auto':
            move_type = 'in_invoice'
        ctx = dict(ctx or {})
        ctx.pop('default_journal_id', None)
        ctx['default_move_type'] = move_type
        vals = {
            'move_type': move_type,
            'ocr_status': 'pending',
        }
        if journal_id:
            vals['journal_id'] = journal_id
            ctx['default_journal_id'] = journal_id
        move = self.with_context(ctx).create(vals)
        attachment.write({'res_model': 'account.move', 'res_id': move.id})
        if not move.message_main_attachment_id:
            move.message_main_attachment_id = attachment.id
        move.with_context(
            account_predictive_bills_disable_prediction=True,
            no_new_invoice=True,
        ).message_post(attachment_ids=attachment.ids)
        return move

    @api.model
    def upload_bills_batch(self, files):
        if not files:
            return []
        ctx = dict(self._context)
        move_type, journal_id, ctx = self._ocr_resolve_upload_type(ctx)
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
            limit_recent = fields.Datetime.now() - timedelta(minutes=30)
            domain = [
                '|',
                ('ocr_status', 'in', ('pending', 'processing')),
                '&',
                ('ocr_status', 'in', ('done', 'error', 'mismatch')),
                '|',
                ('write_date', '>=', limit_recent),
                ('create_date', '>=', limit_recent),
            ]
        moves = self.search(domain, order='id desc', limit=50)
        type_labels = {
            'in_invoice': _('Compra'),
            'in_refund': _('Abono compra'),
            'in_receipt': _('Recibo compra'),
            'out_invoice': _('Venta'),
            'out_refund': _('Abono venta'),
            'out_receipt': _('Recibo venta'),
        }
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
                'iban_status': m.ocr_iban_status or 'none',
                'move_type': m.move_type,
                'move_type_label': type_labels.get(m.move_type, m.move_type),
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
            with odoo.api.Environment.manage():
                with registry.cursor() as worker_cr:
                    worker_env = api.Environment(worker_cr, user_id, {})
                    try:
                        move = worker_env['account.move'].browse(mid)
                        if not move.exists() or move.ocr_status == 'done':
                            return
                        move.ocr_status = 'processing'
                        worker_cr.commit()
                        move.with_context(sync_ocr=True).action_scan_with_ai(run_sync=True)
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

    # ------------------------------------------------------------------ Decoders nativos Odoo 14
    @api.model
    def _get_create_invoice_from_attachment_decoders(self):
        res = super()._get_create_invoice_from_attachment_decoders()
        res.append((50, self._create_invoice_from_ai_ocr_attachment))
        return res

    @api.model
    def _create_invoice_from_ai_ocr_attachment(self, attachment):
        """Decoder para Odoo 14 que intercepta facturas subidas con el botón 'Subir' en la vista lista/kanban."""
        if not (attachment.mimetype in ('application/pdf', 'image/jpeg', 'image/png', 'image/webp')
                or (attachment.name and attachment.name.lower().endswith(('.pdf', '.jpg', '.jpeg', '.png', '.webp')))):
            return self.env['account.move']

        ctx = dict(self._context)
        move_type, journal_id, ctx = self._ocr_resolve_upload_type(ctx)
        if move_type == 'auto':
            move_type = 'in_invoice'
        vals = {
            'move_type': move_type,
            'ocr_status': 'pending',
        }
        if journal_id:
            vals['journal_id'] = journal_id
        move = self.with_context(ctx).create(vals)
        self._trigger_background_ocr_worker([move.id])
        return move

    @api.model
    def _get_update_invoice_from_attachment_decoders(self, invoice):
        res = super()._get_update_invoice_from_attachment_decoders(invoice)
        res.append((50, self._update_invoice_from_ai_ocr_attachment))
        return res

    @api.model
    def _update_invoice_from_ai_ocr_attachment(self, attachment, invoice):
        """Decoder para Odoo 14 que procesa archivos adjuntados en facturas borrador sin líneas."""
        if not (attachment.mimetype in ('application/pdf', 'image/jpeg', 'image/png', 'image/webp')
                or (attachment.name and attachment.name.lower().endswith(('.pdf', '.jpg', '.jpeg', '.png', '.webp')))):
            return False
        if invoice.state != 'draft' or invoice.invoice_line_ids.filtered(lambda l: not l.display_type and l.account_id):
            return False
        if invoice.ocr_status == 'done':
            return False
        attachment.write({'res_model': 'account.move', 'res_id': invoice.id})
        if not invoice.message_main_attachment_id:
            invoice.message_main_attachment_id = attachment.id
        invoice.write({'ocr_status': 'pending'})
        invoice._trigger_background_ocr_worker([invoice.id])
        return invoice
