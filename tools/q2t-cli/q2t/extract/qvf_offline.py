"""Best-effort OFFLINE extraction from a raw .qvf file.

IMPORTANT: a .qvf is a proprietary binary container. There is no public spec
and no guarantee of what can be recovered without a Qlik engine. This module
does NOT pretend otherwise — it scavenges what is recognizable from the bytes
and records, in `app.notes`, everything it could not interpret so nothing is
silently lost.

What it tries to recover:
  * The load script (Qlik stores it as a recognizable text block).
  * Data-connection references (lib://... and CONNECT statements in script).
  * Tables + fields parsed from LOAD / SQL SELECT statements in the script.
  * Any embedded JSON layout fragments (qInfo / qType objects) -> sheets/charts.

For reliable chart/master-item recovery use the engine extractor instead.
"""

from __future__ import annotations

import json
import re
from typing import Iterator

from ..ir import (
    Chart, Column, Connection, MasterMeasure, QlikApp, Sheet, Table,
)

# Printable-string scanning thresholds. Include tab/CR/LF so that multi-line
# blocks (notably the load script) survive as a single run instead of being
# shattered into one-line fragments.
_MIN_STR = 4
_PRINTABLE = re.compile(rb"[\x09\x0a\x0d\x20-\x7e]{%d,}" % _MIN_STR)

# Recognizable Qlik script markers used to locate the load script block.
_SCRIPT_MARKERS = ("LOAD ", "SQL SELECT", "SET ", "LET ", "lib://", "CONNECT")


def extract(qvf_path: str) -> QlikApp:
    with open(qvf_path, "rb") as fh:
        data = fh.read()

    app_name = qvf_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    app = QlikApp(app_name=app_name, source_file=qvf_path, extraction_mode="offline")
    app.note("warning", "general",
             "Offline extraction is best-effort. Charts and master items are "
             "often not fully recoverable without a Qlik engine; verify against "
             "the source app.")

    strings = list(_iter_strings(data))

    script = _recover_load_script(strings)
    if script:
        app.load_script = script
        _parse_connections_from_script(script, app)
        _parse_tables_from_script(script, app)
    else:
        app.note("manual", "script",
                 "Could not locate a load script in the .qvf. Re-export via the "
                 "Qlik engine, or paste the script manually into the IR.")

    _recover_embedded_json(data, app)

    if not app.sheets:
        app.note("manual", "chart",
                 "No sheet/chart layout recovered offline. Charts must be "
                 "rebuilt manually or extracted via --mode engine.")
    return app


# -- string scanning -------------------------------------------------------

def _iter_strings(data: bytes) -> Iterator[str]:
    """Yield printable ASCII runs, plus a UTF-16LE pass (Qlik uses UTF-16)."""
    for m in _PRINTABLE.finditer(data):
        yield m.group().decode("ascii", "ignore")
    try:
        text16 = data.decode("utf-16-le", "ignore")
        for run in re.findall(r"[\x09\x0a\x0d\x20-\x7e]{%d,}" % _MIN_STR, text16):
            yield run
    except Exception:
        pass


def _recover_load_script(strings: list[str]) -> str | None:
    """Heuristically stitch together the longest block of script-looking text."""
    candidates = [s for s in strings if any(mk in s for mk in _SCRIPT_MARKERS)]
    if not candidates:
        return None
    # Prefer the single largest chunk; Qlik usually stores the script contiguously.
    best = max(candidates, key=len)
    return best if len(best) > 20 else None


def _parse_connections_from_script(script: str, app: QlikApp) -> None:
    seen: set[str] = set()
    # lib://ConnectionName/...  and  CONNECT TO [ ... ];
    for name in re.findall(r"lib://([^/\"'\];]+)", script):
        name = name.strip()
        if name and name not in seen:
            seen.add(name)
            app.connections.append(Connection(name=name, qlik_type=_guess_type(script, name)))
    for m in re.finditer(r"CONNECT\s+TO\s+\[?([^\];\n]+)", script, re.IGNORECASE):
        name = m.group(1).strip().strip("'\"")
        if name and name not in seen:
            seen.add(name)
            app.connections.append(Connection(name=name, qlik_type=_guess_type(script, name)))


