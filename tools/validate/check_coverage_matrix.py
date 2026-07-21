#!/usr/bin/env python3
"""
check_coverage_matrix.py — every ts-convert-* skill must ship a
references/coverage-matrix.md documenting what it maps and what it does not.

    python3 tools/validate/check_coverage_matrix.py --root .
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()

    convert_skills = sorted(
        p for p in (root / "agents" / "cli").glob("ts-convert-*")
        if p.is_dir() and (p / "SKILL.md").is_file()
    )
    if not convert_skills:
        print("No ts-convert-* skills found. Nothing to check.")
        return 0

    failed = 0
    for skill in convert_skills:
        matrix = skill / "references" / "coverage-matrix.md"
        rel = skill.relative_to(root)
        if matrix.is_file() and matrix.read_text(encoding="utf-8").strip():
            print(f"  OK   {rel}/references/coverage-matrix.md")
        else:
            print(f"  FAIL {rel}: missing or empty references/coverage-matrix.md")
            failed += 1

    if failed:
        print(f"\n{failed} conversion skill(s) missing a coverage matrix.")
        return 1
    print(f"\nAll {len(convert_skills)} conversion skill(s) have a coverage matrix.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
