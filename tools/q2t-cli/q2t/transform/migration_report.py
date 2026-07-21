"""Post-migration report — what got built, and what needs a human.

Reads the generated TML directory (table / model / liveboard docs), enumerates
every migrated object (connections, tables, columns, joins, formulas, model,
liveboard vizzes, filters, geo/maps), and produces:

  * an object inventory (what migrated), and
  * a human-review checklist (what to confirm / where intervention is needed).

Provenance drives the flags: `SOURCE` (extracted via engine/API — trust it) vs
`INFERRED` (read from a PDF — verify). Optionally overlays per-object import
status so failures show up as must-fix items.
"""

from __future__ import annotations

import glob
import json
import os
from collections import Counter
from typing import Any, Optional

import yaml

# Chart types that are a fallback/approximation and usually warrant a look.
_FALLBACK_CHARTS = {"TABLE", "PIVOT_TABLE", "KPI"}
_GEO_PREFIX = "GEO"


def _load(tml_dir: str) -> list[tuple[str, dict]]:
    out = []
    for path in sorted(glob.glob(os.path.join(tml_dir, "*.tml"))):
        try:
            with open(path, encoding="utf-8") as fh:
                doc = yaml.safe_load(fh)
            if isinstance(doc, dict):
                out.append((os.path.basename(path), doc))
        except (OSError, yaml.YAMLError):
            pass
    return out


def build(tml_dir: str, *, provenance: str = "INFERRED",
          app_name: Optional[str] = None, target: Optional[str] = None,
          import_status: Optional[dict] = None) -> tuple[str, str]:
    """Return (markdown, json). `import_status` maps object name -> status str."""
    docs = _load(tml_dir)
    prov = provenance.upper()
    inferred = prov != "SOURCE"
    status = {k.lower(): v for k, v in (import_status or {}).items()}

    connections: set[str] = set()
    tables: list[dict] = []
    model: Optional[dict] = None
    joins = 0
    measures: list[dict] = []   # every measure: formula-based AND aggregation-based
    geo_columns: list[str] = []
    liveboards: list[dict] = []

    for fname, doc in docs:
        if "table" in doc:
            t = doc["table"]
            connections.add((t.get("connection") or {}).get("name", ""))
            tables.append({"name": t.get("name"), "columns": len(t.get("columns", [])),
                           "db": t.get("db"), "schema": t.get("schema")})
        elif "model" in doc or "worksheet" in doc:
            m = doc.get("model") or doc.get("worksheet")
            model = {"name": m.get("name"), "tables": len(m.get("model_tables") or m.get("tables") or [])}
            for mt in (m.get("model_tables") or []):
                joins += len(mt.get("joins", []) or [])
            # A measure is any column that computes/aggregates a value: either a
            # formula (formula_id) or an aggregation column (column_type MEASURE).
            # ALL of them are Qlik expressions worth confirming.
            formula_expr = {f.get("id"): f.get("expr", "") for f in (m.get("formulas") or [])}
            surfaced_formula_ids = set()
            for c in (m.get("columns") or []):
                props = c.get("properties") or {}
                if props.get("geo_config"):
                    geo_columns.append(c.get("name"))
                if c.get("formula_id"):
                    surfaced_formula_ids.add(c["formula_id"])
                    measures.append({"name": c.get("name"), "kind": "formula",
                                     "definition": formula_expr.get(c["formula_id"], "(formula)")})
                elif props.get("column_type") == "MEASURE":
                    agg = (props.get("aggregation") or "").lower()
                    cid = c.get("column_id", "")
                    measures.append({"name": c.get("name"), "kind": "aggregation",
                                     "definition": f"{agg}({cid})" if agg else cid})
            # formulas defined but not surfaced as a named column
            for f in (m.get("formulas") or []):
                if f.get("id") not in surfaced_formula_ids:
                    measures.append({"name": f.get("name"), "kind": "formula",
                                     "definition": f.get("expr", "")})
        elif "liveboard" in doc:
            lb = doc["liveboard"]
            vizzes = lb.get("visualizations", []) or []
            types = Counter((v.get("answer") or {}).get("chart", {}).get("type", "?") for v in vizzes)
            filters = [(_first(f.get("column")) if isinstance(f.get("column"), list) else f.get("column"))
                       for f in (lb.get("filters") or [])]
            liveboards.append({"name": lb.get("name"), "vizzes": len(vizzes),
                               "types": dict(types), "filters": [f for f in filters if f],
                               "geo_vizzes": [((v.get("answer") or {}).get("name"))
                                              for v in vizzes
                                              if str((v.get("answer") or {}).get("chart", {}).get("type", "")).startswith(_GEO_PREFIX)]})

    def st(name: Optional[str]) -> str:
        return status.get((name or "").lower(), "")

    # ---- build review checklist -----------------------------------------
    review: list[tuple[str, str, str]] = []  # (severity, area, message)

    for c in sorted(x for x in connections if x):
        review.append(("review", "connection",
                       f"Confirm connection '{c}' exists on the cluster and points to the right warehouse."))
    if joins:
        review.append(("review", "joins",
                       f"Verify the {joins} model join(s) — join keys and cardinality "
                       f"({'inferred' if inferred else 'from source'})."))
    for meas in measures:
        review.append(("review", "measure",
                       f"Confirm measure '{meas['name']}' = {meas['definition']}  — matches the Qlik expression."))
    if geo_columns:
        review.append(("review", "geo",
                       f"Geo/map column(s) {geo_columns} need country/region geo-config — verify the map renders."))
    for lb in liveboards:
        if inferred:
            review.append(("review", "charts",
                           f"Verify each of the {lb['vizzes']} viz(es) in '{lb['name']}' against the "
                           f"source dashboard — charts were inferred from the PDF."))
        fallback = {t: n for t, n in lb["types"].items() if t in _FALLBACK_CHARTS}
        if fallback:
            review.append(("review", "charts",
                           f"Chart types that may be fallbacks in '{lb['name']}': {fallback} — confirm intended."))
        if lb["filters"]:
            review.append(("review", "filters",
                           f"Verify filters {lb['filters']} match the source (columns + default selections)."))
    # import failures -> must-fix
    for fname, doc in docs:
        obj = (doc.get("table") or doc.get("model") or doc.get("worksheet") or doc.get("liveboard") or {})
        s = st(obj.get("name"))
        if s and s.upper() not in ("OK", "SUCCESS"):
            review.append(("manual", "import", f"Import FAILED for '{obj.get('name')}': {s}"))

    summary = {
        "app_name": app_name or (model or {}).get("name") or (liveboards[0]["name"] if liveboards else "migration"),
        "target": target,
        "provenance": prov,
        "counts": {
            "connections": len([c for c in connections if c]),
            "tables": len(tables),
            "columns": sum(t["columns"] for t in tables),
            "joins": joins,
            "measures": len(measures),
            "liveboards": len(liveboards),
            "vizzes": sum(lb["vizzes"] for lb in liveboards),
            "filters": sum(len(lb["filters"]) for lb in liveboards),
        },
        "connections": sorted(c for c in connections if c),
        "tables": tables,
        "model": model,
        "measures": measures,
        "liveboards": liveboards,
        "review": [{"severity": s, "area": a, "message": m} for s, a, m in review],
    }
    return _markdown(summary), json.dumps(summary, indent=2, ensure_ascii=False)


