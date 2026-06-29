"""SQLite-based extraction from a .qvf file.

Per the proposed architecture, a .qvf MAY be a SQLite 3 database with a renamed
extension, holding the app layout/script as JSON in named tables. THIS IS NOT
CONFIRMED across Qlik versions — so this reader is defensive:

  * `looks_like_sqlite()` checks the 16-byte magic header before doing anything.
  * extraction probes several known table/column shapes and gracefully reports
    what it could not find rather than throwing.

When the layout JSON is present it gives a clean, reliable parse (qMeasureList,
qDimensionList, qVariableList, qAppObjectList) — far better than byte-scraping.
The pipeline tries this first and falls back to qvf_offline when the file is
not SQLite or the layout cannot be located.
"""

from __future__ import annotations

import gzip
import json
import sqlite3
from typing import Any, Optional

from ..ir import (
    Chart, Column, MasterDimension, MasterMeasure, QlikApp, Sheet, Table, Variable,
)

_SQLITE_MAGIC = b"SQLite format 3\x00"

# Candidate (query, kind) pairs for locating the layout JSON. Different Qlik
# versions name things differently, so we try several and use the first hit.
_LAYOUT_QUERIES = [
    "SELECT value FROM Layout WHERE key='AppProperties'",
    "SELECT value FROM Layout LIMIT 1",
    "SELECT value FROM AppEntry WHERE key='Layout'",
    "SELECT data FROM Layout LIMIT 1",
]
_SCRIPT_QUERIES = [
    "SELECT value FROM Script LIMIT 1",
    "SELECT script FROM Script LIMIT 1",
    "SELECT value FROM Layout WHERE key='Script'",
]


def looks_like_sqlite(qvf_path: str) -> bool:
    try:
        with open(qvf_path, "rb") as fh:
            return fh.read(16) == _SQLITE_MAGIC
    except OSError:
        return False


def extract(qvf_path: str) -> Optional[QlikApp]:
    """Return a populated QlikApp, or None if this isn't a usable SQLite .qvf."""
    if not looks_like_sqlite(qvf_path):
        return None

    app_name = qvf_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    app = QlikApp(app_name=app_name, source_file=qvf_path, extraction_mode="sqlite")

    try:
        conn = sqlite3.connect(qvf_path)
    except sqlite3.Error as e:
        app.note("warning", "general", f"File has SQLite header but failed to open: {e}")
        return None

    try:
        tables = _list_tables(conn)
        app.note("info", "general", f"SQLite tables present: {', '.join(tables) or '(none)'}")

        layout = _first_json(conn, _LAYOUT_QUERIES)
        if layout is None:
            app.note("manual", "general",
                     "SQLite .qvf opened but no recognizable Layout JSON found; "
                     "falling back to offline byte-scan.")
            return None

        script = _first_text(conn, _SCRIPT_QUERIES)
        if script:
            app.load_script = script
            # The layout JSON has master items + charts; connections and tables
            # live in the load script. Reuse the offline script parsers so the
            # SQLite path is complete rather than missing the data layer.
            from . import qvf_offline
            qvf_offline._parse_connections_from_script(script, app)
            qvf_offline._parse_tables_from_script(script, app)

        _parse_layout(layout, app)
        return app
    finally:
        conn.close()


# -- sqlite helpers --------------------------------------------------------

def _list_tables(conn: sqlite3.Connection) -> list[str]:
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        return [r[0] for r in rows]
    except sqlite3.Error:
        return []


def _first_json(conn: sqlite3.Connection, queries: list[str]) -> Optional[dict]:
    for q in queries:
        try:
            row = conn.execute(q).fetchone()
        except sqlite3.Error:
            continue
        if row and row[0] is not None:
            obj = _decode_blob(row[0])
            if isinstance(obj, dict):
                return obj
    return None


def _first_text(conn: sqlite3.Connection, queries: list[str]) -> Optional[str]:
    for q in queries:
        try:
            row = conn.execute(q).fetchone()
        except sqlite3.Error:
            continue
        if row and row[0] is not None:
            val = row[0]
            if isinstance(val, bytes):
                if val[:2] == b"\x1f\x8b":
                    val = gzip.decompress(val)
                val = val.decode("utf-8", "ignore")
            return val
    return None


