from odoo import fields, models

from odoo.addons.incoespacio_assistant_ai_data.models.question import (
    BLOCKED_MODELS,
    blocked_field,
)

MAX_LIMIT = 50
# Operadores que puede pedir la IA y los que admite cada tipo de campo.
OPERATORS = ("=", "!=", ">", ">=", "<", "<=", "contiene", "en", "vacio")
COMPARE = {"=", "!=", ">", ">=", "<", "<=", "vacio"}
TYPE_OPS = {
    "texto": {"=", "!=", "contiene", "vacio"},
    "fecha": COMPARE,
    "numero": COMPARE,
    "si_no": {"="},
    "opcion": {"=", "!=", "en"},
    "relacion": {"=", "contiene", "vacio"},  # «=» busca por el nombre, como «contiene»
}
KINDS = {
    "char": "texto",
    "text": "texto",
    "date": "fecha",
    "datetime": "fecha",
    "integer": "numero",
    "float": "numero",
    "monetary": "numero",
    "boolean": "si_no",
    "selection": "opcion",
    "many2one": "relacion",
}
YES = {"si", "sí", "true", "1", "yes"}


class CatalogError(ValueError):
    """Algo que no está en el catálogo o no tiene sentido: se le dice a la IA."""


def _kind(field):
    return KINDS.get(field.type)


def _in_db(field):
    # Guardado en su tabla o en la del registro del que hereda (la fecha de un
    # pago está en su asiento): se puede ordenar y agrupar en la base de datos.
    return bool(field.store or getattr(field, "inherited", False))


