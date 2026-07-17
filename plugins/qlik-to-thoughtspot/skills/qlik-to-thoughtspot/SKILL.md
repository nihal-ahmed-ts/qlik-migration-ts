---
name: qlik-to-thoughtspot
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
silently guessed. For the foolproof path, use `qlik-to-thoughtspot-api`.

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

## Step 6 — Verify + generate the migration report

Confirm each viz renders (live `searchdata` / `liveboard/sql`), then **always
generate the migration report** — this is a required final deliverable of every
migration, not optional. Write it to `migration_report.md` and hand it to the user.

`python -m q2t report ...` can emit a starting inventory, but the deliverable must
follow the **full report format** below (see the template at
`references/migration-report-format.md`). Fill every section from the actual
migration; do not omit sections.

**Required sections, in order:**

1. **Title + header** — `# Qlik → ThoughtSpot migration report`, then **Source**,
   **Generated** (absolute date), **Target** (`host / connection / db.schema`), and
   **Provenance** (`data model = SOURCE, charts = INFERRED (verify)`).
2. **Executive summary** — Migration complexity (Low/Medium/High); Automation % |
   Manual %; Estimated effort; Risk score with a one-line reason.
3. **Inventory** — Tables | Columns; Relationships | Measures; Sheets | Visuals.
4. **Modernization** — Dashboards eliminated; merged; Search opportunities; Spotter
   opportunities; Semantic improvements (bullets).
5. **Summary by object type** — table: `Object type | In Qlik | Migrated |
   Approximated | Needs review | Skipped`, one row per object type, counts must add up.
6. **Data model** — three tables: **Tables** (`Table | Status | Note`),
   **Relationships → joins** (`Relationship | Status | Note`), **Measures → formulas**
   (`Measure | Complexity | Qlik expression | ThoughtSpot formula | Confidence |
   Status | Note`).
7. **Report / visuals → answers & liveboards** — **Sheet → liveboard**
   (`Sheet | Visual | ThoughtSpot chart | Status | Note`, one row per visual incl.
   note tiles & filters) and a **decision** table (`Sheet | Decision | Liveboard |
   Status`).
8. **Manual review** — bulleted, every NEEDS REVIEW / Approximated item with what
   the human must confirm.
9. **Verification checklist** — checkboxes; tick the ones you verified live (e.g.
   a known total that matches the source), leave the rest unchecked for the user.
10. **ThoughtSpot Modernization Scorecard** — table `Category | Score | Recommendation`
    for Semantic Model, Search Readiness, Spotter Readiness, Liveboards, AI Readiness.

**Status vocabulary (use exactly):** `Migrated` · `Approximated` · `NEEDS REVIEW` ·
`Skipped`. Never silently drop anything — every source object appears in a table with
one of these statuses. Provenance stays **data model = SOURCE, charts = INFERRED
(verify)**; import failures are `NEEDS REVIEW` must-fix rows.

## Principles

- **Never silently drop** anything — unmapped constructs go in the report.
- **Surface, recommend, resolve** ambiguous items with the user.
- **Validate before importing.** Treat credentials as sensitive; never commit them.
