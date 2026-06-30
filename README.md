# Qlik Sense → ThoughtSpot migration utility

A pipeline that migrates Qlik Sense apps into ThoughtSpot.

```
.qvf ──[Extract]──► IR (JSON) ──[Transform]──► TML ──[Load]──► ThoughtSpot
        (2 modes)                  + mapping report           (REST API v2)
```

The pipeline is deliberately split around a **normalized intermediate
representation (IR)** so the fragile Qlik side is decoupled from the
ThoughtSpot side. You can run the stages independently and inspect the
JSON IR between them.

## Why two extraction modes?

A `.qvf` is Qlik's **proprietary binary** app format. The sheets, charts,
master items, variables and load script live inside it in a compressed
binary serialization — there is **no official offline parser**.

| Mode | Reliability | Needs | Recovers |
|------|-------------|-------|----------|
| `engine` | High (recommended) | A running Qlik engine (Desktop/Enterprise/Cloud) with the app open | Full app layout: sheets, charts, master items, dimensions, measures, variables, data connections, load script |
| `offline` | Best-effort / experimental | Nothing — just the `.qvf` file | Whatever can be salvaged from the raw bytes: load-script text and any embedded JSON layout fragments. Charts are usually **not** reliably recoverable offline. |

Use `engine` whenever you can. `offline` exists for when you only have the
file and no live Qlik environment — it tells you honestly what it could and
could not recover.

## Object mapping

