# Open Items: ts-convert-from-qlik

For a full mapping of what IS supported, see [coverage-matrix.md](coverage-matrix.md).

---

## #1 — Offline extractor under-recovers charts — KNOWN (by design)

`q2t extract --mode offline` byte-scans the proprietary `.qvf` binary and
recovers only load-script text and stray JSON fragments — it reports **0 charts**
on most apps. This is expected on the no-API path: the dashboard comes from the
PDF, not the binary.

**Workaround:** the skill reads the dashboard from the PDF/screenshots (Step 4)
and flags every inferred viz. For exact chart definitions, use
`ts-convert-from-qlik-api` (Qlik Cloud API) instead.

Status: KNOWN — inherent to the offline path; not a bug.

---

## #2 — Set-analysis translation is partial — PARTIAL (MEDIUM)

`transform/expr.py` handles common set-analysis patterns (`{<Field={val}>}`) but
not complex modifiers (`P()`/`E()` set functions, nested set expressions,
element-function operators).

**Workaround:** untranslatable set expressions are emitted as NEEDS REVIEW rows
with the original Qlik expression preserved, for hand-translation.

Status: PARTIAL — extend `expr.py` `FUNCTION_MAP` / set-analysis handling as new
patterns are verified against a live cluster.

---

## #3 — `verify`-tagged formula rows unconfirmed — NEEDS VERIFICATION (LOW)

Three rows in the formula map carry status `verify` (`strpos`, `exp`,
`date_trunc`) — their ThoughtSpot equivalents could not be confirmed against the
(truncated) formula-reference docs when the map was built.

**Workaround:** the skill surfaces these as NEEDS REVIEW. Verify each against a
live ThoughtSpot cluster, then re-tag the row `ok` in the source CSV and re-run
`build_formula_map.py`.

Status: NEEDS VERIFICATION — LOW (3 of 199 rows).

---

## #4 — Warehouse type introspection is Snowflake-only — PARTIAL (LOW)

`transform/wh_types.py` introspects column types from Snowflake
(`INFORMATION_SCHEMA.COLUMNS`) only. Other warehouses (BigQuery, Databricks,
Redshift) have no `fetch_*_types` helper yet.

**Workaround:** supply a hand-built `{table:{column:ts_type}}` map to
`transform --types <map.json>`; the skill does not require live introspection.

Status: PARTIAL — add per-warehouse helpers as needed; the `--types` override
already covers every warehouse.
