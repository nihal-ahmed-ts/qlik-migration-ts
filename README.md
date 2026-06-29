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
# 1. Extract a .qvf to IR JSON (offline best-effort)
python -m q2t extract --qvf path/to/App.qvf --out build/app.ir.json --mode offline

#    ...or via a running Qlik engine (recommended)
python -m q2t extract --app-id <guid> --engine wss://qlik-host:4747/app/ \
    --out build/app.ir.json --mode engine

# 2. Transform IR -> TML + mapping report
python -m q2t transform --ir build/app.ir.json --out build/tml/ --report build/report.md

# 3. Load TML into ThoughtSpot (review the report first!)
export TS_HOST=https://your-instance.thoughtspot.cloud
export TS_USER=... TS_PASS=...
python -m q2t load --tml build/tml/ --host $TS_HOST

# Or run all three at once
python -m q2t migrate --qvf path/to/App.qvf --host $TS_HOST
```

## Project layout

```
q2t/
  ir.py              normalized intermediate representation (the contract)
  extract/
    qvf_offline.py   best-effort offline .qvf scanner
    qlik_engine.py   Qlik Engine JSON-RPC extractor (recommended)
  transform/
    to_tml.py        IR -> TML (table / worksheet / liveboard)
    report.py        mapping report (what mapped, what needs manual work)
  load/
    ts_client.py     ThoughtSpot REST v2 client (login, connection, TML import)
  cli.py             orchestrator (extract / transform / load / migrate)
```

## Status & limitations

- The ThoughtSpot **Load** side is complete and verified against a live cluster.
- The **offline** extractor is best-effort and will under-recover charts.
- Chart-type and expression mapping covers the common cases; anything
  unmapped is reported, never guessed.
