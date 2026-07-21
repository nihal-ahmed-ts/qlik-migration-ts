<!-- currency: thoughtspot — 2026-07 (ThoughtSpot Cloud 26.x) -->

# ThoughtSpot TML Invariants

Rules the ThoughtSpot cluster enforces on import. Both `ts-convert-from-qlik`
and `ts-convert-from-qlik-api` rely on these when emitting table / model /
liveboard TML via `q2t transform` and importing via `q2t load`. They come from
real import failures — violating them causes silent errors or rejected imports.

The TML emitter that must honour these lives in
`tools/q2t-cli/q2t/transform/to_tml.py`.

## Table TML

- **`db_column_name`** — include on every table column, even when it equals
  `name`. Missing `db_column_name` produces columns that don't bind to the
  warehouse.
- **Connection block** — reference by `name:` only. Never put `fqn:` inside a
  `connection:` block in table TML.
- **Column data types must match the warehouse.** Import fails with
  `DataType ... does not match CDW DataType` when a type is wrong (e.g. `DOUBLE`
  for an integer column). Introspect types with
  `q2t.transform.wh_types.fetch_snowflake_types` and pass the resulting
  `{table:{column:ts_type}}` map to `q2t transform --types <map.json>` — do not
  guess types. (NUMBER scale 0 → `INT64`, scale > 0 → `DOUBLE`, etc.)

## Model TML

- **Joins** live in `model_tables[].joins` (join reference target is the table
  `name:` when the model `id:` is absent).
- **Formulas** reference columns as `[Table::COLUMN]` and must surface via a
  `columns[]` entry whose `formula_id:` matches the `formulas[]` `id:`. This
  applies to both ATTRIBUTE and MEASURE formulas.
- **`aggregation:`** belongs in `columns[]` entries only — never inside a
  `formulas[]` entry.
- **Formula cross-references** (`[Other Formula]`) fail on first import — inline
  the expression, or import model structure first (no formulas) then update with
  formulas in a second pass.
- **`guid:`** goes at the document root — never nested inside `table:` or
  `model:`. Omit it on first import.

## Liveboard TML

- Layout uses `tiles`; each viz `answer` needs `answer_columns` + `table` +
  `chart.chart_columns` / `axis_configs` referencing the **aggregated output
  column names**. Verify those names with a live `searchdata` query before
  finalizing each viz — guessed column names render empty tiles.

## Import policy

- Dry-run first: `q2t load --validate-only` (VALIDATE_ONLY).
- Then `--import-policy ALL_OR_NONE` for an atomic import, or `PARTIAL` to import
  what validates and report the rest. Import failures become `NEEDS REVIEW` rows
  in the migration report — never silently dropped.

## Formula translation

Before declaring any Qlik expression untranslatable, consult
[../mappings/qlik/qlik-thoughtspot-formula-translation.md](../mappings/qlik/qlik-thoughtspot-formula-translation.md).
Many Qlik aggregation / conditional / set-analysis constructs have direct
ThoughtSpot equivalents (`group_aggregate`, `sum_if`, `unique count`, …).
