import re

from odoo import api, models
from odoo.osv.expression import AND, OR

_CODE_TAIL = re.compile(r"^(.*\D)(\d+)$")
_WORD = re.compile(r"[a-z]{5,}")
_FOLD = str.maketrans("áéíóúüñ", "aeiouun")
_POSITIVE = ("ilike", "like", "=ilike", "=like")
# ponytail: prefix tokens only (tab. → tabique, acom. → acometida), and only if the
# long text says that word. Contractions that are not a prefix (gnral, s/sold) stay unmatched.
# A shorter word can still hit a longer one in the text (tabla → tablero).


def _fold(text):
    return (text or "").lower().translate(_FOLD)


def _leaves(domain):
    for item in domain or ():
        if isinstance(item, (list, tuple)) and item and isinstance(item[0], str):
            yield item


def price_abbrev_ids(model, term):
    words = _WORD.findall(_fold(term))
    categ = model.env.ref(
        "incoespacio_bc3_price_db.price_db_category", raise_if_not_found=False
    )
    if not words or not categ:
        return []
    model.env.flush_all()
    found = None
    for word in words:
        model.env.cr.execute(
            """
            SELECT DISTINCT pp.id
              FROM product_product pp
              JOIN product_template pt ON pt.id = pp.product_tmpl_id
              CROSS JOIN LATERAL (
                    SELECT translate(lower(
                               coalesce(pt.name->>'es_ES', '') || ' ' ||
                               coalesce(pt.name->>'en_US', '')
                           ), 'áéíóúüñ', 'aeiouun') AS folded_name,
                           translate(lower(
                               coalesce(pt.description_sale->>'es_ES', '') || ' ' ||
                               coalesce(pt.description_sale->>'en_US', '')
                           ), 'áéíóúüñ', 'aeiouun') AS folded_desc
              ) f
             WHERE pt.categ_id = %s
               AND pp.active AND pt.active AND pt.sale_ok
               AND EXISTS (
                    SELECT 1
                      FROM regexp_matches(f.folded_name, '\\m[a-z]{3,}\\.?', 'g') AS tok
                     WHERE left(%s, char_length(rtrim(tok[1], '.'))) = rtrim(tok[1], '.')
                       AND char_length(rtrim(tok[1], '.')) < char_length(%s)
                       AND f.folded_desc ~ ('\\m' || %s)
               )
            """,
            [categ.id, word, word, word],
        )
        ids = {row[0] for row in model.env.cr.fetchall()}
        found = ids if found is None else found & ids
    product_ids = list(found or ())
    if model._name == "product.template":
        return model.env["product.product"].browse(product_ids).product_tmpl_id.ids
    return product_ids


def price_abbrev_domain(model, domain):
    if model.env.context.get("price_abbrev_skip"):
        return domain
    categ = model.env.ref(
        "incoespacio_bc3_price_db.price_db_category", raise_if_not_found=False
    )
    term = ""
    seen = False
    for leaf in _leaves(domain):
        if (
            len(leaf) >= 3
            and leaf[0] == "categ_id"
            and leaf[1] == "="
            and categ
            and leaf[2] == categ.id
        ):
            seen = True
        elif (
            len(leaf) >= 3
            and leaf[0] == "name"
            and leaf[1] in _POSITIVE
            and isinstance(leaf[2], str)
            and not term
        ):
            term = leaf[2]
    if not seen or not term:
        return domain
    ids = price_abbrev_ids(model, term)
    if not ids:
        return domain
    # active=True is applied by _where_calc to the whole OR. Don't add it here.
    return OR([domain, AND([[("categ_id", "=", categ.id)], [("id", "in", ids)]])])


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model
    def price_db_domain(self):
        categ = self._price_db_category()
        if not categ:
            return [("id", "=", 0)]
        return [("categ_id", "=", categ.id), ("sale_ok", "=", True)]

    @api.model
    def _name_search(self, name, domain=None, operator="ilike", limit=None, order=None):
        domain = list(domain or [])
        if self.env.context.get("price_db_only"):
            domain = self.price_db_domain() + domain
        me = self.with_context(price_abbrev_skip=True)
        found = super(ProductProduct, me)._name_search(
            name, domain, operator, limit=limit, order=order
        )
        if (
            not name
            or operator not in _POSITIVE
            or not self.env.context.get("price_db_only")
        ):
            return found
        extra_ids = price_abbrev_ids(self, name)
        if not extra_ids:
            return found
        found = list(found)
        extra = [i for i in extra_ids if i not in set(found)]
        if not extra:
            return found
        if not limit:
            return found + extra
        # Half the menu stays on the full word, half on the abbreviation.
        chosen = found[: max(limit // 2, 1)]
        seen = set(chosen)
        for item in extra + found:
            if len(chosen) >= limit:
                break
            if item in seen:
                continue
            chosen.append(item)
            seen.add(item)
        return chosen

    @api.model
    def price_db_search_ids(self, name):
        return list(
            self.with_context(price_db_only=True)._name_search(
                name, [], "ilike", limit=None
            )
        )

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, access_rights_uid=None):
        domain = price_abbrev_domain(self, domain)
        return super()._search(
            domain,
            offset=offset,
            limit=limit,
            order=order,
            access_rights_uid=access_rights_uid,
        )

    def _price_db_category(self):
        return self.env.ref(
            "incoespacio_bc3_price_db.price_db_category", raise_if_not_found=False
        )

    def _next_price_code(self, base, extra=()):
        # ponytail: one ilike of this prefix, no lock. Two creates at once can take the same code.
        match = _CODE_TAIL.match((base or "").strip())
        if not match:
            return False
        prefix, digits = match.group(1), match.group(2)
        codes = list(extra)
        codes.extend(
            self.search([("default_code", "=ilike", prefix + "%")]).mapped(
                "default_code"
            )
        )
        tail = re.compile("^" + re.escape(prefix) + r"(\d+)$", re.IGNORECASE)
        max_n = int(digits)
        width = len(digits)
        for code in codes:
            found = tail.match(code or "")
            if not found:
                continue
            max_n = max(max_n, int(found.group(1)))
            width = max(width, len(found.group(1)))
        return prefix + str(max_n + 1).zfill(width)

    @api.model_create_multi
    def create(self, vals_list):
        base = self.env.context.get("price_db_base_code")
        categ = self._price_db_category() if base else False
        if categ:
            given = []
            for vals in vals_list:
                if vals.get("default_code"):
                    continue
                categ_id = vals.get("categ_id") or self.env.context.get(
                    "default_categ_id"
                )
                if categ_id != categ.id:
                    continue
                code = self._next_price_code(base, given)
                if not code:
                    break
                vals["default_code"] = code
                given.append(code)
        return super().create(vals_list)