def _first(x):
    return x[0] if isinstance(x, list) and x else x


def _markdown(s: dict[str, Any]) -> str:
    c = s["counts"]
    L = [f"# Migration report — {s['app_name']}", ""]
    if s.get("target"):
        L.append(f"- Target: {s['target']}")
    L += [f"- Extraction provenance: **{s['provenance']}** "
          f"({'read from engine/API — trustworthy' if s['provenance']=='SOURCE' else 'inferred from PDF — verify'})",
          "",
          "## What was migrated", "",
          "| Object | Count |", "|--------|------:|",
          f"| Connections | {c['connections']} |",
          f"| Tables | {c['tables']} |",
          f"| Columns | {c['columns']} |",
          f"| Model joins | {c['joins']} |",
          f"| Measures (formulas + aggregations) | {c['measures']} |",
          f"| Liveboards | {c['liveboards']} |",
          f"| Visualizations | {c['vizzes']} |",
          f"| Filters | {c['filters']} |",
          ""]

    if s["tables"]:
        L += ["### Tables", "", "| Table | Columns | Location |", "|-------|--------:|----------|"]
        for t in s["tables"]:
            L.append(f"| {t['name']} | {t['columns']} | {t.get('db')}.{t.get('schema')} |")
        L.append("")
    if s["model"]:
        m = s["model"]
        L += ["### Model", "",
              f"- **{m['name']}** — {m['tables']} tables, {c['joins']} joins, "
              f"{c['measures']} measure(s)", ""]
    if s["measures"]:
        L += ["### Measures (each should be confirmed against its Qlik expression)", ""]
        L += [f"- `{meas['name']}` = `{meas['definition']}`  _({meas['kind']})_" for meas in s["measures"]]
        L.append("")
    for lb in s["liveboards"]:
        L += [f"### Liveboard — {lb['name']}", "",
              f"- {lb['vizzes']} viz(es): {lb['types']}",
              f"- Filters: {lb['filters'] or '(none)'}",
              (f"- Map viz(es): {lb['geo_vizzes']}" if lb.get("geo_vizzes") else ""), ""]

    # the headline section the user asked for
    review = s["review"]
    manual = [r for r in review if r["severity"] == "manual"]
    L += ["## ⚠️ Needs confirmation / human intervention", ""]
    if not review:
        L.append("- _Nothing flagged._")
    else:
        if manual:
            L.append("**Must fix:**")
            L += [f"- 🔴 **[{r['area']}]** {r['message']}" for r in manual]
            L.append("")
        L.append("**Confirm / verify:**")
        L += [f"- 🟡 **[{r['area']}]** {r['message']}"
              for r in review if r["severity"] != "manual"]
    L += ["",
          "## Provenance legend",
          "- **SOURCE** — read from the Qlik engine/API; trust it.",
          "- **INFERRED** — derived from the dashboard PDF; verify against the source.",
          ""]
    return "\n".join([x for x in L if x is not None])
