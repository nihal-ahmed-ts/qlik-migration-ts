# Changelog

Repo-level changes. Dated, newest on top. Per-skill changes live in each skill's
`## Changelog` (see `.claude/rules/versioning.md`).

## 2026-07-21
- refactor: align repo structure with `thoughtspot-agent-skills` conventions
  - skills moved to `agents/cli/` and renamed `qlik-to-thoughtspot*` →
    `ts-convert-from-qlik` / `ts-convert-from-qlik-api` (family `ts-convert-from-*`)
  - `q2t` packaged as an installable CLI under `tools/q2t-cli/` (console script
    `q2t`, replacing `python -m q2t`)
  - shared reference library added under `agents/shared/` (formula translation,
    TML invariants, IR contract)
  - added `.claude/rules/` (skill-naming, content-structure, ts-cli, security,
    branching, versioning), `CLAUDE.md`, `LICENSE`, `.mcp.json`
  - each skill gained `references/coverage-matrix.md`, `references/open-items.md`,
    and a `## Changelog`
  - added `tools/validate/` validators, first unit tests under
    `tools/q2t-cli/tests/`, smoke tests, `scripts/pre-commit.sh`, and CI
    (`.github/workflows/validate.yml`)
  - removed the plugin-marketplace layout (`.claude-plugin/`, `plugins/`,
    `sync-skills.sh`) in favor of the symlink install model
  - relocated `build_*.py` worked-example rigs to `examples/builders/`

## Earlier history (pre-restructure)
- feat: post-migration report (`q2t report`) — object inventory + review checklist
- feat: automatic warehouse type introspection (`transform.wh_types`)
- feat: two migration skills + Qlik Cloud API adapter
- feat: initial Qlik Sense → ThoughtSpot migration utility (`q2t` extract/transform/load)
