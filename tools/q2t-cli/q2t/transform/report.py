"""Element-by-element migration report with provenance.

For every element type (connections, tables, columns, joins, model, formulas,
dimensions, charts, sheets, filters, variables) it reports:

  * in_source   — how many existed in the Qlik app (per the IR)
  * migrated    — how many we produced in TML
  * provenance  — SOURCE (read from an authoritative source: engine / load
                  script / warehouse) vs INFERRED (heuristic / PDF / screenshot)
                  vs MANUAL (must be done by a human)
  * review      — how many need a human check, and why

The goal is honesty: the reader sees exactly how much converted cleanly, how
much was inferred (and should be verified), and what still needs hands-on work.
Emitted as Markdown (people) + JSON (tooling).
"""

from __future__ import annotations

import json
from typing import Any, Optional

from ..ir import QlikApp
from .to_tml import TransformResult

# Extraction mode -> base provenance of whatever it produced.
_MODE_PROV = {"engine": "SOURCE", "sqlite": "SOURCE", "offline": "INFERRED"}
_SEV_REVIEW = {"manual", "warning"}


def _prov(app: QlikApp) -> str:
    return _MODE_PROV.get(app.extraction_mode, "INFERRED")


def build(app: QlikApp, result: TransformResult,
          formula_audit: Optional[dict] = None,
          load_result: Optional[list] = None) -> tuple[str, str]:
    """Return (markdown, json)."""
    notes_by_area: dict[str, list[tuple[str, str]]] = {}
    for sev, area, msg in result.notes:
        notes_by_area.setdefault(area, []).append((sev, msg))

    def review_in(area: str) -> int:
        return sum(1 for sev, _ in notes_by_area.get(area, []) if sev in _SEV_REVIEW)

    base = _prov(app)
    files = sorted(result.documents.keys())
    has_table_tml = any(f.startswith("table.") for f in files)
    has_model = any(f.startswith(("model.", "worksheet.")) for f in files)
    has_lb = any(f.startswith("liveboard.") for f in files)

    n_tables = len(app.tables)
    n_cols = sum(len(t.columns) for t in app.tables)
    n_charts = sum(len(s.charts) for s in app.sheets)
    # Joins: the generic generator does not infer them; >1 table => a gap.
    joins_needed = max(0, n_tables - 1) if n_tables > 1 else 0

    # Formula provenance/review from the audit (translatable/manual/verify).
    fa = formula_audit or {}
    f_manual = len(fa.get("manual", [])) + len(fa.get("unknown", []))
    f_verify = len(fa.get("verify", []))

    rows: list[dict[str, Any]] = [
        _row("Connections", len(app.connections), len(app.connections),
             "SOURCE" if app.load_script else "INFERRED",
             # connection existence on the target always needs a check
             max(review_in("connection"), len(app.connections)),
             "table.*.tml", "Connection must already exist on the target cluster."),
        _row("Tables", n_tables, n_tables if has_table_tml else 0, base,
             review_in("table"), "table.*.tml"),
        _row("Columns", n_cols, n_cols if has_table_tml else 0, base,
             review_in("table"), "table.*.tml"),
        _row("Joins", joins_needed, 0, "MANUAL", joins_needed,
             "model.*.tml",
             "Generic model TML does not infer joins; define them or use engine extraction."),
        _row("Model", 1 if has_model else 0, 1 if has_model else 0, base,
             review_in("model"), "model.*.tml"),
        _row("Formulas / measures", len(app.measures),
             len(app.measures) if has_model else 0, base,
             f_manual + f_verify + review_in("measure"), "model.*.tml",
             "Translatable vs manual/verify per the formula audit."),
        _row("Dimensions", len(app.dimensions),
             len(app.dimensions) if has_model else 0, base,
             review_in("dimension"), "model.*.tml"),
        _row("Charts / vizzes", n_charts, n_charts if has_lb else 0, base,
             review_in("chart"), "liveboard.*.tml",
             "Unmapped chart types fall back to TABLE — review."),
        _row("Sheets -> tabs", len(app.sheets), len(app.sheets) if has_lb else 0,
             base, review_in("liveboard"), "liveboard.*.tml"),
        _row("Variables / parameters", len(app.variables), 0, "MANUAL",
             len(app.variables), "-",
             "Not auto-converted; recreate as Model formulas/parameters."),
        _row("Filters", 0, 0, "MANUAL", 0, "-",
             "Sheet/chart filters are not extracted by this pipeline — verify in source."),
    ]

    summary = {
        "app_name": app.app_name,
        "extraction_mode": app.extraction_mode,
        "base_provenance": base,
        "steps": _steps(app, result, load_result),
        "elements": rows,
        "formula_audit": fa,
        "totals": {
            "in_source": sum(r["in_source"] for r in rows),
            "migrated": sum(r["migrated"] for r in rows),
            "needs_review": sum(r["review"] for r in rows),
        },
        "tml_files": files,
        "action_items": [
            {"severity": s, "area": a, "message": m}
            for s, a, m in sorted(result.notes, key=lambda n: (n[0] != "manual", n[0]))
            if s in _SEV_REVIEW
        ],
    }
    return _markdown(app, summary), json.dumps(summary, indent=2, ensure_ascii=False)