def _decode_blob(data: Any) -> Any:
    if isinstance(data, bytes):
        if data[:2] == b"\x1f\x8b":          # gzip magic
            data = gzip.decompress(data)
        data = data.decode("utf-8", "ignore")
    if isinstance(data, str):
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return None
    return data


# -- layout JSON -> IR -----------------------------------------------------

def _parse_layout(layout: dict, app: QlikApp) -> None:
    meta = layout.get("qMeta", {}) or {}
    if meta.get("title"):
        app.app_name = meta["title"]

    for item in _items(layout, "qMeasureList"):
        qm = (item.get("qData", {}) or {}).get("qMeasure", {}) or {}
        app.measures.append(MasterMeasure(
            id=_qid(item),
            label=qm.get("qLabel") or meta.get("title", "") or _qid(item),
            expression=qm.get("qDef", ""),
            number_format=_fmt(qm.get("qNumFormat")),
        ))

    for item in _items(layout, "qDimensionList"):
        qd = (item.get("qData", {}) or {}).get("qDim", {}) or {}
        defs = qd.get("qFieldDefs", []) or []
        labels = qd.get("qFieldLabels", []) or []
        app.dimensions.append(MasterDimension(
            id=_qid(item),
            label=(labels or defs or [""])[0],
            fields=defs,
            expression=defs[0] if defs and defs[0].startswith("=") else None,
        ))

    for item in _items(layout, "qVariableList"):
        app.variables.append(Variable(
            name=item.get("qName", ""),
            definition=item.get("qDefinition", ""),
        ))

    sheets = [it for it in _items(layout, "qAppObjectList")
              if (it.get("qInfo", {}) or {}).get("qType") == "sheet"]
    sheets.sort(key=lambda s: (s.get("qData", {}) or {}).get("rank", 0))
    for it in sheets:
        app.sheets.append(_parse_sheet(it, app))

    if not app.tables and app.dimensions:
        app.note("info", "table",
                 "No data-model tables in layout; tables are typically defined "
                 "by the load script. Provide a connection/tables at load time.")


def _parse_sheet(item: dict, app: QlikApp) -> Sheet:
    data = item.get("qData", {}) or {}
    meta = item.get("qMeta", {}) or {}
    sheet = Sheet(id=_qid(item), title=meta.get("title", "Sheet"))
    for cell in data.get("cells", []) or []:
        vtype = cell.get("type", "UNKNOWN")
        if vtype in ("", "unknown"):
            continue
        props = cell.get("props", {}) or {}
        hc = props.get("qHyperCubeDef", {}) or {}
        dims = [(_first_field_def(d)) for d in hc.get("qDimensions", []) or []]
        meas = [(_measure_def(m)) for m in hc.get("qMeasures", []) or []]
        sheet.charts.append(Chart(
            id=cell.get("name", "obj"),
            title=props.get("title", "") or cell.get("name", ""),
            viz_type=vtype,
            dimensions=[d for d in dims if d],
            measures=[m for m in meas if m],
            raw={"col": cell.get("col"), "row": cell.get("row"),
                 "colspan": cell.get("colspan"), "rowspan": cell.get("rowspan")},
        ))
    return sheet


# -- small accessors -------------------------------------------------------

def _items(layout: dict, key: str) -> list[dict]:
    return (layout.get(key, {}) or {}).get("qItems", []) or []


def _qid(item: dict) -> str:
    return (item.get("qInfo", {}) or {}).get("qId", "")


def _fmt(numfmt: Optional[dict]) -> Optional[str]:
    if isinstance(numfmt, dict):
        return numfmt.get("qFmt")
    return None


def _first_field_def(dim: dict) -> str:
    qdef = (dim.get("qDef", {}) or {})
    labels = qdef.get("qFieldLabels", []) or []
    defs = qdef.get("qFieldDefs", []) or []
    return (labels or defs or [""])[0]


def _measure_def(m: dict) -> str:
    qdef = (m.get("qDef", {}) or {})
    return qdef.get("qLabel") or qdef.get("qDef", "")
