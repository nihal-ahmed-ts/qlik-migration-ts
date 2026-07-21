"""Qlik Engine JSON-RPC extractor (recommended, reliable path).

Connects to a running Qlik engine over WebSocket and reads the full app
layout — sheets, charts, master dimensions/measures, variables, the data
model tables, and the load script — via documented Engine API methods.

This is the reliable counterpart to qvf_offline: instead of guessing at
bytes, it asks the engine. It requires the app to be reachable by a running
engine (Qlik Sense Desktop, Enterprise on Windows/Kubernetes, or Qlik Cloud)
and `websocket-client` installed.

Engine API methods used (see Qlik Engine API reference):
  OpenDoc / GetScript / GetObjects / GetObject / GetLayout /
  GetAllInfos / CreateSessionObject (for the data-model table list).
"""

from __future__ import annotations

import json
from typing import Any, Optional

from ..ir import (
    Chart, Column, Connection, MasterDimension, MasterMeasure, QlikApp,
    Sheet, Table, Variable,
)

try:
    import websocket  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    websocket = None


class QlikEngine:
    """Minimal JSON-RPC client over the Qlik Engine WebSocket protocol."""

    def __init__(self, url: str, *, headers: Optional[dict[str, str]] = None,
                 timeout: int = 30):
        if websocket is None:
            raise RuntimeError(
                "websocket-client is required for engine mode: pip install websocket-client")
        self.url = url
        self._ws = websocket.create_connection(
            url, header=[f"{k}: {v}" for k, v in (headers or {}).items()],
            timeout=timeout)
        self._id = 0

    def call(self, method: str, handle: int, *params: Any) -> Any:
        self._id += 1
        self._ws.send(json.dumps({
            "jsonrpc": "2.0", "id": self._id, "handle": handle,
            "method": method, "params": list(params),
        }))
        while True:
            msg = json.loads(self._ws.recv())
            if msg.get("id") == self._id:
                if "error" in msg:
                    raise RuntimeError(f"{method} failed: {msg['error']}")
                return msg.get("result", {})

    def close(self) -> None:
        try:
            self._ws.close()
        except Exception:
            pass


def _full_url(engine_url: str, app_id: str) -> str:
    """Qlik Cloud/Enterprise expect the app GUID in the ws path
    (wss://host/app/<guid>). If the URL ends with '/app/' we append it."""
    if engine_url.rstrip("/").endswith("/app"):
        return engine_url.rstrip("/") + "/" + app_id
    return engine_url


def probe(engine_url: str, app_id: str, *,
          headers: Optional[dict[str, str]] = None) -> dict[str, Any]:
    """Safe first-run check: connect, open the app, and list its objects.

    Returns a summary (connection ok, OpenDoc ok, object-type breakdown)
    so auth/endpoint problems surface immediately, before a full pull.
    Raises with a clear message on failure.
    """
    url = _full_url(engine_url, app_id)
    summary: dict[str, Any] = {"ws_url": url, "connected": False,
                               "opened": False, "objects": {}}
    eng = QlikEngine(url, headers=headers)
    summary["connected"] = True
    try:
        doc = eng.call("OpenDoc", -1, app_id)
        h = doc["qReturn"]["qHandle"]
        summary["opened"] = True
        infos = eng.call("GetAllInfos", h).get("qInfos", [])
        breakdown: dict[str, int] = {}
        for i in infos:
            t = i.get("qType", "?")
            breakdown[t] = breakdown.get(t, 0) + 1
        summary["objects"] = dict(sorted(breakdown.items(), key=lambda x: -x[1]))
        summary["total_objects"] = len(infos)
        return summary
    finally:
        eng.close()


def extract(engine_url: str, app_id: str, *,
            headers: Optional[dict[str, str]] = None) -> QlikApp:
    """Open an app on the engine and build the IR from its layout."""
    eng = QlikEngine(_full_url(engine_url, app_id), headers=headers)
    try:
        doc = eng.call("OpenDoc", -1, app_id)
        h = doc["qReturn"]["qHandle"]

        app = QlikApp(app_name=app_id, source_file=engine_url, extraction_mode="engine")

        # Load script.
        try:
            app.load_script = eng.call("GetScript", h).get("qScript")
        except Exception as e:
            app.note("warning", "script", f"GetScript failed: {e}")

        _read_master_items(eng, h, app)
        _read_variables(eng, h, app)
        _read_sheets(eng, h, app)
        _read_tables(eng, h, app)
        return app
    finally:
        eng.close()


