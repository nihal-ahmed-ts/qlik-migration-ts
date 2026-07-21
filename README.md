# qlik-migration-ts

Skills and tooling for migrating **Qlik Sense** apps into **ThoughtSpot**.
Structured to mirror the sibling repo
[`thoughtspot-agent-skills`](https://github.com/thoughtspot/thoughtspot-agent-skills):
guided skills under `agents/cli/`, a shared reference library under
`agents/shared/`, and the migration engine as an installable `q2t` CLI under
`tools/`.

```
.qvf ──[extract]──► IR (JSON) ──[transform]──► TML ──[load]──► ThoughtSpot
        (4 modes)                 + reports                    (REST API v2)
```

The pipeline is split around a normalized **intermediate representation (IR)** so
the fragile Qlik side is decoupled from the ThoughtSpot side — run each stage
independently and inspect the JSON IR between them.

---

## Skills

| Skill | What it does | Coverage | CLI |
|---|---|---|:-:|
| [`ts-convert-from-qlik`](agents/cli/ts-convert-from-qlik/SKILL.md) | Migrate a Qlik app with **no API access** — `.qvf` + dashboard PDF + data model. Data model is SOURCE (from the warehouse); dashboard is inferred from the PDF and flagged. | [coverage](agents/cli/ts-convert-from-qlik/references/coverage-matrix.md) | ✓ |
| [`ts-convert-from-qlik-api`](agents/cli/ts-convert-from-qlik-api/SKILL.md) | Migrate via the **Qlik Cloud API** — tenant + API key + app id. Pulls real definitions (script, model, master items, sheets, charts); SOURCE provenance, minimal guesswork. | [coverage](agents/cli/ts-convert-from-qlik-api/references/coverage-matrix.md) | ✓ |

Both wrap the same `q2t` engine — only the extraction front-end differs.

---

## Object mapping

| Qlik Sense | ThoughtSpot |
|---|---|
| Data connection (`lib://`) | Connection (`connection/create`) |
| Loaded tables | Tables (TML `table`) |
| Master dimension | Model column |
| Master measure | Model formula |
| Variable | Formula / parameter |
| Sheet | Liveboard tab |
| Chart / visualization | Answer (viz) on the Liveboard |
| Load-script ETL | **Manual** — flagged in the report |

Full formula coverage (199 rows):
[agents/shared/mappings/qlik/qlik-thoughtspot-formula-translation.md](agents/shared/mappings/qlik/qlik-thoughtspot-formula-translation.md).
Nothing is silently dropped — unmapped constructs are listed in the migration
report for manual follow-up.

---

## Getting Started

```bash
# Clone
git clone https://github.com/nihal-ahmed-ts/qlik-migration-ts.git ~/qlik-migration-ts

# Install the q2t CLI (Python 3.10–3.14)
pip install -e ~/qlik-migration-ts/tools/q2t-cli
q2t --help

# Symlink the skills into your agent — see agents/cli/SETUP.md for the full list
```

Then run `/ts-convert-from-qlik` (or `/ts-convert-from-qlik-api`) in Claude Code /
Cortex Code. Full install + credential steps: [agents/cli/SETUP.md](agents/cli/SETUP.md).

### CLI usage (standalone)

```bash
q2t extract --qvf App.qvf --out build/app.ir.json --mode offline
q2t transform --ir build/app.ir.json --out build/tml/ --report build/report.md [--types types.json]
q2t load --tml build/tml/ --host "$TS_HOST" --validate-only        # dry run
q2t report --tml build/tml/ --out build/migration_report.md --provenance manual
```

Command reference: [tools/q2t-cli/README.md](tools/q2t-cli/README.md).

---

## Repository Structure

```
qlik-migration-ts/
├── agents/
│   ├── cli/                        Skills (symlinked into ~/.claude/skills/)
│   │   ├── ts-convert-from-qlik/          no-API / manual path
│   │   └── ts-convert-from-qlik-api/      Qlik Cloud API path
│   └── shared/                     Reference files used by both skills
│       ├── mappings/qlik/                 formula translation (199-row map)
│       └── schemas/                       TML invariants + q2t IR contract
├── tools/
│   ├── q2t-cli/                    the `q2t` migration CLI + unit tests
│   ├── validate/                   static validators (naming, versions, refs, secrets)
│   └── smoke-tests/                end-to-end checks over fixtures/
├── scripts/                        pre-commit hook
├── examples/                       Retail demo assets + builders/ (worked-example rigs)
├── fixtures/                       synthetic .qvf files for the extractors
└── qvf-engine-extract/             Node/Docker Qlik Core sidecar (SOURCE-grade JSON dump)
```

---

## Two extraction modes (why)

A `.qvf` is Qlik's **proprietary binary** app format — there is no official offline
parser.

| Mode | Reliability | Needs | Recovers |
|---|---|---|---|
| `qlik-cloud` / `engine` | High | Qlik Cloud API key, or a running engine | Full layout: sheets, charts, master items, variables, connections, load script |
| `engine-artifacts` | High | The `qvf-engine-extract` Docker sidecar's JSON dump | Same, from a headless Qlik Core engine |
| `offline` | Best-effort | Nothing — just the `.qvf` | Load-script text + JSON fragments; charts usually **not** recoverable |

Use an engine/API mode when you can; `offline` is the fallback that honestly
reports what it could and could not recover.

---

## Status & limitations

- The ThoughtSpot **load** side is complete and verified against a live cluster.
- The **offline** extractor under-recovers charts by design — the no-API skill
  reads the dashboard from the PDF and flags every inferred item.
- Chart-type and expression mapping covers the common cases; anything unmapped is
  reported, never guessed. See each skill's `references/coverage-matrix.md`.

## Contributing

Never push to `main` — work on a `feat/*` branch and open a PR. Validators and
unit tests run in pre-commit and CI. See [CLAUDE.md](CLAUDE.md) and
`.claude/rules/`.

## License

[MIT](LICENSE).
