from odoo import _, fields, models
from odoo.tools.misc import formatLang


def _custom_report_values(env, model_name, docids, data):
    # ponytail: ?options= drops ids from the report URL. Recover via active_ids.
    # Drop these report models if the URL ever keeps options and ids together.
    data = data or {}
    if not docids:
        docids = env.context.get("active_ids") or []
    return {
        "doc_ids": docids,
        "doc_model": model_name,
        "docs": env[model_name].browse(docids),
        "custom": bool(data.get("custom")),
        "formatLang": lambda value, digits=2, **kwargs: formatLang(
            env, value, digits=digits, **kwargs
        ),
    }


def _is_root_chapter(line):
    return line.display_type == "line_section" and not line.bc3_level


def _filter_report_lines(lines, first, last, keep_partida, drop_null_chapters, amount):
    """Keep a chapter range, then drop null partidas and the chapters they empty."""
    if not lines:
        return lines
    blocks = []
    current = None
    for line in lines:
        if _is_root_chapter(line):
            if current is not None:
                blocks.append(current)
            current = [line]
        else:
            if current is None:
                current = []
            current.append(line)
    if current is not None:
        blocks.append(current)
    if first or last:
        start, end = 0, len(blocks)
        for index, block in enumerate(blocks):
            if not block or not _is_root_chapter(block[0]):
                continue
            if first and block[0] == first:
                start = index
            if last and block[0] == last:
                end = index + 1
        blocks = [
            block
            for block in blocks[start:end]
            if block and _is_root_chapter(block[0])
        ]
    ids = []
    for block in blocks:
        ids.extend(line.id for line in _trim_block(block, keep_partida, drop_null_chapters, amount))
    return lines.browse(ids)


def _trim_block(block, keep_partida, drop_null_chapters, amount):
    had = set()
    section_id = None
    for line in block:
        if line.display_type == "line_section":
            section_id = line.id
        elif section_id:
            had.add(section_id)
    body = [line for line in block if line.display_type or keep_partida(line)]
    body = _drop_emptied_subchapters(body, had)
    partidas = [line for line in body if not line.display_type]
    chapter_had = any(not line.display_type for line in block)
    if chapter_had and not partidas:
        return []
    if drop_null_chapters and not sum(amount(line) for line in partidas):
        return []
    return body


def _drop_emptied_subchapters(body, had):
    result = []
    index = 0
    while index < len(body):
        line = body[index]
        if line.display_type == "line_section" and line.bc3_level and line.id in had:
            nxt = index + 1
            while nxt < len(body) and body[nxt].display_type != "line_section":
                nxt += 1
            span = body[index + 1 : nxt]
            if any(not item.display_type for item in span):
                result.append(line)
                result.extend(span)
            index = nxt
        else:
            result.append(line)
            index += 1
    return result


def _chapter_label(line):
    name = (line.name or "").strip()
    code = line.bc3_code or ""
    prefix = "[%s]" % code
    if code and name.startswith(prefix):
        name = name[len(prefix) :].strip()
    return code, name or code


