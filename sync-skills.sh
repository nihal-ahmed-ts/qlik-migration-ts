#!/usr/bin/env bash
# Sync the live authoring copies of the skills (~/.claude/skills) into this
# repo's plugin, which is the single source of truth for distribution.
# Run from the repo root after editing a skill, then commit + push.
set -euo pipefail

SRC="$HOME/.claude/skills"
DST="plugins/qlik-to-thoughtspot/skills"

for skill in qlik-to-thoughtspot qlik-to-thoughtspot-api; do
  cp "$SRC/$skill/SKILL.md" "$DST/$skill/SKILL.md"
  echo "synced $skill"
done

git diff --stat "$DST" || true
echo "Done. Review the diff, then: git add $DST && git commit && git push"
