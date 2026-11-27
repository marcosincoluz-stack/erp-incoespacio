from odoo import models

from odoo.addons.incoespacio_assistant_ai_catalog.models.question import (
    CatalogError,
    _in_db,
    _kind,
)
from odoo.addons.incoespacio_assistant_ai_catalog.models.question_more import (
    MAX_GROUPS,
    SCAN,
)

# Va aparte de incoespacio_assistant_ai_catalog, que está en el tope de líneas.
#
# Dos cosas para entradas grandes como las partidas de obra:
# - «requires»: la entrada pide filtrar por alguno de estos campos (p. ej. la
#   obra), para no leer miles de líneas.
# - Agrupar y sumar datos calculados (coste, margen, desviación): se leen los
#   registros (hasta el «scan» de la entrada) y se suma aquí.


class AssistantAIQuestion(models.Model):
    _inherit = "assistant.ai.question"

    def _tool_query(self, env, que="", filtros=None, agrupar="", sumar=None, **kw):
        try:
            self._check_required(que, filtros)
            if self._needs_calc(env, que, agrupar, sumar, filtros):
                return self._grouped_calc(
                    env, que, filtros, agrupar, sumar, kw.get("limite", 20)
                )
        except CatalogError as error:
            return {"error": str(error)}
        return super()._tool_query(
            env, que=que, filtros=filtros, agrupar=agrupar, sumar=sumar, **kw
        )

    # Filtrar por un texto calculado (p. ej. el capítulo de una partida): se lee
    # y se compara aquí, sin distinguir mayúsculas ni acentos de más.
    def _later(self, Model, known, item):
        label, op = item.get("campo"), item.get("operador")
        field = Model._fields[known.get(label, ("id",))[0]]
        if _kind(field) == "texto" and op in ("=", "contiene"):
            wanted = str(item.get("valor", "")).strip().lower()[:100]
            return field.name, ("texto", op), wanted
        return super()._later(Model, known, item)

    def _holds(self, value, op, wanted):
        if isinstance(op, tuple):
            text = str(value or "").strip().lower()
            return text == wanted if op[1] == "=" else wanted in text
        return super()._holds(value, op, wanted)

    def _check_required(self, que, filtros):
        needed = self._catalog().get(que, {}).get("requires")
        if not needed:
            return
        used = {i.get("campo") for i in filtros or [] if isinstance(i, dict)}
        if not used & set(needed):
            raise CatalogError(
                "Para consultar %s filtra por %s." % (que, " o ".join(needed))
            )

    def _needs_calc(self, env, que, agrupar, sumar, filtros=None):
        entry = self._catalog().get(que)
        if not entry or not (agrupar or sumar):
            return False
        Model, known = env[entry["model"]], entry["fields"]
        label = str(agrupar or "").partition(":")[0]
        names = [n for n in [label] + list(sumar or []) if n in known]
        if any(not _in_db(Model._fields[known[n][0]]) for n in names):
            return True
        # Un filtro por un dato calculado que no se puede buscar en la base.
        used = [i.get("campo") for i in filtros or [] if isinstance(i, dict)]
        fields_ = [Model._fields[known[n][0]] for n in used if n in known]
        return any(not (f.store or f.search) for f in fields_)

    def _grouped_calc(self, env, que, filtros, agrupar, sumar, limite):
        label = str(agrupar or "").partition(":")[0]
        sums = list(sumar or [])
        entry, Model, known, hidden = self._entry(
            env, que, [label] * bool(label) + sums
        )
        filtros = [i if isinstance(i, dict) else {} for i in filtros or []]
        for name in [label] + sums + [i.get("campo") for i in filtros]:
            if name in hidden:
                raise CatalogError("No tienes permiso para ver %s." % name)
        for name in sums:
            if _kind(Model._fields[known[name][0]]) != "numero":
                raise CatalogError("No se puede sumar %s: no es un número." % name)
        domain, later = list(entry.get("domain", [])), []
        for item in filtros:
            field = Model._fields[known.get(item.get("campo"), ("id",))[0]]
            if item.get("campo") in known and not (field.store or field.search):
                later.append(self._later(Model, known, item))
            else:
                domain.append(self._condition(env, Model, known, item))
        Model.check_access_rights("read")
        scan = entry.get("scan", SCAN)
        total = Model.search_count(domain)
        if total > scan:
            raise CatalogError(
                "Hay %d %s; para sumar datos calculados filtra hasta %d o menos."
                % (total, que, scan)
            )
        group_field = known[label][0] if label else None
        names = [known[n][0] for n in sums] + [n for n, _o, _v in later]
        rows = self._rows(
            env,
            entry["model"],
            domain,
            names + [group_field] * bool(label),
            entry.get("order"),
            scan,
            scan,
        )["filas"]
        rows = [
            r for r in rows if all(self._holds(r.get(n), o, v) for n, o, v in later)
        ]
        groups = {}
        for row in rows:
            key = row.get(group_field) if label else None
            group = groups.setdefault(
                key,
                dict.fromkeys(
                    sums,
                    0.0,
                )
                | {"cantidad": 0},
            )
            group["cantidad"] += 1
            for name in sums:
                value = row.get(known[name][0])
                group[name] += value if isinstance(value, (int, float)) else 0.0
        if not label:
            totals = groups.get(None, dict.fromkeys(sums, 0.0))
            return {
                "que": que,
                "total": len(rows),
                "sumas": {n: totals.get(n, 0.0) for n in sums},
            }
        first = sums[0] if sums else "cantidad"
        ordered = sorted(groups.items(), key=lambda kv: kv[1][first], reverse=True)
        out = [
            {
                label: key if key not in (False, None, "") else "(sin %s)" % label,
                **values,
            }
            for key, values in ordered[: self._limit(limite, MAX_GROUPS)]
        ]
        return {
            "que": que,
            "agrupado_por": agrupar,
            "total": len(rows),
            "total_grupos": len(groups),
            "grupos": out,
        }