class SaleOrder(models.Model):
    _inherit = "sale.order"

    print_chapter_first_id = fields.Many2one(
        "sale.order.line", string="Capítulo inicial", ondelete="set null"
    )
    print_chapter_last_id = fields.Many2one(
        "sale.order.line", string="Capítulo final", ondelete="set null"
    )
    print_hide_null_chapters = fields.Boolean(string="Ocultar capítulos con importe nulo")
    print_hide_null_price = fields.Boolean(string="Ocultar partidas con precio nulo")
    print_hide_null_qty = fields.Boolean(string="Ocultar partidas con cantidad nula")

    def _keep_print_partida(self, line):
        if self.print_hide_null_price and not line.price_unit:
            return False
        if self.print_hide_null_qty and not line.product_uom_qty:
            return False
        return True

    def _get_custom_report_lines(self):
        self.ensure_one()
        return _filter_report_lines(
            self._get_order_lines_to_report(),
            self.print_chapter_first_id,
            self.print_chapter_last_id,
            self._keep_print_partida,
            self.print_hide_null_chapters,
            lambda line: line.price_subtotal or 0.0,
        )

    def _get_chapter_summary(self, lines=None):
        """Capítulos de nivel 0 con el importe de sus partidas, subcapítulos incluidos."""
        self.ensure_one()
        source = (
            self.order_line.sorted(key=lambda item: (item.sequence, item.id))
            if lines is None
            else lines
        )
        chapters = []
        current = None
        for line in source:
            if _is_root_chapter(line):
                code, name = _chapter_label(line)
                current = {"code": code, "name": name, "amount": 0.0}
                chapters.append(current)
            elif not line.display_type and current:
                current["amount"] += line.price_subtotal or 0.0
            # ponytail: partidas before the first level-0 chapter are dropped.
            # Fold them into a synthetic chapter if a quote without chapters must summarize.
        total = (
            (self.amount_untaxed or 0.0)
            if lines is None
            else sum(chapter["amount"] for chapter in chapters)
        )
        for chapter in chapters:
            chapter["pct"] = chapter["amount"] / total * 100.0 if total else 0.0
        return chapters

    def action_print_custom(self):
        self.ensure_one()
        view = self.env.ref(
            "incoespacio_construction_print_options.view_sale_order_print_custom"
        )
        return {
            "name": _("PDF personalizado"),
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "res_id": self.id,
            "view_mode": "form",
            "views": [(view.id, "form")],
            "target": "new",
        }

    def action_print_custom_pdf(self):
        self.ensure_one()
        return self.env.ref("sale.action_report_saleorder").report_action(
            self, data={"custom": True}
        )


class ConstructionCertification(models.Model):
    _inherit = "construction.certification"

    print_full_text = fields.Boolean(string="Con texto completo")
    print_chapter_first_id = fields.Many2one(
        "construction.certification.line", string="Capítulo inicial", ondelete="set null"
    )
    print_chapter_last_id = fields.Many2one(
        "construction.certification.line", string="Capítulo final", ondelete="set null"
    )
    print_hide_null_chapters = fields.Boolean(
        string="Ocultar capítulos sin importe en el periodo"
    )
    print_hide_null_price = fields.Boolean(string="Ocultar partidas con precio nulo")
    print_hide_null_qty = fields.Boolean(
        string="Ocultar partidas sin medición en el periodo"
    )

    def _keep_print_partida(self, line):
        if self.print_hide_null_price and not line.price_unit:
            return False
        if self.print_hide_null_qty and not line.qty_period:
            return False
        return True

    def _get_custom_report_lines(self):
        self.ensure_one()
        return _filter_report_lines(
            self._get_report_lines(),
            self.print_chapter_first_id,
            self.print_chapter_last_id,
            self._keep_print_partida,
            self.print_hide_null_chapters,
            lambda line: line.amount_period or 0.0,
        )

    def action_print_custom(self):
        self.ensure_one()
        view = self.env.ref(
            "incoespacio_construction_print_options.view_certification_print_custom"
        )
        return {
            "name": _("PDF personalizado"),
            "type": "ir.actions.act_window",
            "res_model": "construction.certification",
            "res_id": self.id,
            "view_mode": "form",
            "views": [(view.id, "form")],
            "target": "new",
        }

    def action_print_custom_pdf(self):
        self.ensure_one()
        return self.env.ref(
            "incoespacio_construction_certification.action_report_construction_certification"
        ).report_action(self, data={"custom": True})


class ReportSaleOrder(models.AbstractModel):
    _name = "report.sale.report_saleorder"
    _description = "Presupuesto"

    def _get_report_values(self, docids, data=None):
        return _custom_report_values(self.env, "sale.order", docids, data)


class ReportCertification(models.AbstractModel):
    _name = "report.incoespacio_construction_certification.report_certification_document"
    _description = "Certificación"
    # The report name is fixed by the existing action; the default table name exceeds 63 chars.
    _table = "report_cert_print_options"

    def _get_report_values(self, docids, data=None):
        return _custom_report_values(
            self.env, "construction.certification", docids, data
        )
