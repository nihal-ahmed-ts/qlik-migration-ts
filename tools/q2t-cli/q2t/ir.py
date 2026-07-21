"""Normalized intermediate representation (IR) for a Qlik Sense app.

This is the single contract between the Qlik-extraction side and the
ThoughtSpot-loading side of the pipeline. Extractors (offline or engine)
populate these dataclasses; transformers consume them. Keeping it plain and
serializable means you can dump the IR to JSON, inspect it, hand-edit it, and
re-run the later stages without touching Qlik again.

Every field is optional-friendly: a best-effort offline extraction will fill
in what it can and leave the rest empty rather than fail.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict, is_dataclass
from typing import Any, Optional


@dataclass
class Column:
    """A field/column on a Qlik table."""
    name: str
    data_type: str = "UNKNOWN"          # Qlik-side type, mapped later
    src_table: Optional[str] = None     # qualified source table, if known


@dataclass
class Table:
    """A table as loaded into the Qlik data model."""
    name: str
    columns: list[Column] = field(default_factory=list)
    db_name: Optional[str] = None       # external DB (when live-connected)
    schema_name: Optional[str] = None
    source_connection: Optional[str] = None  # name of the Connection it came from
    # Free-form load-script snippet that produced this table, if recovered.
    load_script: Optional[str] = None


@dataclass
class Connection:
    """A Qlik data connection (lib://...)."""
    name: str
    qlik_type: str = "UNKNOWN"          # e.g. "Snowflake", "ODBC", "Folder"
    # Raw connection-string / properties as recovered from Qlik. Secrets are
    # never present in a .qvf, so credentials must be supplied at load time.
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class MasterDimension:
    """Qlik master dimension -> ThoughtSpot worksheet column (or formula)."""
    id: str
    label: str
    fields: list[str] = field(default_factory=list)  # one or more field defs
    expression: Optional[str] = None    # set for calculated dimensions


@dataclass
class MasterMeasure:
    """Qlik master measure -> ThoughtSpot worksheet formula."""
    id: str
    label: str
    expression: str = ""                # Qlik measure expression (e.g. Sum(Sales))
    number_format: Optional[str] = None


@dataclass
class Variable:
    """Qlik variable -> ThoughtSpot formula / parameter."""
    name: str
    definition: str = ""


@dataclass
class Chart:
    """A single visualization on a sheet."""
    id: str
    title: str = ""
    viz_type: str = "UNKNOWN"           # Qlik object type: barchart, kpi, table...
    dimensions: list[str] = field(default_factory=list)  # measure/dim ids or exprs
    measures: list[str] = field(default_factory=list)
    # Anything we could not interpret, kept verbatim for the report.
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class Sheet:
    """A Qlik sheet -> a ThoughtSpot Liveboard tab."""
    id: str
    title: str = ""
    charts: list[Chart] = field(default_factory=list)


@dataclass
class ExtractionNote:
    """A single thing the extractor could not fully recover."""
    severity: str                       # "info" | "warning" | "manual"
    area: str                           # "connection" | "chart" | "script" ...
    message: str


@dataclass
class QlikApp:
    """The whole extracted app — the root of the IR."""
    app_name: str
    source_file: Optional[str] = None
    extraction_mode: str = "offline"    # "offline" | "engine"
    connections: list[Connection] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)
    dimensions: list[MasterDimension] = field(default_factory=list)
    measures: list[MasterMeasure] = field(default_factory=list)
    variables: list[Variable] = field(default_factory=list)
    sheets: list[Sheet] = field(default_factory=list)
    load_script: Optional[str] = None
    notes: list[ExtractionNote] = field(default_factory=list)

    # -- (de)serialization -------------------------------------------------

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(asdict(self), indent=indent, ensure_ascii=False)

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self.to_json())

    def note(self, severity: str, area: str, message: str) -> None:
        self.notes.append(ExtractionNote(severity, area, message))

    @staticmethod
    def load(path: str) -> "QlikApp":
        with open(path, encoding="utf-8") as fh:
            return QlikApp.from_dict(json.load(fh))

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "QlikApp":
        return QlikApp(
            app_name=d.get("app_name", "Untitled"),
            source_file=d.get("source_file"),
            extraction_mode=d.get("extraction_mode", "offline"),
            connections=[_mk(Connection, c) for c in d.get("connections", [])],
            tables=[_mk_table(t) for t in d.get("tables", [])],
            dimensions=[_mk(MasterDimension, x) for x in d.get("dimensions", [])],
            measures=[_mk(MasterMeasure, x) for x in d.get("measures", [])],
            variables=[_mk(Variable, x) for x in d.get("variables", [])],
            sheets=[_mk_sheet(s) for s in d.get("sheets", [])],
            load_script=d.get("load_script"),
            notes=[_mk(ExtractionNote, n) for n in d.get("notes", [])],
        )


# -- small construction helpers (tolerant of missing/extra keys) -----------

def _fields(cls) -> set[str]:
    return {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]


def _mk(cls, d: dict[str, Any]):
    """Build a flat dataclass, ignoring unknown keys."""
    allowed = _fields(cls)
    return cls(**{k: v for k, v in d.items() if k in allowed})


def _mk_table(d: dict[str, Any]) -> Table:
    t = _mk(Table, d)
    t.columns = [_mk(Column, c) for c in d.get("columns", [])]
    return t


def _mk_sheet(d: dict[str, Any]) -> Sheet:
    s = _mk(Sheet, d)
    s.charts = [_mk(Chart, c) for c in d.get("charts", [])]
    return s


assert is_dataclass(QlikApp)
