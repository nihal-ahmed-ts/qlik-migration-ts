#!/usr/bin/env python3
"""
check_skill_versions.py — every skill's SKILL.md must have a ## Changelog section
with at least one valid semver row.

    ## Changelog
    | Version | Date | Summary |
    |---|---|---|
    | 1.0.0 | 2026-07-21 | ... |

    python3 tools/validate/check_skill_versions.py --root .
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROW_RE = re.compile(r"^\|\s*(\d+\.\d+\.\d+)\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|.+\|")


def check_skill(skill_file: Path) -> list[str]:
    text = skill_file.read_text(encoding="utf-8")
    if "## Changelog" not in text:
        return ["missing ## Changelog section"]
    body = text.split("## Changelog", 1)[1]
    rows = [ln for ln in body.splitlines() if ROW_RE.match(ln.strip())]
    if not rows:
        return ["## Changelog has no valid rows (expected | X.Y.Z | YYYY-MM-DD | ... |)"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()

    skill_files = sorted((root / "agents" / "cli").glob("*/SKILL.md"))
    if not skill_files:
        print("ERROR: no SKILL.md files found under agents/cli/ — is --root correct?")
        return 1

    failed = 0
    for f in skill_files:
        rel = f.relative_to(root)
        errors = check_skill(f)
        if errors:
            for e in errors:
                print(f"  FAIL  {rel}: {e}")
            failed += 1
        else:
            body = f.read_text(encoding="utf-8").split("## Changelog", 1)[1]
            ver = next(ln.strip().split("|")[1].strip()
                       for ln in body.splitlines() if ROW_RE.match(ln.strip()))
            print(f"  PASS  {rel}: v{ver}")

    if failed:
        print(f"\n{failed} skill file(s) missing a valid changelog.")
        return 1
    print(f"\nAll {len(skill_files)} skill file(s) have a valid changelog.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
