"""Ingest the JSON artifacts produced by the headless-engine extractor
(qvf-engine-extract/) into the IR.

That sidecar Node/Docker tool dumps an output/ folder:
    script.qvs         raw load script
    data-model.json    getTablesAndKeys() -> { qtr: [tables], qk: [keys] }
    master-items.json  { measures: [{id, props}], dimensions: [{id, props}] }
    sheets.json        [{ id, title, properties, children: [{id, type, props}] }]
    manifest.json      { app, counts, ... }

Because those come straight from the Qlik engine, the resulting IR is
SOURCE-grade (extraction_mode="engine") — the faithful path, no PDF guessing.
This reader is tolerant of missing files/keys so a partial export still yields
a usable IR with notes about what was absent.
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional

from ..ir import (
    Chart, Column, Connection, MasterDimension, MasterMeasure, QlikApp,
    Sheet, Table, Variable,
)


def _read_json(path: str) -> Optional[Any]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def _read_text(path: str) -> Optional[str]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def extract(artifacts_dir: str) -> QlikApp:
    d = artifacts_dir
    manifest = _read_json(os.path.join(d, "manifest.json")) or {}
    app_name = (manifest.get("app") or os.path.basename(os.path.normpath(d)) or "app")
    if app_name.lower().endswith(".qvf"):
        app_name = app_name[:-4]

    app = QlikApp(app_name=app_name, source_file=d, extraction_mode="engine")

    script = _read_text(os.path.join(d, "script.qvs"))
    if script:
        app.load_script = script
        from . import qvf_offline
        qvf_offline._parse_connections_from_script(script, app)
    else:
        app.note("warning", "script", "No script.qvs in artifacts.")

    _ingest_data_model(_read_json(os.path.join(d, "data-model.json")), app)
    _ingest_master_items(_read_json(os.path.join(d, "master-items.json")), app)
    _ingest_sheets(_read_json(os.path.join(d, "sheets.json")), app)
    return app


# -- data model (getTablesAndKeys) -----------------------------------------

def _ingest_data_model(dm: Optional[dict], app: QlikApp) -> None:
    if not dm:
        app.note("warning", "table", "No data-model.json; tables not loaded.")
        return
    conn = app.connections[0].name if app.connections else None
    for t in dm.get("qtr", []) or []:
        name = t.get("qName")
        if not name:
            continue
        cols = [Column(name=f.get("qName")) for f in (t.get("qFields") or []) if f.get("qName")]
        app.tables.append(Table(name=name, columns=cols, source_connection=conn))

    # Associations (qk) become join hints — the IR has no joins field, so we
    # record them as notes for the transform/report to surface.
    for k in dm.get("qk", []) or []:
        fields = k.get("qKeyFields") or []
        tables = k.get("qTables") or []
        if fields and len(tables) >= 2:
            app.note("info", "join",
                     f"Association on {', '.join(fields)}: {' <-> '.join(tables)}")


# -- master items ----------------------------------------------------------

def _ingest_master_items(mi: Optional[dict], app: QlikApp) -> None:
    if not mi:
        app.note("warning", "measure", "No master-items.json; measures/dimensions not loaded.")
        return
    for m in mi.get("measures", []) or []:
        props = m.get("props", {}) or {}
        qm = props.get("qMeasure", {}) or {}
        meta = props.get("qMetaDef", {}) or {}
        app.measures.append(MasterMeasure(
            id=m.get("id") or _qid(props),
            label=qm.get("qLabel") or meta.get("title") or m.get("id", ""),
            expression=qm.get("qDef", ""),
            number_format=_fmt(qm.get("qNumFormat")),
        ))
    for dmn in mi.get("dimensions", []) or []:
        props = dmn.get("props", {}) or {}
        qd = props.get("qDim", {}) or {}
        meta = props.get("qMetaDef", {}) or {}
        defs = qd.get("qFieldDefs", []) or []
        labels = qd.get("qFieldLabels", []) or []
        app.dimensions.append(MasterDimension(
            id=dmn.get("id") or _qid(props),
            label=meta.get("title") or (labels or defs or [""])[0],
            fields=defs,
            expression=defs[0] if defs and defs[0].startswith("=") else None,
        ))


# -- sheets + charts -------------------------------------------------------

def _ingest_sheets(sheets: Optional[list], app: QlikApp) -> None:
    if not sheets:
        app.note("warning", "chart", "No sheets.json; sheets/charts not loaded.")
        return
    for s in sheets:
        sheet = Sheet(id=s.get("id", ""), title=s.get("title") or s.get("id", "Sheet"))
        for child in s.get("children", []) or []:
            props = child.get("props", {}) or {}
            vtype = child.get("type") or _qtype(props) or "UNKNOWN"
            if vtype in ("", "sheet"):
                continue
            hc = props.get("qHyperCubeDef", {}) or {}
            dims = [_first_def(x) for x in hc.get("qDimensions", []) or []]
            meas = [_measure_def(x) for x in hc.get("qMeasures", []) or []]
            sheet.charts.append(Chart(
                id=child.get("id", ""),
                title=props.get("title") or (props.get("qMetaDef", {}) or {}).get("title", "")
                      or child.get("id", ""),
                viz_type=vtype,
                dimensions=[x for x in dims if x],
                measures=[x for x in meas if x],
            ))
        app.sheets.append(sheet)


# -- small accessors -------------------------------------------------------

def _qid(props: dict) -> str:
    return (props.get("qInfo", {}) or {}).get("qId", "")


def _qtype(props: dict) -> str:
    return (props.get("qInfo", {}) or {}).get("qType", "")


def _fmt(numfmt: Optional[dict]) -> Optional[str]:
    return numfmt.get("qFmt") if isinstance(numfmt, dict) else None


def _first_def(dim: dict) -> str:
    qdef = dim.get("qDef", {}) or {}
    labels = qdef.get("qFieldLabels", []) or []
    defs = qdef.get("qFieldDefs", []) or []
    return (labels or defs or [""])[0]


def _measure_def(m: dict) -> str:
    qdef = m.get("qDef", {}) or {}
    return qdef.get("qLabel") or qdef.get("qDef", "")
