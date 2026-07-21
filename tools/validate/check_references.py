#!/usr/bin/env python3
"""
check_references.py — verify markdown links in SKILL.md, references/*.md,
agents/shared/**/*.md, and top-level docs resolve to files that exist.

Relative links resolve from the source file's own directory. HTTP links,
anchors, and template placeholders ({var}) are skipped.

    python3 tools/validate/check_references.py --root .
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def scanned_files(root: Path) -> list[Path]:
    files: list[Path] = []
    files += sorted((root / "agents" / "cli").glob("*/SKILL.md"))
    files += sorted((root / "agents" / "cli").glob("*/references/*.md"))
    files += sorted((root / "agents" / "shared").glob("**/*.md"))
    for name in ("README.md", "CLAUDE.md", "CHANGELOG.md"):
        p = root / name
        if p.is_file():
            files.append(p)
    return files


def resolve(target: str, source: Path) -> Path | None:
    if target.startswith(("http://", "https://", "#", "mailto:")) or not target.strip():
        return None
    path_part = target.split("#")[0]
    if not path_part or "{" in path_part or "}" in path_part:
        return None
    if path_part.startswith("/"):
        return None  # absolute filesystem paths — skip
    return (source.parent / path_part).resolve()


def check_file(f: Path, root: Path) -> list[tuple[int, str, str]]:
    broken = []
    for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
        for _text, target in LINK_RE.findall(line):
            resolved = resolve(target, f)
            if resolved is None:
                continue
            if not resolved.exists():
                try:
                    shown = resolved.relative_to(root)
                except ValueError:
                    shown = resolved
                broken.append((i, target, str(shown)))
    return broken


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()

    files = scanned_files(root)
    if not files:
        print("No markdown files found to check.")
        return 1

    total = 0
    for f in files:
        rel = f.relative_to(root)
        broken = check_file(f, root)
        if broken:
            for ln, target, resolved in broken:
                print(f"FAIL  {rel}:{ln}  →  {target}  (resolved: {resolved})")
                total += 1
        else:
            print(f"PASS  {rel}")

    if total:
        print(f"\n{total} broken reference(s) found.")
        return 1
    print("\nAll references resolved.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
