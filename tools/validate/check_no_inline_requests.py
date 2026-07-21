#!/usr/bin/env python3
"""
check_no_inline_requests.py — SKILL.md files must not contain inline HTTP calls.

Skills drive ThoughtSpot/Qlik through the `q2t` CLI; direct `requests` (or
websocket) calls belong INSIDE the CLI (tools/q2t-cli/), never in a SKILL.md.
See .claude/rules/ts-cli.md.

    python3 tools/validate/check_no_inline_requests.py --root .
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# High-signal inline-HTTP patterns. `requests` as a bare English word is fine;
# these match actual call/import forms.
PATTERNS = [
    re.compile(r"\bimport\s+requests\b"),
    re.compile(r"\bfrom\s+requests\b"),
    re.compile(r"\brequests\.(get|post|put|delete|patch|request|Session)\s*\("),
    re.compile(r"\bhttpx\.(get|post|put|delete|patch|Client)\s*\("),
    re.compile(r"\burllib\.request\.urlopen\s*\("),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()

    skill_files = sorted((root / "agents" / "cli").glob("*/SKILL.md"))
    if not skill_files:
        print("No SKILL.md files found. Nothing to check.")
        return 0

    hits = []
    for f in skill_files:
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            for pat in PATTERNS:
                if pat.search(line):
                    hits.append((f.relative_to(root), i, line.strip()))
                    break

    if hits:
        print("Inline HTTP calls found in SKILL.md (use the q2t CLI instead):\n")
        for rel, ln, text in hits:
            print(f"  FAIL  {rel}:{ln}  {text}")
        print("\nMove the call into tools/q2t-cli/ and invoke it via a q2t command.")
        return 1

    print(f"OK — no inline HTTP calls in {len(skill_files)} SKILL.md file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
