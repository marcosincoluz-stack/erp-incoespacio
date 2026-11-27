import operator
from datetime import date

from odoo import fields, models

from .question import CatalogError, _in_db, _kind

MAX_GROUPS = 30
# Para ordenar o filtrar por un campo calculado (p. ej. el margen) se leen
# los registros y se compara aquí: como mucho estos (o el «scan» de la entrada).
SCAN = 200
COMPARE = {
    "=": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
}
PERIODS = {"mes": "month", "año": "year", "ano": "year", "dia": "day", "día": "day"}


class AssistantAIQuestion(models.Model):
    _inherit = "assistant.ai.question"

    # ------------------------------------------------------------------ #
    # Campos calculados: se leen hasta SCAN registros y se compara aquí
    # ------------------------------------------------------------------ #
    def _later(self, Model, known, item):
        label, op = item.get("campo"), item.get("operador")
        field = Model._fields[known[label][0]]
        if _kind(field) not in ("numero", "fecha") or op not in COMPARE:
            raise CatalogError("Aún no se puede filtrar así por %s." % label)
        if _kind(field) == "numero":
            value = self._number(str(item.get("valor", "")).strip()[:100])
        else:
            value = fields.Date.to_date(
                self._condition(self.env, Model, known, item)[2]
            )
        return field.name, COMPARE[op], value

    def _scanned(self, env, que, entry, domain, names, later, sort, desc, limit):
        Model = env[entry["model"]]
        Model.check_access_rights("read")
        total, scan = Model.search_count(domain), entry.get("scan", SCAN)
        if total > scan:
            raise CatalogError(
                "Hay %d %s; para comparar por un dato calculado filtra hasta %d o "
                "menos (por fecha, estado, cliente…)." % (total, que, scan)
            )
        extra = [name for name, _op, _value in later] + ([sort.name] if sort else [])
        labels = entry.get("labels", [])
        result = self._rows(
            env,
            entry["model"],
            domain,
            names + extra + labels,
            entry.get("order"),
            scan,
            scan,
        )
        rows = [
            row
            for row in result["filas"]
            if all(self._holds(row.get(name), op, value) for name, op, value in later)
        ]
        if sort:
            rows.sort(key=lambda row: self._key(row.get(sort.name)), reverse=desc)
        known = entry["fields"]
        wanted = [label for label in known if known[label][0] in names]
        hidden = self._hidden(env, known)
        filas = [self._clean(r, entry, known, wanted, hidden) for r in rows[:limit]]
        return {"que": que, "total": len(rows), "filas": filas}

    @staticmethod
    def _comparable(value):
        if isinstance(value, bool) or not isinstance(value, (int, float, date)):
            return None
        return value.toordinal() if isinstance(value, date) else value

    def _holds(self, value, op, wanted):
        value = self._comparable(value)
        return value is not None and op(value, self._comparable(wanted))

    def _key(self, value):
        # Lo que no es número ni fecha (vacío, «sin permiso») va al final.
        value = self._comparable(value)
        return (0, 0) if value is None else (1, value)

    # ------------------------------------------------------------------ #
    # Agrupar y sumar (read_group, como el usuario: sus permisos y reglas)
    # ------------------------------------------------------------------ #
    def _grouped(self, env, que, filtros, agrupar, sumar, limite):
        label, _sep, period = str(agrupar or "").partition(":")
        sums = list(sumar or [])
        entry, Model, known, hidden = self._entry(
            env, que, [label] * bool(label) + sums
        )
        filtros = [i if isinstance(i, dict) else {} for i in filtros or []]
        for name in [label] + sums + [i.get("campo") for i in filtros]:
            if name in hidden:
                raise CatalogError("No tienes permiso para ver %s." % name)
        if not label:
            return self._totals(env, que, entry, Model, known, filtros, sums)
        field = Model._fields[known[label][0]]
        groupable = ("texto", "fecha", "si_no", "opcion", "relacion")
        if not _in_db(field) or _kind(field) not in groupable:
            raise CatalogError("No se puede agrupar por %s." % label)
        groupby = field.name
        if _kind(field) == "fecha":
            groupby += ":" + PERIODS.get(period.strip().lower() or "mes", "month")
        fields_, domain = self._sums_and_domain(env, Model, known, entry, filtros, sums)
        groups = Model.read_group(domain, fields_, [groupby], lazy=False)
        first = fields_[0].split(":")[0] if fields_ else "__count"
        groups.sort(key=lambda g: g.get(first) or 0, reverse=True)
        options = (
            dict(field._description_selection(env)) if field.type == "selection" else {}
        )
        out = []
        for group in groups[: self._limit(limite, MAX_GROUPS)]:
            value = group.get(groupby)
            if isinstance(value, tuple):
                value = value[1]
            elif field.type == "selection":
                value = options.get(value, value)
            elif field.type == "boolean":
                value = "sí" if value else "no"
            row = {label: value if value not in (False, None) else "(sin %s)" % label}
            row["cantidad"] = group.get("__count", 0)
            for name in sums:
                row[name] = group.get(known[name][0]) or 0
            out.append(row)
        return {
            "que": que,
            "agrupado_por": agrupar,
            "total": sum(g.get("__count", 0) for g in groups),
            "total_grupos": len(groups),
            "grupos": out,
        }

    def _sums_and_domain(self, env, Model, known, entry, filtros, sums):
        fields_ = []
        for name in sums:
            target = Model._fields[known[name][0]]
            if _kind(target) != "numero":
                raise CatalogError("No se puede sumar %s: no es un número." % name)
            if not _in_db(target):
                # El error le dice a la IA cómo hacerlo, para que no se pierda.
                raise CatalogError(
                    "%s es un dato calculado y no se puede sumar ni agrupar. Para "
                    "«el que más %s», usa orden=%s y descendente=true, sin agrupar "
                    "ni sumar." % (name, name, name)
                )
            fields_.append("%s:sum" % target.name)
        domain = list(entry.get("domain", []))
        for item in filtros:
            target = Model._fields[known.get(item.get("campo"), ("id",))[0]]
            if item.get("campo") in known and not (target.store or target.search):
                raise CatalogError(
                    "Al sumar no se puede filtrar por %s." % item["campo"]
                )
            domain.append(self._condition(env, Model, known, item))
        return fields_, domain

    def _totals(self, env, que, entry, Model, known, filtros, sums):
        # «Sumar» sin «agrupar»: cuántos hay y cuánto suman, todo junto.
        fields_, domain = self._sums_and_domain(env, Model, known, entry, filtros, sums)
        group = (Model.read_group(domain, fields_, [], lazy=False) or [{}])[0]
        totals = {name: group.get(known[name][0]) or 0 for name in sums}
        return {"que": que, "total": group.get("__count", 0), "sumas": totals}
