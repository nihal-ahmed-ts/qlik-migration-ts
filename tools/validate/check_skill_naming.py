#!/usr/bin/env python3
"""
check_skill_naming.py — validate skill directory names against the family
patterns in .claude/rules/skill-naming.md.

Walks agents/cli/<skill>/ for any directory containing a SKILL.md and checks the
name matches a documented family regex (or is allowlisted).

    python3 tools/validate/check_skill_naming.py --root .
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# family key -> (regex matching the full dir name, one-line description)
FAMILY_PATTERNS = {
    "ts-convert-*": (
        re.compile(r"ts-convert-(to|from)-[a-z][a-z0-9]*(-[a-z0-9]+)*"),
        "cross-platform conversion: ts-convert-{to|from}-{format}[-{frontend}]",
    ),
}

# Skills that legitimately don't match any family (each needs a justification).
ALLOWLIST: set[str] = set()


def find_skills(root: Path) -> list[Path]:
    cli = root / "agents" / "cli"
    if not cli.is_dir():
        return []
    return sorted(c for c in cli.iterdir() if c.is_dir() and (c / "SKILL.md").is_file())


def matched_family(name: str) -> str | None:
    for family, (pattern, _) in FAMILY_PATTERNS.items():
        if pattern.fullmatch(name):
            return family
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()

    skills = find_skills(root)
    if not skills:
        print(f"No skills found under {root}/agents/cli/. Nothing to check.")
        return 0

    failures = []
    for path in skills:
        name = path.name
        if name in ALLOWLIST or matched_family(name):
            print(f"  OK   {name}")
        else:
            failures.append(path)

    if failures:
        print(f"\n{len(failures)} skill(s) violate the naming convention:\n")
        for path in failures:
            print(f"  ✗ {path.relative_to(root)} — {path.name!r} matches no family")
        print("\nDocumented families (see .claude/rules/skill-naming.md):")
        for family, (_, desc) in FAMILY_PATTERNS.items():
            print(f"  {family:<16} {desc}")
        return 1

    print(f"\nAll {len(skills)} skill name(s) match a documented family.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
