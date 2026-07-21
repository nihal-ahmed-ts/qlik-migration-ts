"""Transform the IR into ThoughtSpot TML documents.

Produces, for one Qlik app:
  * one Table TML per IR table        (table:)
  * one Model TML for the app          (model:)   -- modern, 10.12+
  * one Liveboard TML                  (liveboard:) -- one tab per Qlik sheet

Worksheets are deprecated in favour of Models, so we emit Models by default;
pass model_kind="worksheet" if your cluster predates 10.12.

Anything that cannot be mapped faithfully is NOT guessed — it is recorded via
the returned TransformResult.notes and surfaced in the mapping report.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import yaml

from ..ir import Chart, MasterMeasure, QlikApp, Table
from . import expr as expr_translator

# Qlik field/expr type hints -> ThoughtSpot db_column_properties.data_type.
_TYPE_MAP = {
    "integer": "INT64", "int": "INT64", "num": "DOUBLE", "number": "DOUBLE",
    "double": "DOUBLE", "real": "DOUBLE", "money": "DOUBLE",
    "text": "VARCHAR", "string": "VARCHAR", "ascii": "VARCHAR",
    "date": "DATE", "timestamp": "DATE_TIME", "time": "TIME",
    "bool": "BOOL", "boolean": "BOOL",
}

# Qlik viz object type -> ThoughtSpot chart type.
_CHART_MAP = {
    "barchart": "COLUMN", "bar": "BAR",
    "linechart": "LINE", "line": "LINE",
    "combochart": "COLUMN",
    "piechart": "PIE", "pie": "PIE",
    "kpi": "KPI",
    "gauge": "KPI",
    "scatterplot": "SCATTER",
    "table": "TABLE", "pivot-table": "PIVOT_TABLE", "sn-table": "TABLE",
    "treemap": "TREEMAP",
    "map": "GEO_AREA",
    "histogram": "COLUMN",
}


@dataclass
class TransformResult:
    documents: dict[str, str] = field(default_factory=dict)   # filename -> yaml
    notes: list[tuple[str, str, str]] = field(default_factory=list)  # (severity, area, msg)

    def note(self, severity: str, area: str, msg: str) -> None:
        self.notes.append((severity, area, msg))


def transform(app: QlikApp, *, model_kind: str = "model",
              type_overrides: dict | None = None) -> TransformResult:
    res = TransformResult()
    # Carry forward extraction notes so the report is the single place to look.
    for n in app.notes:
        res.note(n.severity, n.area, n.message)

    table_names: list[str] = []
    for tbl in app.tables:
        doc = _table_tml(tbl, app, res, type_overrides)
        res.documents[f"table.{_slug(tbl.name)}.tml"] = _dump(doc)
        table_names.append(tbl.name)

    if not table_names:
        res.note("manual", "model",
                 "No tables in IR; cannot build a Model. Recover tables via "
                 "--mode engine or add them to the IR by hand.")
    else:
        model_doc = (_model_tml if model_kind == "model" else _worksheet_tml)(
            app, table_names, res)
        res.documents[f"{'model' if model_kind=='model' else 'worksheet'}."
                      f"{_slug(app.app_name)}.tml"] = _dump(model_doc)

    if app.sheets:
        lb = _liveboard_tml(app, res)
        res.documents[f"liveboard.{_slug(app.app_name)}.tml"] = _dump(lb)

    return res


# -- tables ----------------------------------------------------------------

def _table_tml(tbl: Table, app: QlikApp, res: TransformResult,
               type_overrides: dict | None = None) -> dict[str, Any]:
    from . import wh_types
    conn_name = tbl.source_connection or (app.connections[0].name if app.connections else None)
    if not conn_name:
        res.note("manual", "table",
                 f"Table '{tbl.name}' has no source connection; set "
                 f"connection.name in the TML before import.")
    db_table = tbl.name
    columns = []
    for col in tbl.columns:
        # Prefer the real warehouse type (introspected) over inferring from Qlik.
        ts_type = wh_types.lookup(type_overrides, db_table, col.name) or _map_type(col.data_type)
        columns.append({
            "name": col.name,
            "db_column_name": col.name,
            "properties": {"column_type": "ATTRIBUTE"},
            "db_column_properties": {"data_type": ts_type},
        })
    if not columns:
        res.note("warning", "table", f"Table '{tbl.name}' has no columns recovered.")
    table: dict[str, Any] = {
        "name": tbl.name,
        "db": tbl.db_name or "DATABASE",
        "schema": tbl.schema_name or "PUBLIC",
        "db_table": tbl.name,
        "connection": {"name": conn_name or "CONNECTION"},
        "columns": columns,
    }
    return {"table": table}


# -- model (modern) --------------------------------------------------------

def _model_tml(app: QlikApp, table_names: list[str], res: TransformResult) -> dict[str, Any]:
    model: dict[str, Any] = {
        "name": app.app_name,
        "model_tables": [{"name": n} for n in table_names],
    }
    formulas = _measure_formulas(app.measures, res)
    if formulas:
        model["formulas"] = formulas
    cols = _model_columns(app, formulas, res)
    if cols:
        model["columns"] = cols
    if app.variables:
        res.note("manual", "variable",
                 f"{len(app.variables)} Qlik variable(s) not auto-mapped; "
                 f"recreate as Model formulas or parameters if needed.")
    return {"model": model}


def _worksheet_tml(app: QlikApp, table_names: list[str], res: TransformResult) -> dict[str, Any]:
    ws: dict[str, Any] = {
        "name": app.app_name,
        "tables": [{"name": n} for n in table_names],
        "table_paths": [{"id": n, "table": n, "join_path": [{"join": []}]}
                        for n in table_names],
    }
    formulas = _measure_formulas(app.measures, res)
    if formulas:
        ws["formulas"] = formulas
    return {"worksheet": ws}


def _measure_formulas(measures: list[MasterMeasure], res: TransformResult) -> list[dict[str, Any]]:
    formulas = []
    for m in measures:
        ts_expr, review, reason = expr_translator.translate(m.expression)
        if review:
            res.note("manual", "measure",
                     f"Measure '{m.label}': {reason} "
                     f"(Qlik: '{m.expression}' -> '{ts_expr}'). Review formula.")
        formulas.append({"name": m.label or m.id, "expr": ts_expr})
    return formulas


def _model_columns(app: QlikApp, formulas: list[dict[str, Any]],
                   res: TransformResult) -> list[dict[str, Any]]:
    cols: list[dict[str, Any]] = []
    # ThoughtSpot requires column display names to be unique within a model.
    # The same field loaded from two tables (e.g. a shared join key) collides,
    # so we qualify the duplicate with its table name rather than drop it.
    seen: set[str] = set()

    def unique(name: str, table: str) -> str:
        if name not in seen:
            seen.add(name)
            return name
        qualified = f"{name} ({table})"
        i = 2
        while qualified in seen:
            qualified = f"{name} ({table} {i})"
            i += 1
        seen.add(qualified)
        res.note("warning", "model",
                 f"Duplicate column '{name}' renamed to '{qualified}' to keep "
                 f"model column names unique.")
        return qualified

    # Expose raw table columns as attributes (column_id = table::column).
    for tbl in app.tables:
        for col in tbl.columns:
            cols.append({
                "name": unique(col.name, tbl.name),
                "column_id": f"{tbl.name}::{col.name}",
                "properties": {"column_type": "ATTRIBUTE"},
            })
    # Expose measure formulas as measures.
    for f in formulas:
        cols.append({
            "name": unique(f["name"], "formula"),
            "column_id": f["name"],
            "properties": {"column_type": "MEASURE", "aggregation": "SUM"},
        })
    return cols


# -- liveboard -------------------------------------------------------------

def _liveboard_tml(app: QlikApp, res: TransformResult) -> dict[str, Any]:
    viz_list: list[dict[str, Any]] = []
    tab_layout: list[dict[str, Any]] = []
    counter = 0
    for sheet in app.sheets:
        tab_viz_ids: list[str] = []
        for chart in sheet.charts:
            counter += 1
            vid = f"Viz_{counter}"
            viz_list.append(_viz_tml(vid, chart, app, res))
            tab_viz_ids.append(vid)
        tab_layout.append({"name": sheet.title or sheet.id,
                           "visualization_ids": tab_viz_ids})
    lb: dict[str, Any] = {
        "name": app.app_name,
        "visualizations": viz_list,
    }
    if tab_layout:
        lb["layout"] = {"tabs": tab_layout}
    res.note("warning", "liveboard",
             "Liveboard vizzes are generated from chart dimensions/measures as "
             "natural-language search queries. Review each viz — Qlik set "
             "analysis, alternate dimensions, and complex expressions are not "
             "translated.")
    return {"liveboard": lb}


def _viz_tml(vid: str, chart: Chart, app: QlikApp, res: TransformResult) -> dict[str, Any]:
    chart_type = _CHART_MAP.get(chart.viz_type.lower())
    if chart_type is None:
        chart_type = "TABLE"
        res.note("manual", "chart",
                 f"Chart '{chart.title or chart.id}' type '{chart.viz_type}' "
                 f"has no ThoughtSpot equivalent; defaulted to TABLE.")
    # Build a search query from the chart's dimensions + measures.
    tokens = [f"[{d}]" for d in chart.dimensions] + [f"[{m}]" for m in chart.measures]
    search_query = " ".join(tokens)
    answer: dict[str, Any] = {
        "name": chart.title or chart.id,
        "tables": [{"name": app.app_name}],   # the model/worksheet
        "search_query": search_query or "[]",
        "chart": {"type": chart_type},
        "display_mode": "CHART_MODE" if chart_type != "TABLE" else "TABLE_MODE",
    }
    return {"id": vid, "answer": answer}


# -- helpers ---------------------------------------------------------------

def _map_type(qlik_type: str) -> str:
    return _TYPE_MAP.get((qlik_type or "").lower(), "VARCHAR")


def _slug(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", name).strip("_") or "obj"


def _dump(doc: dict[str, Any]) -> str:
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, default_flow_style=False)
