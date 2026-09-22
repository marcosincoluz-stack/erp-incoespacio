import base64
import re
from datetime import datetime

import chardet

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# V/C/D/T/M. ~T is the long text, ~M the measurement lines.
_BC3_RECORD = re.compile(r"~([VCDTM])\|")
_BC3_NEXT = re.compile(r"~[A-Za-z]\|")
_CHAPTER_TYPES = frozenset({"CA", "OB"})
_UOM_PRODUCT_XMLIDS = (
    "bc3_importer.product_product_product_units",
    "bc3_importer.product_product_product_meter",
    "bc3_importer.product_product_product_square_meter",
    "bc3_importer.product_product_product_cubic_meter",
    "bc3_importer.product_product_product_g",
    "bc3_importer.product_product_product_l",
)


class BC3ImportWizard(models.TransientModel):
    _name = "bc3.import.wizard"
    _description = "Import BC3 file"

    @api.model
    def _default_version(self):
        return self.env.ref("bc3_importer.bc3_version_2020_v2") or self.env[
            "bc3.version"
        ].search([], limit=1)

    bc3_file = fields.Binary(string="BC3 file", required=True)
    bc3_file_name = fields.Char(string="BC3 file name")
    project_id = fields.Many2one("project.project", string="Project")
    version_id = fields.Many2one(
        "bc3.version", string="Version", ondelete="cascade", default=_default_version
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Customer/Vendor",
        store=True,
        readonly=False,
        required=True,
        ondelete="restrict",
        domain="['|', ('parent_id','=', False), ('is_company','=', True)]",
        check_company=True,
    )
    create_products = fields.Boolean("Create non-existent products")
    product_id = fields.Many2one(
        "product.product",
        string="Default product",
        ondelete="cascade",
        help="Select a product which will be used in the BC3 file.",
    )
    sale_id = fields.Many2one("sale.order", "Sale Order")
    sequence = fields.Integer()

    def do_action(self):
        self.ensure_one()
        self.sequence = 0
        so_vals = {"partner_id": self.partner_id.id, "bc3": True}
        if self.project_id and "project_id" in self.env["sale.order"]._fields:
            so_vals["project_id"] = self.project_id.id
        self.sale_id = self.env["sale.order"].create(so_vals).id
        concepts, tree, detail = self._collect_tree()
        self._emit_from_tree(concepts, tree, detail)
        return {
            "name": _("Show Sale Order"),
            "type": "ir.actions.act_window",
            "view_type": "form",
            "view_mode": "form",
            "res_model": "sale.order",
            "views": [(self.env.ref("sale.view_order_form").id, "form")],
            "view_id": self.env.ref("sale.view_order_form").id,
            "target": "current",
            "res_id": self.sale_id.id,
        }

    def _collect_tree(self):
        concepts = {}
        tree = {}
        detail = {"texts": {}, "measures": {}}
        for register in self._iter_bc3_registers(
            self._decode_bc3(base64.decodebytes(self.bc3_file))
        ):
            if not register:
                continue
            kind = register[0].upper()
            if kind == "V":
                if self.sale_id:
                    self._parse_register(register)
            elif kind == "C":
                self._collect_concept(register, concepts)
            elif kind == "D":
                self._collect_decomp(register, tree)
            elif kind == "T":
                self._collect_text(register, detail["texts"])
            elif kind == "M":
                self._collect_measure(register, detail["measures"])
        return concepts, tree, detail

    def _raw_code(self, code):
        return (code or "").split("\\")[0].strip()

    def _code_key(self, code):
        # Presto ~D lists C01, ~C is C01#; strip hashes so the tree matches.
        return self._raw_code(code).rstrip("#")

    def _line_code(self, code):
        return self._code_key(code)

    def _bc3_float(self, raw, default=1.0):
        text = (raw or "").strip().replace(",", ".")
        if not text:
            return default
        try:
            return float(text)
        except ValueError:
            return default

    def _collect_concept(self, register, concepts):
        parts = register.split("|")
        raw = self._raw_code(parts[1] if len(parts) > 1 else "")
        key = raw.rstrip("#")
        if not key:
            return
        price_raw = parts[4] if len(parts) > 4 else ""
        prices = [p for p in price_raw.split("\\") if p.strip()]
        price_vals = [self._bc3_float(p, 0.0) for p in prices]
        tipo = self._code_key(parts[6] if len(parts) > 6 else "")
        concepts[key] = {
            "unit": self._code_key(parts[2] if len(parts) > 2 else ""),
            "summary": (parts[3] if len(parts) > 3 else "").replace("\\", "").strip(),
            "price": price_vals[-1] if price_vals else 0.0,
            "prices": price_vals,  # Incoespacio: ~C puede traer venta\objetivo
            "tipo": tipo,
            "root": raw.endswith("##"),
            "chapter": (raw.endswith("#") and not raw.endswith("##"))
            or tipo in _CHAPTER_TYPES,
        }

    def _parse_d_children(self, payload):
        parts = payload.split("\\")
        while parts and parts[-1] == "":
            parts.pop()
        children = []
        for i in range(0, len(parts), 3):
            code = (parts[i] or "").strip()
            if not code:
                continue
            children.append(
                (
                    self._code_key(code),
                    self._bc3_float(parts[i + 1] if i + 1 < len(parts) else ""),
                    self._bc3_float(parts[i + 2] if i + 2 < len(parts) else ""),
                )
            )
        return children

    def _collect_text(self, register, texts):
        body = register.split("|", 2)
        if len(body) < 3:
            return
        key = self._code_key(body[1])
        if not key:
            return
        text = body[2][:-1] if body[2].endswith("|") else body[2]
        text = text.strip()
        if text:
            texts[key] = text

    def _measure_num(self, raw):
        text = (raw or "").strip().replace(",", ".")
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    def _parse_measure_lines(self, payload):
        parts = (payload or "").split("\\")
        rows = []
        for i in range(0, len(parts) - 5, 6):
            tipo, comment, units, length, width, height = parts[i : i + 6]
            # ponytail: tipo 1/2/3 are subtotal/formula, not a quantity line
            if (tipo or "").strip() in ("1", "2", "3"):
                continue
            nums = [self._measure_num(raw) for raw in (units, length, width, height)]
            comment = (comment or "").replace("\r", "").strip()
            if not comment and all(num is None for num in nums):
                continue
            present = [num for num in nums if num is not None]
            partial = 1.0
            for num in present:
                partial *= num
            rows.append(
                {
                    "comment": comment,
                    "units": nums[0],
                    "length": nums[1],
                    "width": nums[2],
                    "height": nums[3],
                    "partial": partial if present else 0.0,
                }
            )
        return rows

    def _collect_measure(self, register, measures):
        parts = register.split("|")
        ident = parts[1] if len(parts) > 1 else ""
        segs = [self._code_key(seg) for seg in ident.split("\\") if seg.strip()]
        if not segs:
            return
        child = segs[-1]
        parent = segs[-2] if len(segs) > 1 else ""
        payload = parts[4] if len(parts) > 4 else ""
        rows = self._parse_measure_lines(payload)
        if not rows:
            rows = max(
                (self._parse_measure_lines(field) for field in parts[2:]),
                key=len,
                default=[],
            )
        if rows:
            measures.setdefault((parent, child), []).extend(rows)

    def _measures_for(self, measures, parent, child):
        parent = self._code_key(parent)
        child = self._code_key(child)
        if (parent, child) in measures:
            return measures[(parent, child)]
        if ("", child) in measures:
            return measures[("", child)]
        found = [rows for (par, code), rows in measures.items() if code == child]
        if len(found) == 1:
            return found[0]
        return []

    def _collect_decomp(self, register, tree):
        parts = register.split("|")
        parent = self._code_key(parts[1] if len(parts) > 1 else "")
        if not parent:
            return
        payload = parts[2] if len(parts) > 2 else ""
        tree.setdefault(parent, []).extend(self._parse_d_children(payload))

    def _is_root(self, code, concept):
        return bool((concept or {}).get("root") or (code or "").endswith("##"))

    def _is_chapter(self, code, concept, tree):
        concept = concept or {}
        if concept.get("chapter") or concept.get("tipo") in _CHAPTER_TYPES:
            return True
        # no UoM + has children = capítulo (Presto tipo 0 is also used on partidas)
        return not concept.get("unit") and bool(tree.get(code))

    def _emit_from_tree(self, concepts, tree, detail=None):
        roots = [code for code, concept in concepts.items() if concept.get("root")]
        if not roots:
            child_codes = {child for nodes in tree.values() for child, _, _ in nodes}
            roots = [parent for parent in tree if parent not in child_codes]
        prices = {}
        detail = detail or {}
        for root in roots:
            self._emit_node(root, 1.0, 1.0, concepts, tree, prices, 0, "", detail)

    def _emit_node(
        self,
        code,
        factor,
        rendimiento,
        concepts,
        tree,
        prices,
        level=0,
        parent="",
        detail=None,
    ):
        concept = concepts.get(code) or {}
        detail = detail or {}
        if self._is_root(code, concept):
            for child, child_factor, child_rend in tree.get(code, []):
                self._emit_node(
                    child, child_factor, child_rend, concepts, tree, prices, 0, "", detail
                )
            return
        if self._is_chapter(code, concept, tree):
            self._create_section(code, concept, level)
            for child, child_factor, child_rend in tree.get(code, []):
                self._emit_node(
                    child,
                    child_factor,
                    child_rend,
                    concepts,
                    tree,
                    prices,
                    level + 1,
                    code,
                    detail,
                )
            return
        self._create_partida(
            code,
            concept,
            factor * rendimiento,
            concepts,
            tree,
            prices,
            level,
            parent,
            detail,
        )

    def _create_section(self, code, concept, level=0):
        line_code = self._line_code(code)
        summary = concept.get("summary") or line_code
        self.env["sale.order.line"].create(
            {
                "order_id": self.sale_id.id,
                "display_type": "line_section",
                "bc3_code": line_code,
                "bc3_level": level,
                "name": "[%s] %s" % (line_code, summary),
                "sequence": self.sequence,
            }
        )
        self.sequence += 1

    def _percent_prefix(self, code):
        for i, ch in enumerate(code or ""):
            if ch in "%&":
                return code[:i]
        return ""

    def _concept_price(self, code, concepts, tree, prices):
        if code in prices:
            return prices[code]
        prices[code] = (concepts.get(code) or {}).get("price") or 0.0
        children = tree.get(code)
        if not children:
            return prices[code]
        lines = []
        for child, factor, rend in children:
            prefix = self._percent_prefix(child)
            if "%" in child or "&" in child:
                base = sum(amt for c, amt in lines if c.startswith(prefix))
                amount = base * factor * rend
            else:
                amount = (
                    factor * rend * self._concept_price(child, concepts, tree, prices)
                )
            lines.append((child, amount))
        prices[code] = sum(amt for _, amt in lines)
        return prices[code]

    def _create_partida(
        self,
        code,
        concept,
        qty,
        concepts,
        tree,
        prices,
        level=0,
        parent="",
        detail=None,
    ):
        line_code = self._line_code(code)
        summary = concept.get("summary") or line_code
        product, uom_id = self._product_for_line(line_code, concept)
        detail = detail or {}
        measures = self._measures_for(detail.get("measures") or {}, parent, line_code)
        self.env["sale.order.line"].create(
            {
                "order_id": self.sale_id.id,
                "bc3_code": line_code,
                "bc3_level": level,
                "bc3_text": (detail.get("texts") or {}).get(line_code) or False,
                "bc3_measures": measures or False,
                "name": "[%s] %s" % (line_code, summary),
                "product_id": product.id,
                "product_uom": uom_id,
                "product_uom_qty": qty,
                "price_unit": self._concept_price(code, concepts, tree, prices),
                "sequence": self.sequence,
            }
        )
        self.sequence += 1

    def _product_for_line(self, line_code, concept):
        uom_products = self.get_uom_products()
        uom_id = (
            self._search_create_uom(concept["unit"]) if concept.get("unit") else False
        )
        product = uom_products.get(uom_id) if uom_id else None
        if self.create_products:
            product = self._search_create_product([line_code])
            if concept.get("summary"):
                product.name = concept["summary"]
        if not product:
            product = self.env.ref("bc3_importer.product_product_product_units")
        if not uom_id or uom_id not in uom_products:
            uom_id = product.uom_id.id
        return product, uom_id

    @api.model
    def _parse_register_sale_order(
        self, parsed_line, rules, current_register, red=False
    ):
        if len(parsed_line) == len(rules):
            i = 0
            for rule in rules:
                if len(parsed_line[i]) == 1:
                    self.sale_id[rule.field_id.name] = self._parse_data(
                        parsed_line[i][0], rule.field_id.ttype
                    )
                elif len(parsed_line[i]) > 1:
                    if self.sale_id[rule.field_id.name]:
                        self.sale_id[rule.field_id.name] += self._parse_child_data(
                            parsed_line[i], rule.field_id.ttype
                        )
                    else:
                        self.sale_id[rule.field_id.name] = self._parse_child_data(
                            parsed_line[i], rule.field_id.ttype
                        )
                i += 1
        return True

    @api.model
    def _search_create_product(self, code):
        Product = self.env["product.product"]
        product = Product.search([("default_code", "ilike", code[0])], limit=1)
        if product:
            return product
        if self.create_products:
            code_temp = "-".join(code) if len(code) > 1 else code[0]
            return Product.create(
                {
                    "name": _("Dynamic Product ") + code_temp,
                    "default_code": code_temp,
                }
            )
        return self.env.ref("bc3_importer.product_product_product_units")

    @api.model
    def _search_create_uom(self, name):
        uom = False
        if name == "m3" or name == "M3" or name == "m³":
            uom = self.env.ref("uom.product_uom_cubic_meter").id or False
        elif name == "m²" or name == "M2" or name == "m2":
            uom = self.env.ref("bc3_importer.product_uom_square_meter").id or False
        elif name == "ud":
            uom = self.env.ref("uom.product_uom_unit").id or False
        else:
            uom = (
                self.env["uom.uom"]
                .search(
                    [
                        "|",
                        "|",
                        ("name", "ilike", name),
                        ("name", "ilike", name.upper()),
                        ("name", "ilike", name.lower()),
                    ],
                    limit=1,
                )
                .id
                or False
            )
        return uom

    @api.model
    def _parse_data(self, data, field_type):
        data = data.replace("\\", "").replace("#", "")
        if field_type in ["char", "text"]:
            return data
        if field_type == "date":
            # if odd -> 0
            if not len(data) % 2 == 0:
                data += "0"
            # AA
            if len(data) == 2:
                return datetime.strptime(data, "%y").date()
            # MMAA
            elif len(data) == 4:
                return datetime.strptime(data, "%m%y").date()
            # DDMMAA
            elif len(data) == 6:
                return datetime.strptime(data, "%d%m%y").date()
            # DDMMAAAA
            elif len(data) == 8:
                return datetime.strptime(data, "%d%m%Y").date()
            return data
        return data

    @api.model
    def _parse_child_data(self, data, field_type):
        if field_type == "char" or field_type == "text":
            result = ""
            for d in data:
                d = d.replace("\\", "").replace("\\\\", "")
                result += d + ";"
            return result
        elif field_type == "float":
            if len(data) > 0:
                return float(data[-1].replace("\\", ""))
            else:
                return float(data.replace("\\", ""))
        return data

    def _parse_register_data(
        self, register_rules, register_line, current_register, model, render_func
    ):
        regular_expression = []
        parser_result = []
        for r in register_rules.filtered(lambda x: not x.is_child):
            regular_expression.append(r.regular_expression)
        if len(regular_expression) == len(register_line):
            i = 0
            while i < len(regular_expression):
                parser_result.append(
                    self._get_results(
                        regular_expression[i], register_line[i].replace("\n", "")
                    )
                )
                i += 1
        else:
            raise ValidationError(_("Parsing error, missing data"))
        if len(parser_result) > 0:
            final_result = []
            for i in parser_result:
                if len(i) > 1:
                    for j in i:
                        final_result.append(j)
                elif not len(i) == 0:
                    final_result.append(i[0])
                else:
                    final_result.append([])
            if register_rules[0].register_id.edit_existent:
                raise UserError(_("Error parsing the file"))
            render_func(final_result, register_rules, current_register)

    @api.model
    def _decode_bc3(self, raw):
        head = raw[:200].decode("ascii", errors="replace").upper()
        if "UTF-8" in head or "UTF8" in head:
            enc = "utf-8"
        elif any(tag in head for tag in ("ANSI", "8859-1", "1252")):
            enc = "cp1252"
        else:
            # ponytail: header charset first; chardet on 4k only (full Presto files are binary)
            enc = (chardet.detect(raw[:4096]) or {}).get("encoding") or "cp1252"
        return raw.decode(enc, errors="replace")

    @api.model
    def _iter_bc3_registers(self, text):
        """Yield ~V/~C/~D/~T. Presto 8.8 glue drawings as NULs after ~T; don't split on every ~."""
        in_blob = False
        for m in _BC3_RECORD.finditer(text):
            prev = text[m.start() - 1] if m.start() else "\n"
            if prev == "\x00" or (in_blob and prev not in "\n\r"):
                continue
            in_blob = False
            rest = text[m.end() :]
            nxt = _BC3_NEXT.search(rest)
            end = nxt.start() if nxt else len(rest)
            nul = rest.find("\x00", 0, end)
            if nul != -1:
                end = nul
                in_blob = True
            yield m.group(1) + "|" + rest[:end]

    def _parse_register(self, line):
        if not line or line[0].lower() not in "vcdt":
            return
        register_type = line[0].lower()
        current_register = register_type
        register_line = (
            line[1:]
            .rstrip()
            .replace("�", "")
            .replace("(", ",")
            .replace(")", ",")
            .replace("[", ",")
            .replace("]", ",")
            .strip()
            .split("|")
        )
        register_rules = (
            self.env["bc3.version.register"]
            .search(
                [
                    ("name", "ilike", register_type),
                    ("version_id", "=", self.version_id.id),
                ],
                limit=1,
            )
            .rule_ids
        )

        if (
            register_rules
            and register_rules[0]
            and register_rules[0].register_id.model_id
        ):
            model = register_rules[0].register_id.model_id.model.replace(".", "_")
            register_line.pop(0)
            if len(register_line) < len(
                register_rules.filtered(lambda x: not x.is_child)
            ):
                for _i in range(
                    abs(
                        len(register_rules.filtered(lambda x: not x.is_child))
                        - len(register_line)
                    )
                ):
                    register_line.append("")
            elif len(register_line) > len(
                register_rules.filtered(lambda x: not x.is_child)
            ):
                for _i in range(
                    abs(
                        len(register_rules.filtered(lambda x: not x.is_child))
                        - len(register_line)
                    )
                ):
                    register_line.pop()
            render_func = getattr(self, "_parse_register_" + model, None)
            if not render_func:
                raise UserError(_("Error parsing the file"))

            self._parse_register_data(
                register_rules, register_line, current_register, model, render_func
            )

    def get_groups_matches(self, group_id, check_list, text, group_pattern):
        # Hay que revisar las substring:
        for a in check_list:
            t = text[a[0] : a[1]]
            matches = re.finditer(group_pattern[group_id]["expression"], t)
            last_index = (0, 0)
            for match in matches:
                if match.lastindex:
                    for index in range(1, match.lastindex + 1):
                        group_pattern[str(group_id)]["groups"].insert(
                            0, match.group(index)
                        )
                    if not last_index[0] == match.span(index)[0]:
                        group_pattern[str(group_id)]["check"].append(
                            (last_index[0], match.span(index)[0])
                        )
            group_pattern[str(group_id)]["check"].remove(a)
        if len(group_pattern[group_id]["check"]) > 0:
            self.get_groups_matches(
                group_id, group_pattern[group_id]["check"], t, group_pattern
            )
        else:
            return True

    def _parse_matches(self, matches, group_pattern):
        for match in matches:
            # Recorro los grupos
            # Empiezo en 1 porque el primer grupo es todo el match, no me interesa
            last_index = (0, 0)
            if match.lastindex:
                if match.lastindex > 1:
                    for index in range(1, match.lastindex + 1):
                        if str(index) in group_pattern and match.group(index):
                            group_pattern[str(index)]["groups"].append(
                                match.group(index)
                            )
                            # Es el primer grupo
                            if index == 1:
                                last_index = match.span(index)
                            else:
                                if not last_index[1] == match.span(index)[0]:
                                    group_pattern[str(index)]["check"].append(
                                        (last_index[1], match.span(index)[0])
                                    )
                                last_index = match.span(index)
                else:
                    for index in range(1, match.lastindex + 1):
                        if str(index) in group_pattern and match.group(index):
                            group_pattern[str(index)]["groups"].append(
                                match.group(index)
                            )
                            if not last_index[1] == match.span(index)[0]:
                                group_pattern[str(index)]["check"].append(
                                    (last_index[1], match.span(index)[0])
                                )
                                last_index = match.span(index)
        return group_pattern

    def _get_results(self, pattern, text):
        text = text.rstrip()
        result = []
        if pattern:
            pattern_2 = pattern.split("(")
            group_pattern = {}
            counter = 1
            for p in pattern_2:
                if p:
                    group_pattern[str(counter)] = {
                        "expression": "(" + p,
                        "groups": [],
                        "check": [],
                    }
                    counter += 1
            matches = re.finditer(pattern, text)
            group_pattern = self._parse_matches(matches, group_pattern)

            # Reviso los checks
            for i in group_pattern:
                if len(group_pattern[i]["check"]) > 0:
                    self.get_groups_matches(
                        i, group_pattern[i]["check"], text, group_pattern
                    )
            for i in group_pattern:
                result.append(group_pattern[i]["groups"])
        return result

    @api.model
    def get_uom_products(self):
        return {
            self.env.ref(xmlid).uom_id.id: self.env.ref(xmlid)
            for xmlid in _UOM_PRODUCT_XMLIDS
        }