def _read_master_items(eng: QlikEngine, h: int, app: QlikApp) -> None:
    for qtype, sink in (("dimension", "dim"), ("measure", "mea")):
        try:
            so = eng.call("CreateSessionObject", h, {
                "qInfo": {"qType": f"{qtype}list"},
                f"{'qDimensionListDef' if qtype=='dimension' else 'qMeasureListDef'}": {
                    "qType": qtype,
                    "qData": {"title": "/qMetaDef/title", "expr": "/qDim" if qtype=="dimension" else "/qMeasure"},
                },
            })
            soh = so["qReturn"]["qHandle"]
            layout = eng.call("GetLayout", soh)["qLayout"]
            items = (layout.get("qDimensionList") or layout.get("qMeasureList") or {}).get("qItems", [])
            for it in items:
                info = it.get("qInfo", {})
                meta = it.get("qMeta", {})
                if qtype == "dimension":
                    app.dimensions.append(MasterDimension(
                        id=info.get("qId", ""), label=meta.get("title", "")))
                else:
                    app.measures.append(MasterMeasure(
                        id=info.get("qId", ""), label=meta.get("title", "")))
        except Exception as e:
            app.note("warning", qtype, f"Could not list {qtype}s: {e}")


def _read_variables(eng: QlikEngine, h: int, app: QlikApp) -> None:
    try:
        so = eng.call("CreateSessionObject", h, {
            "qInfo": {"qType": "variablelist"},
            "qVariableListDef": {"qType": "variable", "qShowReserved": False,
                                 "qShowConfig": False, "qData": {"definition": "/qDefinition"}},
        })
        layout = eng.call("GetLayout", so["qReturn"]["qHandle"])["qLayout"]
        for it in layout.get("qVariableList", {}).get("qItems", []):
            app.variables.append(Variable(
                name=it.get("qName", ""),
                definition=(it.get("qData", {}) or {}).get("definition", "")))
    except Exception as e:
        app.note("warning", "variable", f"Could not list variables: {e}")


def _read_sheets(eng: QlikEngine, h: int, app: QlikApp) -> None:
    try:
        so = eng.call("CreateSessionObject", h, {
            "qInfo": {"qType": "sheetlist"},
            "qAppObjectListDef": {"qType": "sheet", "qData": {"title": "/qMetaDef/title", "cells": "/cells"}},
        })
        layout = eng.call("GetLayout", so["qReturn"]["qHandle"])["qLayout"]
        for it in layout.get("qAppObjectList", {}).get("qItems", []):
            info = it.get("qInfo", {})
            data = it.get("qData", {}) or {}
            sheet = Sheet(id=info.get("qId", ""), title=data.get("title", "Sheet"))
            for cell in data.get("cells", []) or []:
                sheet.charts.append(_chart_from_cell(eng, h, cell, app))
            app.sheets.append(sheet)
    except Exception as e:
        app.note("warning", "chart", f"Could not list sheets: {e}")


def _chart_from_cell(eng: QlikEngine, h: int, cell: dict, app: QlikApp) -> Chart:
    obj_id = cell.get("name", "")
    chart = Chart(id=obj_id, viz_type=cell.get("type", "UNKNOWN"))
    try:
        obj = eng.call("GetObject", h, obj_id)
        layout = eng.call("GetLayout", obj["qReturn"]["qHandle"])["qLayout"]
        chart.title = (layout.get("title") or layout.get("qMeta", {}).get("title") or "")
        hc = layout.get("qHyperCube", {})
        chart.dimensions = [d.get("qFallbackTitle", "") for d in hc.get("qDimensionInfo", [])]
        chart.measures = [m.get("qFallbackTitle", "") for m in hc.get("qMeasureInfo", [])]
    except Exception as e:
        app.note("warning", "chart", f"Could not read object {obj_id}: {e}")
    return chart


def _read_tables(eng: QlikEngine, h: int, app: QlikApp) -> None:
    try:
        tv = eng.call("GetTablesAndKeys", h, {"qcx": 1000, "qcy": 1000},
                      {"qcx": 0, "qcy": 0}, 0, True, False)
        for t in tv.get("qtr", []):
            tbl = Table(name=t.get("qName", ""))
            for fld in t.get("qFields", []):
                tbl.columns.append(Column(name=fld.get("qName", "")))
            app.tables.append(tbl)
    except Exception as e:
        app.note("warning", "table", f"Could not read data model tables: {e}")
