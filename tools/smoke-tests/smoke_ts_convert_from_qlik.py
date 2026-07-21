#!/usr/bin/env python3
"""
Smoke test — ts-convert-from-qlik (no-API / manual path).

Runs the offline extract → transform → report pipeline over a fixture .qvf and
asserts real TML + a migration report are produced. No live ThoughtSpot or Qlik
connection required (the load stage is exercised only with --validate-only in the
live smoke, not here).

    python tools/smoke-tests/smoke_ts_convert_from_qlik.py
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "fixtures" / "RetailDemo.qvf"


def run(*args: str) -> None:
    print("+ q2t", *args)
    subprocess.run(["q2t", *args], check=True)


def main() -> int:
    if not FIXTURE.is_file():
        print(f"SKIP — fixture not found: {FIXTURE}")
        return 0

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        ir_path = tmp / "app.ir.json"
        tml_dir = tmp / "tml"
        report = tmp / "report.md"

        run("extract", "--qvf", str(FIXTURE), "--out", str(ir_path), "--mode", "offline")
        assert ir_path.is_file(), "extract did not produce IR JSON"

        run("transform", "--ir", str(ir_path), "--out", str(tml_dir), "--report", str(report))
        tml_files = list(tml_dir.glob("*.tml"))
        assert tml_files, "transform produced no TML files"
        assert report.is_file(), "transform produced no report"

        # Structural sanity: at least one table TML and a model TML.
        names = {p.name for p in tml_files}
        assert any(n.startswith("table.") for n in names), f"no table TML in {names}"
        assert any(n.startswith("model.") for n in names), f"no model TML in {names}"

        print(f"PASS — {len(tml_files)} TML file(s) + report generated: {sorted(names)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
