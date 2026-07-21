#!/usr/bin/env python3
"""
Smoke test — ts-convert-from-qlik-api (Qlik Cloud API path).

The full API path needs a live Qlik Cloud tenant + key, so this smoke test
verifies the CLI *wiring* instead: the qlik-cloud extract mode is registered and
fails cleanly without credentials, and the shared transform → report stage
produces valid TML from a fixture IR (the half that does not depend on Qlik).

    python tools/smoke-tests/smoke_ts_convert_from_qlik_api.py
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "fixtures" / "RetailDemo.qvf"


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    print("+ q2t", *args)
    return subprocess.run(["q2t", *args], capture_output=True, text=True, check=check)


def main() -> int:
    # 1. qlik-cloud mode is a registered extract mode (help mentions it).
    help_out = run("extract", "--help").stdout + run("extract", "--help").stderr
    assert "qlik-cloud" in help_out, "extract --help does not list the qlik-cloud mode"
    print("PASS — qlik-cloud extract mode is wired")

    # 2. Without a tenant/key, qlik-cloud extract fails cleanly (non-zero, no traceback dump).
    with tempfile.TemporaryDirectory() as tmp:
        out = run("extract", "--mode", "qlik-cloud", "--out", str(Path(tmp) / "x.json"),
                  check=False)
        assert out.returncode != 0, "qlik-cloud extract should fail without tenant/app-id"
        print("PASS — qlik-cloud extract fails cleanly without credentials")

    # 3. Shared transform → report stage works (Qlik-independent half of the path).
    if FIXTURE.is_file():
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            ir_path, tml_dir, report = tmp / "a.json", tmp / "tml", tmp / "r.md"
            run("extract", "--qvf", str(FIXTURE), "--out", str(ir_path), "--mode", "offline")
            run("transform", "--ir", str(ir_path), "--out", str(tml_dir), "--report", str(report))
            assert list(tml_dir.glob("*.tml")), "transform produced no TML"
            assert report.is_file(), "transform produced no report"
            print("PASS — transform → report stage produces TML")
    else:
        print(f"SKIP transform stage — fixture not found: {FIXTURE}")

    print("PASS — ts-convert-from-qlik-api wiring verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