def _row(element, in_source, migrated, provenance, review, files, note="") -> dict[str, Any]:
    return {"element": element, "in_source": in_source, "migrated": migrated,
            "provenance": provenance, "review": review, "files": files, "note": note}


def _steps(app: QlikApp, result: TransformResult, load_result) -> list[dict[str, Any]]:
    extract_detail = {
        "SOURCE": f"mode={app.extraction_mode} (read from authoritative source)",
        "INFERRED": f"mode={app.extraction_mode} (best-effort / PDF — verify)",
    }[_prov(app)]
    steps = [
        {"step": "Extract", "status": "done", "detail": extract_detail},
        {"step": "Transform", "status": "done",
         "detail": f"{len(result.documents)} TML document(s) generated"},
    ]
    if load_result is None:
        steps.append({"step": "Load", "status": "skipped",
                      "detail": "not run (use `q2t load` / validate-only first)"})
    else:
        ok = sum(1 for r in load_result if str(r).find("OK") != -1)
        steps.append({"step": "Load", "status": "done",
                      "detail": f"{ok}/{len(load_result)} objects OK"})
    return steps


def _markdown(app: QlikApp, s: dict[str, Any]) -> str:
    L = [
        f"# Migration report — {app.app_name}",
        "",
        f"- Extraction mode: **{app.extraction_mode}**  ·  base provenance: **{s['base_provenance']}**",
        f"- Source: `{app.source_file or 'n/a'}`",
        "",
        "## Pipeline steps",
        "",
        "| Step | Status | Detail |",
        "|------|--------|--------|",
    ]
    for st in s["steps"]:
        L.append(f"| {st['step']} | {st['status']} | {st['detail']} |")

    L += [
        "",
        "## Element coverage",
        "",
        "| Element | In source | Migrated | Provenance | Needs review | File |",
        "|---------|----------:|---------:|------------|-------------:|------|",
    ]
    for r in s["elements"]:
        L.append(f"| {r['element']} | {r['in_source']} | {r['migrated']} | "
                 f"{r['provenance']} | {r['review']} | `{r['files']}` |")
    t = s["totals"]
    L.append(f"| **Total** | **{t['in_source']}** | **{t['migrated']}** | | "
             f"**{t['needs_review']}** | |")

    L += [
        "",
        "### Provenance legend",
        "- **SOURCE** — read from an authoritative source (Qlik engine / load script / warehouse introspection). Trust it.",
        "- **INFERRED** — derived heuristically or from a PDF/screenshot. **Verify against the source app.**",
        "- **MANUAL** — not auto-migrated; needs hands-on work.",
        "",
    ]

    fa = s.get("formula_audit") or {}
    if fa:
        L += [
            "## Formula coverage (audit)",
            "",
            f"- Coverage: **{fa.get('coverage_pct', 0)}%** translatable "
            f"({len(fa.get('translatable', []))}/{fa.get('distinct_functions', 0)} functions)",
            f"- 🟡 Manual: {fa.get('manual', [])}",
            f"- ❓ Verify: {fa.get('verify', [])}",
            f"- ✗ Unknown: {fa.get('unknown', [])}",
            "",
        ]

    items = s["action_items"]
    L += ["## Human review checklist", ""]
    if not items:
        L.append("- _Nothing flagged._")
    else:
        for it in items:
            tag = "🔴" if it["severity"] == "manual" else "🟡"
            msg = it["message"].replace("\n", " ")
            L.append(f"- {tag} **[{it['area']}]** {msg}")
    L.append("")
    return "\n".join(L)