| Qlik Sense | ThoughtSpot |
|------------|-------------|
| Data connection (lib://) | Connection (`connection/create`) |
| Loaded tables | Tables (TML `table`) |
| Master dimension | Worksheet column |
| Master measure | Worksheet formula |
| Variable | Worksheet formula / parameter |
| Sheet | Liveboard tab |
| Chart / visualization | Answer (viz) on the Liveboard |
| Load-script transforms | **Manual** — flagged in the report |

Qlik's load-script ETL and many chart expressions have no 1:1 ThoughtSpot
equivalent. Those are never silently dropped — they are listed in the
**mapping report** (`report.md` / `report.json`) for manual follow-up.

## Install

```bash
cd qlik-to-thoughtspot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
# 1. Extract a .qvf to IR JSON. Pick an extraction mode:
python -m q2t extract --qvf path/to/App.qvf --out build/app.ir.json --mode offline      # best-effort (no engine)
python -m q2t extract --artifacts output/   --out build/app.ir.json --mode engine-artifacts  # JSON from a Qlik engine
python -m q2t extract --tenant https://t.us.qlikcloud.com --app-id <guid> \
    --out build/app.ir.json --mode qlik-cloud   # Qlik Cloud API (foolproof; needs API key)
python -m q2t extract --app-id <guid> --engine wss://qlik-host:4747/app/ \
    --out build/app.ir.json --mode engine       # direct engine ws URL

# 2. Transform IR -> TML + mapping report
#    (optional --types: a {table:{column:ts_type}} map from wh_types.fetch_snowflake_types,
#     so column data types come from the warehouse instead of being guessed)
python -m q2t transform --ir build/app.ir.json --out build/tml/ --report build/report.md \
    [--types build/types.json]

# 3. Load TML into ThoughtSpot (review the report first!)
export TS_HOST=https://your-instance.thoughtspot.cloud
export TS_USER=... TS_PASS=...
python -m q2t load --tml build/tml/ --host $TS_HOST

# Or run all three at once
python -m q2t migrate --qvf path/to/App.qvf --host $TS_HOST
```

## Claude Code skills

Two guided skills wrap the CLI (in `.claude/skills/`). Invoke inside Claude Code
with `/<name>` or by describing the task; each asks for the inputs it needs.

| Skill | Path | When to use |
|-------|------|-------------|
| `ts-convert-from-qlik` | no-API / manual | You have a `.qvf` + dashboard PDF + data model, but no Qlik API. Data model is faithful; dashboard is inferred and flagged. |
| `ts-convert-from-qlik-api` | Qlik Cloud API | You have a Qlik Cloud tenant + API key. Foolproof, low-guesswork (SOURCE provenance). |

Both call the same `q2t` core — only the extraction front-end differs.

## Project layout

```
q2t/                        the migration package (installable, importable)
  cli.py                    orchestrator: extract / transform / load / migrate / formulas
  ir.py                     normalized intermediate representation (the contract between stages)
  extract/                  Qlik -> IR
    __init__.py             dispatcher: try SQLite first, fall back to byte-scan
    qvf_sqlite.py           reads a .qvf as a SQLite DB (clean, if applicable)
    qvf_offline.py          best-effort byte-scan of a raw .qvf (fragments only)
    qlik_engine.py          Qlik Engine JSON-RPC extractor (reliable; needs a running engine)
  transform/                IR -> TML + reports
    to_tml.py               IR -> TML (table / model / liveboard)
    expr.py                 Qlik expression -> ThoughtSpot formula translator
    formula_map.py          formula-mapping sub-utility: lookup / classify / audit
    report.py               element-level migration report (provenance + review checklist)
  load/
    ts_client.py            ThoughtSpot REST v2 client (login, create connection, TML import/validate)
  data/                     packaged reference data
    qlik_ts_formula_map.csv / .json   the 199-row Qlik->TS formula map (corrected)
build_live.py               builder for a specific live migration's TML (worked example)
build_formula_map.py        regenerates q2t/data/ from the source CSV (applies corrections)
fixtures/                   synthetic .qvf files for testing the extractors
README.md / requirements.txt / .gitignore
```

## What each part does

**`q2t/` — the package.** The whole migration tool, run as `python -m q2t <command>`.
It moves a Qlik app through four stages around a shared IR:
- **extract** — turn a `.qvf` (or a live Qlik engine) into the normalized `ir.py`
  representation. Three modes: `qlik_engine` (reliable, needs an engine), `qvf_sqlite`
  (clean if the file is a SQLite DB), `qvf_offline` (best-effort byte-scan fallback).
- **transform** — `to_tml.py` turns the IR into ThoughtSpot TML (tables, model,
  liveboard); `expr.py` translates Qlik formulas; `report.py` writes the migration report.
- **load** — `ts_client.py` logs in, creates the connection, and imports/validates the TML.
- **formula_map** — the formula reference + coverage audit (see below).

**`q2t/data/` — the corrected 199-row formula mapping (CSV + JSON).** The canonical
Qlik→ThoughtSpot formula reference, every row tagged `ok` / `corrected` / `verify`.
Consumed by `formula_map.py` for `q2t formulas --lookup <fn>` (find a function's
equivalent) and `--audit` (report how much of an app's formula surface converts
cleanly vs. needs manual work). The CSV is human-editable; the JSON is what the code loads.

**`build_live.py`, `build_formula_map.py` — the builders.**
- `build_formula_map.py` regenerates `q2t/data/` from the source CSV, applying the
  verified corrections (`date_diff→diff_days`, `add_years`, `sql_*_op`) and the
  status tags. Re-run it whenever the source mapping changes.
- `build_live.py` is a worked example: it hand-builds the exact table/model/liveboard
  TML for a real migrated dashboard against a known star schema — useful as a
  reference for the precise TML shape the cluster accepts.

**`fixtures/` — synthetic test `.qvf`s.** Small, hand-made `.qvf` files
(`RetailDemo.qvf`, `SqliteApp.qvf`) used to exercise the extractors without needing
a real Qlik app — one mimics the SQLite layout, one is opaque binary for the
byte-scan path.

**`README.md` / `requirements.txt` / `.gitignore`.** Docs; Python dependencies
(`requests`, `PyYAML`, optional `websocket-client` for engine mode); and the ignore
rules that keep secrets, the venv, and build output out of git.

## Status & limitations

- The ThoughtSpot **Load** side is complete and verified against a live cluster.
- The **offline** extractor is best-effort and will under-recover charts.
- Chart-type and expression mapping covers the common cases; anything
  unmapped is reported, never guessed.
