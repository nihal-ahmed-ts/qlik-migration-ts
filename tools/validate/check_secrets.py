#!/usr/bin/env python3
"""
check_secrets.py — scan tracked text files for committed credentials.

High-signal patterns only, to avoid flagging placeholders like `--password`,
`TS_PASS`, or `QLIK_API_KEY=<key>`. Fails the commit/PR if any real-looking
secret literal is found.

    python3 tools/validate/check_secrets.py --root .
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

SECRET_PATTERNS = [
    ("GitHub PAT", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("GitHub fine-grained PAT", re.compile(r"github_pat_[A-Za-z0-9_]{30,}")),
    ("AWS access key id", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Private key block", re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("Slack token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    # bearer/secret literals assigned to an obvious secret var (not a placeholder)
    ("Hardcoded bearer token", re.compile(r"[Bb]earer\s+[A-Za-z0-9_\-\.]{30,}")),
]

# Placeholder fragments that neutralise a match on the same line.
PLACEHOLDER_HINTS = ("<", ">", "example", "placeholder", "your-", "xxxx", "…", "REDACTED")

SKIP_SUFFIXES = (".png", ".jpg", ".jpeg", ".pdf", ".qvf", ".ico", ".gif",
                 ".zip", ".gz", ".lock")
SKIP_DIRS = ("node_modules", "__pycache__", ".git", "build", ".venv")


def tracked_files(root: Path) -> list[Path]:
    out = subprocess.run(["git", "ls-files"], capture_output=True, text=True, cwd=root)
    files = []
    for rel in out.stdout.splitlines():
        if any(part in SKIP_DIRS for part in Path(rel).parts):
            continue
        if rel.endswith(SKIP_SUFFIXES):
            continue
        files.append(root / rel)
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()

    hits = []
    for f in tracked_files(root):
        # Never scan this validator itself — it contains the patterns by design.
        if f.name == "check_secrets.py":
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            low = line.lower()
            if any(h in low for h in (p.lower() for p in PLACEHOLDER_HINTS)):
                continue
            for label, pat in SECRET_PATTERNS:
                if pat.search(line):
                    hits.append((f.relative_to(root), i, label))
                    break

    if hits:
        print("Potential secrets found in tracked files:\n")
        for rel, ln, label in hits:
            print(f"  FAIL  {rel}:{ln}  ({label})")
        print("\nRemove the secret, rotate it, and use env vars / a credential store.")
        return 1

    print("OK — no committed secrets detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
