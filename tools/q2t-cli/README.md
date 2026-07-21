# q2t — Qlik → ThoughtSpot migration CLI

The Python engine behind the `ts-convert-from-qlik` and `ts-convert-from-qlik-api`
skills. It moves a Qlik Sense app through four stages around a normalized
intermediate representation (IR):

```
.qvf ──[extract]──► IR (JSON) ──[transform]──► TML ──[load]──► ThoughtSpot
        (4 modes)                 + reports                    (REST API v2)
```

The pipeline is split around the IR so the fragile Qlik side is decoupled from
the ThoughtSpot side — you can run each stage independently and inspect the JSON
IR between them.

## Install

```bash
pip install -e tools/q2t-cli                 # base (requests + PyYAML)
pip install -e "tools/q2t-cli[engine]"       # + websocket-client for --mode engine
pip install -e "tools/q2t-cli[snowflake]"    # + snowflake-connector for wh-type introspection
```

Verify:

```bash
q2t --help
```

## Commands

| Command | Purpose |
|---|---|
| `q2t extract` | Qlik app → IR JSON. `--mode {offline,engine,engine-artifacts,qlik-cloud}` |
| `q2t transform` | IR → TML (table / model / liveboard) + mapping report. `--types <map.json>` for warehouse column types |
| `q2t load` | Import TML into ThoughtSpot via REST v2. `--validate-only` for a dry run; `--import-policy {PARTIAL,ALL_OR_NONE,VALIDATE_ONLY}` |
| `q2t report` | Post-migration report: object inventory + review checklist. `--provenance {SOURCE,INFERRED,MANUAL}` |
| `q2t formulas` | Qlik→TS formula reference. `--lookup <fn>` / `--audit <file>` / `--ir <json>` |
| `q2t migrate` | Run extract → transform → load against a workdir |

## Package layout

```
q2t/
  cli.py                  argparse orchestrator (extract/transform/load/report/formulas/migrate)
  ir.py                   normalized IR — the contract between stages
  extract/                Qlik → IR
    qvf_sqlite.py         .qvf-as-SQLite reader (clean, if applicable)
    qvf_offline.py        best-effort byte-scan fallback (fragments only)
    qlik_engine.py        Qlik Engine JSON-RPC over WebSocket (reliable; needs an engine)
    qlik_cloud.py         Qlik Cloud REST + Engine adapter (SOURCE provenance)
    engine_artifacts.py   ingest JSON from the qvf-engine-extract Node sidecar
  transform/              IR → TML + reports
    to_tml.py             IR → TML (table / model / liveboard)
    expr.py               Qlik expression → ThoughtSpot formula translator
    formula_map.py        formula lookup / classify / audit over data/*.json
    report.py             element-level migration report (provenance + checklist)
    migration_report.py   post-migration object inventory report
    wh_types.py           warehouse column-type introspection (Snowflake)
  load/
    ts_client.py          ThoughtSpot REST v2 client (login, connection, TML import/validate)
  data/                   packaged 199-row Qlik→TS formula map (CSV + JSON)
build_formula_map.py      regenerates q2t/data/ from a source CSV (applies corrections)
```

## Notes on HTTP

Direct `requests` usage lives only inside this CLI (`load/ts_client.py`,
`extract/qlik_cloud.py`) — that is the correct place for it per
`.claude/rules/ts-cli.md`. Skills call the `q2t` command; they never make inline
API calls. `extract/qlik_engine.py` uses `websocket-client` (not HTTP);
`transform/wh_types.py` uses the Snowflake driver (not HTTP).

## Tests

```bash
pytest tools/q2t-cli/tests
```

Unit tests cover the pure functions (formula translation, formula-map lookup,
warehouse type mapping, TML emission, IR round-trip) — no live connection needed.

## Regenerating the formula map

```bash
python tools/q2t-cli/build_formula_map.py [source.csv]
```

Defaults to the packaged CSV (idempotent). Pass a fresh Qlik→TS export to
re-ingest; corrections (`date_diff→diff_days`, `add_years`, `sql_*_op`) and status
tags are re-applied.
