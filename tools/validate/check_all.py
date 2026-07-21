#!/usr/bin/env python3
"""
check_all.py — run every tools/validate/check_*.py validator and report a summary.

    python3 tools/validate/check_all.py --root .

Exit code is non-zero if any validator fails.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

CHECKS = [
    "check_skill_naming.py",
    "check_skill_versions.py",
    "check_references.py",
    "check_coverage_matrix.py",
    "check_no_inline_requests.py",
    "check_secrets.py",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    here = Path(__file__).resolve().parent

    failed = []
    for check in CHECKS:
        print(f"\n=== {check} ===")
        result = subprocess.run(
            [sys.executable, str(here / check), "--root", str(root)]
        )
        if result.returncode != 0:
            failed.append(check)

    print("\n" + "=" * 40)
    if failed:
        print(f"FAILED: {', '.join(failed)}")
        return 1
    print(f"All {len(CHECKS)} validators passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
