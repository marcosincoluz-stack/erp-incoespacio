from odoo import _, api, fields, models
from odoo.exceptions import UserError

# FIEBDC: 1 mano de obra, 2 maquinaria, 3 material. La partida llega como 0, vacío o EU.
_RESOURCE_TIPOS = frozenset({"1", "2", "3"})
_GENERIC_NAMES = (
    ("bc3_importer.product_product_product_units", "Sin vincular (ud)"),
    ("bc3_importer.product_product_product_meter", "Sin vincular (ml)"),
    ("bc3_importer.product_product_product_square_meter", "Sin vincular (m²)"),
    ("bc3_importer.product_product_product_cubic_meter", "Sin vincular (m³)"),
    ("bc3_importer.product_product_product_g", "Sin vincular (g)"),
    ("bc3_importer.product_product_product_l", "Sin vincular (L)"),
)
# Copies created beside the variants. Some old lines point at them.
_GENERIC_COPIES = (
    ("bc3_importer.product_product_product_template_units", "Sin vincular (ud)"),
    ("bc3_importer.product_product_product_template_meter", "Sin vincular (ml)"),
    ("bc3_importer.product_product_product_template_square_meter", "Sin vincular (m²)"),
    ("bc3_importer.product_product_product_template_cubic_meter", "Sin vincular (m³)"),
    ("bc3_importer.product_product_product_template_g", "Sin vincular (g)"),
    ("bc3_importer.product_product_product_template_l", "Sin vincular (L)"),
)
# ponytail: one create() per chunk, no commit. Split with commit if a real bank exceeds the worker CPU limit.
_CREATE_CHUNK = 500


class Bc3PriceImportWizard(models.TransientModel):
    _name = "bc3.price.import.wizard"
    _description = "Importar base de precios BC3"

    bc3_file = fields.Binary(string="Fichero BC3", required=True)
    bc3_file_name = fields.Char(string="Nombre")

    def _rename_in_langs(self, xmlid, name, langs):
        record = self.env.ref(xmlid, raise_if_not_found=False)
        if not record:
            return record
        for lang in langs:
            translated = record.with_context(lang=lang)
            if translated.name != name:
                translated.name = name
        return record

    @api.model
    def _rename_generic_products(self):
        # noupdate=1 on bc3_importer product data, so an XML write of those xmlids is skipped.
        # name is translated: write every installed language or es_ES keeps "m²".
        langs = [code for code, _label in self.env["res.lang"].get_installed()]
        for xmlid, name in _GENERIC_NAMES:
            self._rename_in_langs(xmlid, name, langs)
        for xmlid, name in _GENERIC_COPIES:
            record = self._rename_in_langs(xmlid, name, langs)
            if record and record.sale_ok:
                record.sale_ok = False

    def action_import(self):
        self.ensure_one()
        if not self.bc3_file:
            raise UserError(_("Falta el fichero BC3."))
        parser = self.env["bc3.import.wizard"].new({"bc3_file": self.bc3_file})
        concepts, tree, detail = parser._collect_tree()
        texts = detail.get("texts") or {}
        partidas = {
            code: concept
            for code, concept in concepts.items()
            if self._is_partida(parser, code, concept, tree)
        }
        if not partidas:
            raise UserError(_("El fichero no contiene partidas."))
        categ = self.env.ref("incoespacio_bc3_price_db.price_db_category")
        existing = {
            product.default_code: product
            for product in self.env["product.template"].search(
                [
                    ("default_code", "in", list(partidas)),
                    ("categ_id", "=", categ.id),
                ]
            )
        }
        prices = {}
        uoms = {}
        to_create = []
        Product = self.env["product.template"].with_context(
            tracking_disable=True, mail_create_nolog=True
        )
        for code, concept in partidas.items():
            vals = self._partida_vals(
                parser, code, concept, concepts, tree, prices, texts, categ, uoms
            )
            product = existing.get(code)
            if product:
                product.write(vals)
            else:
                to_create.append(vals)
        for start in range(0, len(to_create), _CREATE_CHUNK):
            Product.create(to_create[start : start + _CREATE_CHUNK])
        return self.env["ir.actions.act_window"]._for_xml_id(
            "incoespacio_bc3_price_db.action_price_db"
        )

    def _is_partida(self, parser, code, concept, tree):
        unit = concept.get("unit") or ""
        if not unit or unit in {"%", "&"}:
            return False
        if parser._is_root(code, concept) or parser._is_chapter(code, concept, tree):
            return False
        return (concept.get("tipo") or "") not in _RESOURCE_TIPOS

    def _partida_vals(
        self, parser, code, concept, concepts, tree, prices, texts, categ, uoms
    ):
        unit = concept.get("unit") or ""
        if unit not in uoms:
            # ponytail: unknown UoM stays on the product default (Units)
            uoms[unit] = parser._search_create_uom(unit)
        vals = {
            "name": concept.get("summary") or code,
            "default_code": code,
            "list_price": parser._concept_price(code, concepts, tree, prices),
            "description_sale": texts.get(code) or False,
            "categ_id": categ.id,
            "detailed_type": "service",
            "sale_ok": True,
            "purchase_ok": False,
        }
        if uoms[unit]:
            vals["uom_id"] = uoms[unit]
            vals["uom_po_id"] = uoms[unit]
        return vals