def _guess_type(script: str, near: str) -> str:
    low = script.lower()
    for key in ("snowflake", "bigquery", "redshift", "postgres", "sqlserver",
                "sql server", "databricks", "oracle", "mysql", "teradata"):
        if key in low:
            return key
    return "UNKNOWN"


def _parse_tables_from_script(script: str, app: QlikApp) -> None:
    """Parse `[Table]:` labels followed by LOAD field lists. Heuristic but
    handles the common `TableName:\\n LOAD a, b, c FROM ...;` pattern."""
    # Split on statement labels:  Name:
    for m in re.finditer(r"(?:^|\n)\s*([A-Za-z_][\w ]*?):\s*\n?\s*(LOAD|SQL\s+SELECT)",
                         script, re.IGNORECASE):
        tname = m.group(1).strip()
        start = m.end()
        stmt = script[start:start + 2000]            # window after the label
        end = stmt.find(";")
        if end != -1:
            stmt = stmt[:end]
        cols = _parse_field_list(stmt)
        if cols:
            app.tables.append(Table(name=tname, columns=[Column(name=c) for c in cols]))


def _parse_field_list(stmt: str) -> list[str]:
    """Extract field names from the part of a LOAD/SELECT before FROM."""
    head = re.split(r"\bFROM\b|\bRESIDENT\b", stmt, maxsplit=1, flags=re.IGNORECASE)[0]
    fields: list[str] = []
    for part in head.split(","):
        part = part.strip()
        # `expr as [Alias]` -> Alias ; `[Field]` -> Field ; `Field`
        m = re.search(r"\bas\s+\[?([^\],]+)\]?\s*$", part, re.IGNORECASE)
        if m:
            fields.append(m.group(1).strip())
        else:
            m2 = re.match(r"^\[?([A-Za-z_][\w ]*)\]?$", part)
            if m2:
                fields.append(m2.group(1).strip())
    return [f for f in fields if f and f.upper() not in ("LOAD", "SELECT")]


# -- embedded JSON layout --------------------------------------------------

def _recover_embedded_json(data: bytes, app: QlikApp) -> None:
    """Scan for embedded JSON objects carrying Qlik qInfo/qType markers and
    turn any sheet/chart-shaped ones into IR Sheets/Charts."""
    text = data.decode("utf-8", "ignore")
    found = 0
    for obj in _iter_json_objects(text):
        qtype = (obj.get("qInfo", {}) or {}).get("qType") or obj.get("qType")
        if qtype == "sheet" or obj.get("cells") is not None:
            app.sheets.append(_sheet_from_json(obj))
            found += 1
        elif qtype == "measure":
            qm = obj.get("qMeasure", {})
            app.measures.append(MasterMeasure(
                id=(obj.get("qInfo", {}) or {}).get("qId", "m"),
                label=qm.get("qLabel") or qm.get("title", ""),
                expression=qm.get("qDef", ""),
            ))
            found += 1
    if found:
        app.note("info", "general", f"Recovered {found} embedded JSON object(s) offline.")


def _iter_json_objects(text: str) -> Iterator[dict]:
    """Yield top-level JSON objects found by brace-matching around 'qInfo'."""
    for anchor in re.finditer(r'\{[^{}]*"qInfo"', text):
        start = anchor.start()
        depth, i = 0, start
        in_str, esc = False, False
        while i < len(text) and i < start + 100_000:
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            yield json.loads(text[start:i + 1])
                        except json.JSONDecodeError:
                            pass
                        break
            i += 1


def _sheet_from_json(obj: dict) -> Sheet:
    info = obj.get("qInfo", {}) or {}
    meta = obj.get("qMeta", {}) or obj.get("meta", {}) or {}
    sheet = Sheet(id=info.get("qId", "sheet"), title=meta.get("title", "Sheet"))
    for cell in obj.get("cells", []) or []:
        sheet.charts.append(Chart(
            id=cell.get("name", "obj"),
            viz_type=cell.get("type", "UNKNOWN"),
            raw=cell,
        ))
    return sheet
