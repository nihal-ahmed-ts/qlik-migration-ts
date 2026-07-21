#!/usr/bin/env bash
# Pre-commit hook — static validation + unit tests.
# Install:  ln -s ../../scripts/pre-commit.sh .git/hooks/pre-commit
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

echo "[pre-commit] validators…"
python3 tools/validate/check_all.py --root .

echo "[pre-commit] unit tests…"
if command -v pytest >/dev/null 2>&1; then
  pytest -q tools/q2t-cli/tests
else
  python3 -m pytest -q tools/q2t-cli/tests
fi

echo "[pre-commit] OK"
