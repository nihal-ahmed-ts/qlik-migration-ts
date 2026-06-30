---
name: ts-convert-from-qlik
description: >-
  Migrate a Qlik Sense dashboard to ThoughtSpot WITHOUT Qlik API access — the
  manual / no-API path. Use when the user has a .qvf file plus a dashboard
  PDF/screenshot and the Qlik data model (e.g. data model viewer), but no Qlik
  Cloud API key or live engine. Reads the dashboard from the PDF and the model
  from the warehouse, then generates ThoughtSpot TML (connection refs, tables,
  model, liveboard) and imports it. Inferred items are flagged for review.
  Triggers: "migrate this Qlik dashboard", "convert .qvf to ThoughtSpot",
  "no Qlik API", "I have a PDF and the data model".
---

# Qlik → ThoughtSpot (no-API / manual path)

This is the **fallback path** for when there's no Qlik API/engine access. It is
faithful for the **data model** (read from the warehouse) but the **dashboard
layer is inferred** from the PDF — so every inferred item is flagged, never
silently guessed. For the foolproof path, use `ts-convert-from-qlik-api`.

The engine is the `q2t` CLI in this repo. Run it from the repo root with the
project venv active (`source .venv/bin/activate`).

## Step 1 — Ask the user for these inputs

Ask for (and wait for) all of the following before doing anything:

1. **`.qvf` file path** — the source app (used for offline fragments + record).
2. **Dashboard PDF or screenshots** — the source of chart definitions
   (titles, chart types, the dimensions/measures each viz shows, layout).
3. **Qlik data model** — the data model viewer screenshot, OR a table/field
   list, OR the load script. (Confirms tables, fields, and joins.)
4. **ThoughtSpot host** + auth (username/password or token), and the **target
   org** if not Primary.
5. **Target connection** — name of an existing ThoughtSpot connection to reuse,
   OR warehouse credentials + type to create one. Plus the **database/schema**
   where the physical tables live.

## Step 2 — Extract what the binary will give (expect little)

```bash
python -m q2t extract --qvf "<path>" --out build/app.ir.json --mode offline
```

`.qvf` is proprietary binary; offline recovers only fragments (it will report
0 charts). This is expected — the dashboard comes from the PDF.

## Step 3 — Recover the real data model (source-of-truth)

Introspect the **target warehouse** for exact tables/columns (the reliable
source for the model), or use the provided data model. Identify the
fact/dimension tables and the join keys.

**Introspect column types — do not guess them.** TML import fails with
`DataType ... does not match CDW DataType` if a column type is wrong (e.g.
DOUBLE for an integer column). Use `q2t.transform.wh_types.fetch_snowflake_types`
to build a `{table:{column:ts_type}}` map (NUMBER scale 0 → INT64, scale > 0 →
DOUBLE, etc.), save it as JSON, and pass it to `transform --types <map.json>`.

## Step 4 — Read the dashboard from the PDF (inferred)

From the PDF/screenshots, enumerate each viz: title, chart type, the
dimension(s) and measure(s) shown, and layout. Map chart types and measure
expressions to ThoughtSpot. **Flag** anything ambiguous (custom formulas,
unsupported charts, filters not visible in a static export) — confirm with the
user rather than guessing.

## Step 5 — Build IR → TML, validate, import

Assemble the IR (tables + joins + measures + sheets/charts), then:

```bash
python -m q2t transform --ir build/app.ir.json --out build/tml/ --report build/report.md
# review build/report.md, ensure the connection exists on the cluster, then:
python -m q2t load --tml build/tml/ --host <TS_HOST> --validate-only   # dry run
python -m q2t load --tml build/tml/ --host <TS_HOST> --import-policy ALL_OR_NONE
```

Use TML invariants the cluster enforces: model joins in `model_tables[].joins`;
formulas reference `[Table::COLUMN]` and surface via `formula_id`; liveboard
layout uses `tiles`; viz `answer` needs `answer_columns` + `table` +
`chart.chart_columns`/`axis_configs` with the **aggregated output column names**
(verify them with a live `searchdata` query before finalizing each viz).

## Step 6 — Verify + report

Confirm each viz renders (live query / liveboard SQL) and hand the user the
element-level report — with provenance: **data model = SOURCE, charts =
INFERRED (verify)** — plus the human-review checklist.

## Principles

- **Never silently drop** anything — unmapped constructs go in the report.
- **Surface, recommend, resolve** ambiguous items with the user.
- **Validate before importing.** Treat credentials as sensitive; never commit them.
