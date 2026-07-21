# qlik-migration-ts

Skills and tooling for migrating **Qlik Sense** apps into **ThoughtSpot**.
Structured to mirror the sibling repo
[`thoughtspot-agent-skills`](https://github.com/thoughtspot/thoughtspot-agent-skills):
skills under `agents/cli/`, a shared reference library under `agents/shared/`, and
the migration engine as an installable CLI under `tools/`.

## Directory map

```
agents/cli/            Skills (Claude Code + Cortex Code CLI); symlinked into ~/.claude/skills/
  ts-convert-from-qlik/       no-API / manual path (PDF + data model)
  ts-convert-from-qlik-api/   Qlik Cloud API path (SOURCE provenance)
agents/shared/         Reference files consumed by BOTH skills
  mappings/qlik/       Qlik → ThoughtSpot formula translation (199-row map)
  schemas/             TML invariants + the q2t IR contract
tools/q2t-cli/         The `q2t` migration CLI (extract/transform/load/report) + tests
tools/validate/        Static validators (naming, versions, references, secrets, …)
tools/smoke-tests/     End-to-end checks over fixtures/
scripts/               pre-commit hook
examples/              Retail demo assets + builders/ (worked-example TML rigs)
qvf-engine-extract/    Node/Docker Qlik Core sidecar (SOURCE-grade JSON dump)
```

## The pipeline

```
.qvf ──[q2t extract]──► IR (JSON) ──[q2t transform]──► TML ──[q2t load]──► ThoughtSpot
        (4 modes)                     + reports                    (REST API v2)
```

The IR (`tools/q2t-cli/q2t/ir.py`) is the contract between the fragile Qlik side
and the ThoughtSpot side — dump it, inspect it, hand-edit it, re-run later stages.

## Change impact map — when you change X, also update Y

| Changed area | Also update |
|---|---|
| Any `SKILL.md` (new command/step) | `README.md` skills table; bump version in that SKILL.md `## Changelog` |
| A `ts-convert-*` skill: new mapped/unmapped construct | `references/coverage-matrix.md` in that skill (validator enforces existence) |
| `q2t` command interface | `tools/q2t-cli/README.md`; any SKILL.md that uses it; bump version in `pyproject.toml` + `q2t/__init__.py`; `CHANGELOG.md` |
| `agents/shared/*` | Both SKILL.md files that reference it; refresh the currency anchor |
| The 199-row formula map | Regenerate `q2t/data/` via `build_formula_map.py`; regenerate `agents/shared/mappings/qlik/qlik-thoughtspot-formula-translation.md` |
| Add a new skill | `README.md`; `agents/cli/SETUP.md`; `tools/smoke-tests/smoke_<skill>.py`; `## Changelog` starting at 1.0.0; `CHANGELOG.md`; **name must match a family in `.claude/rules/skill-naming.md`** |

## Commit + deploy protocol

**Never push directly to `main`.** Every change goes through a PR on a `feat/*`
branch. See `.claude/rules/branching.md`. Claude Code changes take effect
immediately via symlinks; `q2t` changes need `pip install -e tools/q2t-cli`.

## Skills use `q2t`, never inline `requests`

All ThoughtSpot API + Qlik extraction calls go through the `q2t` CLI. Direct HTTP
belongs inside the CLI (`load/ts_client.py`, `extract/qlik_cloud.py`,
`extract/qlik_engine.py`), never in a SKILL.md. See `.claude/rules/ts-cli.md`.

## Critical TML invariants

Read `agents/shared/schemas/thoughtspot-tml-invariants.md` before generating any
TML — these rules come from real import failures (`db_column_name` on every
column, connection by `name:` not `fqn:`, formulas surface via `formula_id`, model
joins in `model_tables[].joins`, warehouse-matched column types).

## Formula classification

Before declaring any Qlik expression untranslatable, read
`agents/shared/mappings/qlik/qlik-thoughtspot-formula-translation.md`. Many Qlik
aggregation / conditional / set-analysis constructs have direct ThoughtSpot
equivalents.

## Rules index (`.claude/rules/`)

`skill-naming` · `content-structure` · `ts-cli` · `security` · `branching` ·
`versioning`.
