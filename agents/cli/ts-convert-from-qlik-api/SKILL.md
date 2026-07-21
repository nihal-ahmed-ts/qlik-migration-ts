---
name: ts-convert-from-qlik-api
description: >-
  Migrate a Qlik Sense app to ThoughtSpot using the QLIK CLOUD API — the
  foolproof, low-guesswork path. Use when the user HAS Qlik Cloud access: a
  tenant URL + API key + app id. Pulls the app's real definitions (script,
  data model, master items, sheets, charts) via the Qlik Cloud REST + Engine
  APIs, then generates ThoughtSpot TML (connection, tables, model, liveboard)
  and imports it. No PDF, no guessing. Triggers: "migrate Qlik via API",
  "I have a Qlik Cloud API key", "convert Qlik app using the API",
  "Qlik tenant + app id to ThoughtSpot".
---

# Qlik → ThoughtSpot (Qlik Cloud API path)

The **foolproof path**: definitions come straight from the Qlik engine, so the
extraction is exact (SOURCE provenance) — no PDF, minimal guesswork. The only
judgment left is the ThoughtSpot translation (expression → formula, chart-type
fallbacks), which the formula map + report flag rather than guess.

For the no-API / manual path (PDF + data model), use `ts-convert-from-qlik`.

The engine is the `q2t` CLI (`pip install -e "tools/q2t-cli[engine]"` — the
`engine` extra adds `websocket-client` for the Qlik Engine API; see
[agents/cli/SETUP.md](../SETUP.md)). All ThoughtSpot API calls go through `q2t`;
never make inline `requests` calls from this skill.

## References

| File | Purpose |
|---|---|
| [../../shared/mappings/qlik/qlik-thoughtspot-formula-translation.md](../../shared/mappings/qlik/qlik-thoughtspot-formula-translation.md) | Qlik → ThoughtSpot formula translation (199-row map). Consult before declaring any expression untranslatable. |
| [../../shared/schemas/thoughtspot-tml-invariants.md](../../shared/schemas/thoughtspot-tml-invariants.md) | TML rules the cluster enforces on import (table / model / liveboard) |
| [../../shared/schemas/qlik-app-ir.md](../../shared/schemas/qlik-app-ir.md) | The IR contract between extract and transform |
| [references/coverage-matrix.md](references/coverage-matrix.md) | What this skill maps and what it does not |
| [references/open-items.md](references/open-items.md) | Known gaps and deferred capabilities |
| [../ts-convert-from-qlik/references/migration-report-format.md](../ts-convert-from-qlik/references/migration-report-format.md) | Required migration-report format (shared with the manual skill) |

## Step 1 — Ask the user for these inputs

1. **Qlik Cloud tenant URL** — e.g. `https://your-tenant.us.qlikcloud.com`.
2. **Qlik Cloud API key** — a tenant API key (needs the Developer role to
   generate). Accept it via `QLIK_API_KEY` env var; treat it as sensitive,
   never commit it, and tell the user to revoke it after.
3. **App** — the app GUID (or its name; the adapter resolves a name to a GUID).
4. **ThoughtSpot host** + auth, and target **org** if not Primary.
5. **Connection mapping** — which ThoughtSpot connection the tables should use
   (existing or to create), and the **database/schema** of the physical tables.
   The adapter pulls Qlik data connections to help, but the physical warehouse
   mapping may still need confirming.

## Step 2 — Extract from Qlik Cloud (SOURCE)

```bash
export QLIK_API_KEY=<key>
q2t extract --mode qlik-cloud \
  --tenant "https://<tenant>.<region>.qlikcloud.com" \
  --app-id "<app-guid-or-name>" \
  --out build/app.ir.json
```

This uses the Cloud REST API (resolve app + data connections) and the Engine
API over `wss` to read the full layout into the IR. Charts carry their real
inline expressions, and table associations become join hints.

## Step 3 — Map to the warehouse

The Qlik data model gives field names; ThoughtSpot needs the **physical
warehouse tables**. Use the pulled data connections + load script to identify
them, or introspect the target warehouse to confirm exact tables/columns.

**Introspect column types — do not guess them** (TML import rejects type
mismatches). Use `q2t.transform.wh_types.fetch_snowflake_types` to build a
`{table:{column:ts_type}}` map and pass it to `transform --types <map.json>`.

## Step 4 — Transform → validate → import

```bash
q2t transform --ir build/app.ir.json --out build/tml/ --report build/report.md
q2t load --tml build/tml/ --host <TS_HOST> --validate-only
q2t load --tml build/tml/ --host <TS_HOST> --import-policy ALL_OR_NONE
```

Same TML invariants as the manual skill (model joins, `[Table::COLUMN]`
formulas + `formula_id`, `tiles` layout, render-ready viz `answer` blocks with
aggregated output column names verified via `searchdata`).

## Step 5 — Verify + generate the migration report

Confirm each viz renders, then **generate the migration report**:

```bash
q2t report --tml build/tml/ --out build/migration_report.md \
    --provenance api --app-name "<app>" \
    --target "<host> / <connection> / <db>.<schema>"
```

It lists every migrated object (connections, tables, columns, joins, formulas,
model, liveboard vizzes, filters, maps) + a review checklist. Because extraction
was via the API, provenance is **SOURCE** — so the checklist focuses on
ThoughtSpot-side translation items (untranslatable formulas, unsupported chart
types) and import failures, not inference.

## Prerequisites & notes

- Requires Qlik Cloud API access; **trial tenants often cannot generate API
  keys** (no Developer role) — if so, fall back to `ts-convert-from-qlik`.
- `pip install -e "tools/q2t-cli[engine]"` (the `engine` extra pulls
  `websocket-client` for the Qlik Engine API).
- Never commit the API key or ThoughtSpot credentials.

---

## Changelog

| Version | Date | Summary |
|---|---|---|
| 1.0.0 | 2026-07-21 | Initial release under `agents/cli/` — Qlik Cloud API (SOURCE-provenance) migration path (renamed from `qlik-to-thoughtspot-api`; engine invoked via the installed `q2t` CLI). |