class AssistantAIQuestion(models.Model):
    _inherit = "assistant.ai.question"

    def _catalog(self):
        """{nombre: entrada} de lo que IncoBot puede consultar. Cada módulo añade
        lo suyo. Una entrada:

        {"model": "account.move", "help": "…", "domain": [base fija],
         "order": "orden por defecto", "labels": ["campos para el enlace"],
         "fields": {"nombre_en_español": ("campo_odoo", "qué significa"[, grupo])}}

        El grupo (xmlid), si lo hay, hace falta para ver ese campo: p. ej. el
        margen, que solo cuadra si se ven todas las facturas de proveedor.
        """
        return {}

    def _catalog_checked(self):
        # Segunda barrera: nada del catálogo puede tocar lo bloqueado.
        catalog = self._catalog()
        for name, entry in catalog.items():
            if entry["model"] in BLOCKED_MODELS:
                raise CatalogError("%s: modelo bloqueado" % name)
            Model = self.env[entry["model"]]
            for label, spec in entry["fields"].items():
                field = spec[0]
                if blocked_field(field) or field not in Model._fields:
                    raise CatalogError("%s.%s: campo no permitido" % (name, label))
                if not _kind(Model._fields[field]):
                    raise CatalogError("%s.%s: tipo no admitido" % (name, label))
        return catalog

    # ------------------------------------------------------------------ #
    # La herramienta
    # ------------------------------------------------------------------ #
    def _tools(self):
        tools = super()._tools()
        catalog = self._catalog_checked()
        if catalog:
            spec = self._catalog_spec(catalog)
            tools[spec["name"]] = (spec, self._tool_query)
        return tools

    def _catalog_spec(self, catalog):
        env = self.env(context=dict(self.env.context, lang=self.user_id.lang))
        lines = []
        for name, entry in catalog.items():
            Model = env[entry["model"]]
            lines.append("- %s: %s Campos:" % (name, entry["help"]))
            for label, (field, help_text, *_group) in entry["fields"].items():
                odoo = Model._fields[field]
                text = "%s [%s]: %s" % (label, _kind(odoo), help_text)
                if odoo.type == "selection":
                    options = odoo._description_selection(env)
                    text += " Opciones: %s." % ", ".join(
                        "%s (%s)" % (key, value) for key, value in options
                    )
                lines.append("    · " + text)
        filter_item = {
            "type": "object",
            "properties": {
                "campo": {"type": "string"},
                "operador": {"type": "string", "enum": list(OPERATORS)},
                "valor": {
                    "type": "string",
                    "description": "Fechas AAAA-MM-DD; «en»: separados por comas; "
                    "«vacio»: si o no.",
                },
            },
            "required": ["campo", "operador", "valor"],
        }
        return {
            "name": "consultar",
            "description": (
                "Consulta datos del ERP del catálogo: filtra, ordena y limita "
                "(como mucho %d filas), o agrupa y suma. Devuelve también el total "
                "que cumple los filtros. Para totales, recuentos o «por cliente», "
                "«por obra», «por mes», usa agrupar y sumar: no sumes tú listas. "
                "Usa solo estos nombres:\n%s" % (MAX_LIMIT, "\n".join(lines))
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "que": {"type": "string", "enum": list(catalog)},
                    "filtros": {"type": "array", "items": filter_item},
                    "campos": {"type": "array", "items": {"type": "string"}},
                    "orden": {"type": "string", "description": "Un campo."},
                    "descendente": {
                        "type": "boolean",
                        "description": "true: de mayor a menor («el que más», «los "
                        "más caros»). false: de menor a mayor («el que menos», «el "
                        "primero»). Si no lo pones: fechas de la más reciente a la más "
                        "antigua y números de menor a mayor.",
                    },
                    "limite": {"type": "integer"},
                    "agrupar": {
                        "type": "string",
                        "description": "Un campo para agrupar (fechas: «campo:mes» o "
                        "«campo:año»). Devuelve grupos con cuántos hay y las sumas.",
                    },
                    "sumar": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Campos numéricos a sumar por grupo.",
                    },
                },
                "required": ["que"],
            },
        }

    def _tool_query(
        self,
        env,
        que="",
        filtros=None,
        campos=None,
        orden="",
        descendente=None,
        limite=20,
        agrupar="",
        sumar=None,
    ):
        try:
            if agrupar or sumar:
                return self._grouped(env, que, filtros, agrupar, sumar, limite)
            return self._query(env, que, filtros, campos, orden, descendente, limite)
        except CatalogError as error:
            return {"error": str(error)}

    def _entry(self, env, que, labels):
        entry = self._catalog().get(que)
        if not entry:
            raise CatalogError("No está en el catálogo: %s." % que)
        known = entry["fields"]
        for label in labels:
            if label not in known:
                raise CatalogError(
                    "%s no tiene «%s». Campos: %s." % (que, label, ", ".join(known))
                )
        return entry, env[entry["model"]], known, self._hidden(env, known)

    @staticmethod
    def _limit(limite, top=MAX_LIMIT):
        try:
            return max(1, min(int(limite or 20), top))
        except (TypeError, ValueError):
            return min(20, top)

    def _query(self, env, que, filtros, campos, orden, descendente, limite):
        filtros = [i if isinstance(i, dict) else {} for i in filtros or []]
        # La IA a veces escribe el sentido en el propio orden: «margen desc».
        orden = str(orden or "").strip().lower()
        if orden.startswith("-"):
            orden, descendente = orden[1:], True
        for word, desc in ((" desc", True), (" asc", False)):
            if orden.lower().endswith(word):
                orden, descendente = orden[: -len(word)].strip(), desc
        wanted = list(campos or self._catalog().get(que, {}).get("fields", {}))
        used = [i.get("campo") for i in filtros] + ([orden] if orden else [])
        entry, Model, known, hidden = self._entry(
            env, que, wanted + [orden] * bool(orden)
        )
        for label in used:
            if label in hidden:
                raise CatalogError("No tienes permiso para ver %s." % label)
        domain, later = list(entry.get("domain", [])), []
        for item in filtros:
            field = Model._fields[known.get(item.get("campo"), ("id",))[0]]
            if item.get("campo") in known and not (field.store or field.search):
                later.append(self._later(Model, known, item))  # calculado
            else:
                domain.append(self._condition(env, Model, known, item))
        sort = Model._fields[known[orden][0]] if orden else None
        if sort and descendente is None:
            # Sin decirlo: fechas de la más reciente a la más antigua (como las
            # listas de Odoo); lo demás, de menor a mayor.
            descendente = _kind(sort) == "fecha"
        if sort and not _in_db(sort) and _kind(sort) not in ("numero", "fecha"):
            raise CatalogError("No se puede ordenar por %s." % orden)
        limit = self._limit(limite)
        odoo_names = [known[label][0] for label in wanted]
        if later or (sort and not _in_db(sort)):
            return self._scanned(
                env, que, entry, domain, odoo_names, later, sort, descendente, limit
            )
        order = entry.get("order")
        if sort:
            order = "%s %s, id desc" % (sort.name, "desc" if descendente else "asc")
        labels = entry.get("labels", [])
        result = self._rows(
            env, entry["model"], domain, odoo_names + labels, order, limit, MAX_LIMIT
        )
        rows = [
            self._clean(row, entry, known, wanted, hidden) for row in result["filas"]
        ]
        return {"que": que, "total": result["total"], "filas": rows}

    @staticmethod
    def _clean(row, entry, known, wanted, hidden):
        back = {known[label][0]: label for label in wanted}
        row["_link"][2] += [row.get(name) for name in entry.get("labels", [])]
        clean = {"id": row["id"], "_link": row["_link"]}
        clean.update({back[k]: v for k, v in row.items() if k in back})
        clean.update({label: "sin permiso" for label in hidden if label in wanted})
        return clean

    @staticmethod
    def _hidden(env, known):
        return {
            label
            for label, spec in known.items()
            if len(spec) > 2 and not env.user.has_group(spec[2])
        }

    def _condition(self, env, Model, known, item):
        item = item if isinstance(item, dict) else {}
        label, op = item.get("campo"), item.get("operador")
        value = str(item.get("valor", "")).strip()[:100]
        if label not in known:
            raise CatalogError("No se puede filtrar por «%s»." % label)
        field = Model._fields[known[label][0]]
        kind = _kind(field)
        if not (field.store or field.search):
            raise CatalogError("Aún no se puede filtrar por %s." % label)
        if op not in TYPE_OPS[kind]:
            raise CatalogError(
                "%s es de tipo %s: operadores %s."
                % (label, kind, ", ".join(sorted(TYPE_OPS[kind])))
            )
        name = field.name
        if op == "vacio":
            return (name, "=" if value.lower() in YES else "!=", False)
        if op == "contiene" or kind == "relacion":
            return (name, "ilike", value)
        if kind == "fecha":
            try:
                value = fields.Date.to_string(fields.Date.to_date(value))
            except (TypeError, ValueError):
                raise CatalogError("Fecha no válida: %s (AAAA-MM-DD)." % value)
        elif kind == "numero":
            value = self._number(value)
        elif kind == "si_no":
            value = value.lower() in YES
        elif kind == "opcion":
            options = field._description_selection(env)
            keys = [self._option(options, v, label) for v in value.split(",")]
            return (name, "in", keys) if op == "en" else (name, op, keys[0])
        return (name, op, value)

    @staticmethod
    def _number(value):
        text = value.replace(" ", "").replace("€", "")
        if "," in text:
            text = text.replace(".", "").replace(",", ".")
        try:
            return float(text)
        except ValueError:
            raise CatalogError("Número no válido: %s." % value)

    @staticmethod
    def _option(options, value, label):
        wanted = value.strip().lower()
        for key, text in options:
            if wanted in (str(key).lower(), str(text).lower()):
                return key
        raise CatalogError(
            "%s no admite «%s». Opciones: %s."
            % (label, value, ", ".join(str(key) for key, _text in options))
        )
