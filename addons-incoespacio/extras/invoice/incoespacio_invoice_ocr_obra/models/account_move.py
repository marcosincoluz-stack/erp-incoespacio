import json
import logging
import re

from markupsafe import Markup
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import config

_logger = logging.getLogger(__name__)

_SO_CODE = re.compile(r"\b(P\d{6,})\b", re.I)


class AccountMove(models.Model):
    _inherit = "account.move"

    ocr_obra_state = fields.Selection(
        [
            ("none", "Sin sugerir"),
            ("suggested", "Sugerida"),
            ("confirmed", "Confirmada"),
            ("skipped", "No es de obra"),
        ],
        string="Estado obra OCR",
        default="none",
        copy=False,
    )
    ocr_obra_open_ids = fields.Many2many(
        "project.project",
        compute="_compute_ocr_obra_open_ids",
        string="Obras abiertas",
    )
    ocr_obra_suggested_id = fields.Many2one(
        "project.project",
        string="Obra sugerida",
        copy=False,
    )
    ocr_obra_not_job = fields.Boolean(
        string="No es de obra",
        compute="_compute_ocr_obra_not_job",
        inverse="_inverse_ocr_obra_not_job",
    )

    @api.depends("ocr_obra_state")
    def _compute_ocr_obra_not_job(self):
        for move in self:
            move.ocr_obra_not_job = move.ocr_obra_state == "skipped"

    def _inverse_ocr_obra_not_job(self):
        for move in self:
            if move.ocr_obra_not_job:
                move.ocr_obra_state = "skipped"
                move.project_id = False
                move.ocr_obra_suggested_id = False
            elif move.ocr_obra_state == "skipped":
                move.ocr_obra_state = "none"

    def _open_obra_projects(self):
        cr = self.env.cr
        ids = getattr(cr, "_ocr_open_obra_ids", None)
        if ids is None:
            ids = (
                self.env["sale.order"]
                .search(
                    [("project_id", "!=", False), ("state", "in", ("sale", "done"))]
                )
                .mapped("project_id")
                .ids
            )
            cr._ocr_open_obra_ids = ids
        return self.env["project.project"].browse(ids)

    @api.depends("company_id")
    def _compute_ocr_obra_open_ids(self):
        open_projects = self._open_obra_projects()
        for move in self:
            move.ocr_obra_open_ids = open_projects

    def _vendor_open_obras(self, partner, open_projects=None):
        self.ensure_one()
        if not partner:
            return self.env["project.project"]
        if open_projects is None:
            open_projects = self._open_obra_projects()
        bills = self.search(
            [
                ("partner_id", "=", partner.id),
                ("move_type", "in", ("in_invoice", "in_refund")),
                ("state", "=", "posted"),
                ("project_id", "!=", False),
                ("id", "!=", self._origin.id or 0),
            ]
        )
        return bills.mapped("project_id") & open_projects

    def _sticky_obra(self, partner, open_projects=None):
        last = self.search(
            [
                ("partner_id", "=", partner.id),
                ("ocr_obra_state", "=", "confirmed"),
                ("project_id", "!=", False),
                ("id", "!=", self._origin.id or 0),
            ],
            order="invoice_date desc, id desc",
            limit=1,
        )
        if open_projects is None:
            open_projects = self._open_obra_projects()
        if last.project_id and last.project_id in open_projects:
            return last.project_id
        return self.env["project.project"]

    def _obra_from_so_code(self, data):
        blob = (json.dumps(data or {}, ensure_ascii=False) + " " + " ".join(self.invoice_line_ids.mapped("name") or [])).upper()
        codes = list({m.group(1).upper() for m in _SO_CODE.finditer(blob)})
        if not codes:
            return self.env["project.project"]
        order = self.env["sale.order"].search(
            [
                ("name", "in", codes),
                ("project_id", "!=", False),
                ("state", "in", ("sale", "done")),
            ],
            limit=1,
        )
        return order.project_id

    def _gemini_pick_obra(self, candidates, data):
        # ponytail: skip Gemini in tests; real key would hit the API
        if config.get("test_enable") or not candidates:
            return self.env["project.project"]
        from odoo.addons.incoespacio_ai_core.models.ai_ocr_service import AiOcrService

        orders = self.env["sale.order"].search(
            [("project_id", "in", candidates.ids), ("state", "in", ("sale", "done"))]
        )
        by_project = {}
        for so in orders:
            by_project.setdefault(so.project_id.id, so)
        obras = []
        for project in candidates:
            so = by_project.get(project.id)
            caps = so.order_line.filtered(lambda l: l.display_type == "line_section").mapped("name") if so else []
            obras.append(
                {
                    "id": project.id,
                    "obra": project.name,
                    "pedido": so.name if so else "",
                    "cliente": so.partner_id.name if so else "",
                    "capitulos": caps,
                }
            )
        lineas = [l.get("descripcion") or "" for l in (data or {}).get("lineas") or []]
        if not lineas:
            lineas = self.invoice_line_ids.mapped("name")
        prompt = (
            "Elige la obra de esta factura de subcontrata. "
            "Casi nunca trae el número de pedido del ERP. "
            "Devuelve {\"project_id\": <id o null>}.\n"
            f"Conceptos: {lineas}\nProveedor: {self.partner_id.name}\n"
            f"Obras candidatas: {json.dumps(obras, ensure_ascii=False)}"
        )
        result = AiOcrService.complete_json(self.env, prompt)
        if not result:
            self.message_post(
                body=Markup(
                    "<div class='alert alert-warning'><b>%s</b> %s</div>"
                )
                % (
                    _("Obra IA:"),
                    _("no se pudo sugerir obra automáticamente. Elige el proyecto a mano."),
                ),
                subtype_xmlid="mail.mt_note",
            )
            return self.env["project.project"]
        pid = result.get("project_id")
        picked = candidates.filtered(lambda p: p.id == pid)
        return picked[:1]

    def _suggest_obra(self, data=None):
        self.ensure_one()
        if self.move_type not in ("in_invoice", "in_refund"):
            return
        if self.ocr_obra_state in ("confirmed", "skipped"):
            return
        partner = self.partner_id
        project = self.env["project.project"]
        reason = ""
        apply = False
        open_projects = self._open_obra_projects()
        vendor_obras = self._vendor_open_obras(partner, open_projects)
        if len(vendor_obras) == 1:
            project = vendor_obras
            reason = _("este proveedor ya factura esa obra")
        elif len(vendor_obras) > 1:
            sticky = self._sticky_obra(partner, open_projects)
            if sticky:
                project = sticky
                reason = _("última obra confirmada de este proveedor")
            else:
                project = self._gemini_pick_obra(vendor_obras, data)
                if project:
                    reason = _("IA entre las obras de este proveedor")
        if not project:
            project = self._obra_from_so_code(data)
            if project:
                reason = _("código de pedido en el documento")
                apply = True
        if not project:
            self.ocr_obra_state = "none"
            self.ocr_obra_suggested_id = False
            return
        vals = {"ocr_obra_suggested_id": project.id, "ocr_obra_state": "suggested"}
        if apply:
            vals["project_id"] = project.id
        self.write(vals)
        self.message_post(
            body=Markup(
                "<div class='alert alert-info'><b>%s</b> %s (%s).</div>"
            )
            % (_("Obra sugerida:"), project.display_name, reason),
            subtype_xmlid="mail.mt_note",
        )
        if apply:
            self._suggest_chapters()

    def _suggest_chapters(self):
        self.ensure_one()
        if not self.project_id:
            return
        so = self.env["sale.order"].search(
            [("project_id", "=", self.project_id.id), ("state", "in", ("sale", "done"))],
            limit=1,
        )
        sections = so.order_line.filtered(lambda l: l.display_type == "line_section")
        if not sections:
            return
        for line in self.invoice_line_ids.filtered(lambda l: l.display_type == "product"):
            if (
                line.construction_section_id
                and line.construction_section_id.order_id.project_id == self.project_id
            ):
                continue
            matched = line._match_bc3_section(sections)
            line.construction_section_id = matched.id if matched else False

    def _apply_ai_extracted_data(self, data, force=False):
        res = super()._apply_ai_extracted_data(data, force=force)
        if res and self.move_type in ("in_invoice", "in_refund"):
            self._suggest_obra(data)
        return res

    def action_confirm_obra(self):
        for move in self:
            if not move.project_id and move.ocr_obra_suggested_id:
                move.write(
                    {
                        "project_id": move.ocr_obra_suggested_id.id,
                        "ocr_obra_state": "confirmed",
                    }
                )
            elif move.project_id:
                move.ocr_obra_state = "confirmed"
                move._suggest_chapters()

    def write(self, vals):
        if vals.get("project_id") and "ocr_obra_state" not in vals:
            vals["ocr_obra_state"] = "confirmed"
        res = super().write(vals)
        if vals.get("project_id"):
            for move in self.filtered(lambda m: m.move_type in ("in_invoice", "in_refund")):
                move._suggest_chapters()
        return res

    @api.onchange("project_id")
    def _onchange_project_id_chapters(self):
        if self.project_id:
            self._suggest_chapters()

    def action_post(self):
        for move in self:
            if (
                move.move_type in ("in_invoice", "in_refund")
                and not move.project_id
                and move.ocr_obra_state != "skipped"
            ):
                raise UserError(
                    _("Elige la obra o marca «No es de obra» antes de publicar.")
                )
        return super().action_post()

    @api.model
    def get_active_ocr_batch(self, move_ids=None):
        result = super().get_active_ocr_batch(move_ids=move_ids)
        moves = {m.id: m for m in self.browse([r["id"] for r in result])}
        for row in result:
            move = moves.get(row["id"])
            if not move:
                continue
            row["obra"] = move.project_id.display_name if move.project_id else ""
            row["ocr_obra_state"] = move.ocr_obra_state
        return result
