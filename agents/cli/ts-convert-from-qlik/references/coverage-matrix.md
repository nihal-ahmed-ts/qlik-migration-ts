# Coverage Matrix: Qlik Sense → ThoughtSpot (no-API / manual path)

What the `ts-convert-from-qlik` skill maps and what it does not. Use this as the
canonical limitations reference. Formula-level coverage is in
[../../../shared/mappings/qlik/qlik-thoughtspot-formula-translation.md](../../../shared/mappings/qlik/qlik-thoughtspot-formula-translation.md)
(199 rows). TML rules are in
[../../../shared/schemas/thoughtspot-tml-invariants.md](../../../shared/schemas/thoughtspot-tml-invariants.md).

**Provenance on this path:** data model = **SOURCE** (read from the warehouse);
dashboard layer = **INFERRED** from the PDF (every inferred item is flagged).

---

## Mapped Constructs

### Structure and schema

| # | Qlik Sense | ThoughtSpot | Notes |
|---|---|---|---|
| 1 | Data connection (`lib://`) | Connection (`connection/create`) | Type mapped via `QLIK_TO_TS_WAREHOUSE`; credentials supplied at load, never from the `.qvf` |
| 2 | Loaded table | Table TML (`table`) | One Table TML per model table; `db_column_name` on every column (I-table) |
| 3 | Table field / column | Table column | Data type from warehouse introspection (`--types`), never guessed |
| 4 | Table associations | Model joins (`model_tables[].joins`) | Join keys confirmed from the data model / warehouse |

### Semantics

| # | Qlik Sense | ThoughtSpot | Notes |
|---|---|---|---|
| 5 | Master dimension | Model column (ATTRIBUTE) | Calculated dimensions → formula column |
| 6 | Master measure | Model formula (MEASURE) | Expression translated via the 199-row map |
| 7 | Variable | Formula / parameter | Simple substitutions → formula; user-input → parameter |
| 8 | Aggregation / conditional-aggregation expressions | ThoughtSpot formulas | `Sum`→`sum`, `Sum(If(...))`→`sum_if`, `Count(DISTINCT)`→`unique count`, `TOTAL`→`group_aggregate`, … |

### Dashboard (inferred from PDF)

| # | Qlik Sense | ThoughtSpot | Notes |
|---|---|---|---|
| 9 | Sheet | Liveboard tab | |
| 10 | Chart / visualization | Answer (viz) on the Liveboard | Chart-type mapped; aggregated output column names verified via live `searchdata` |
| 11 | KPI / text tiles | Note tile / KPI viz | |
| 12 | Sheet filters | Liveboard filters | Only those visible in the static export — flagged as INFERRED |

---

## Unmapped Constructs (Limitations)

| # | Qlik Sense | Limitation | Workaround |
|---|---|---|---|
| L1 | Load-script ETL (`LOAD`, `SQL SELECT`, resident/joins, `ApplyMap`) | No 1:1 ThoughtSpot equivalent — transforms happen in the warehouse, not in TML | Flagged **MANUAL** in the report; replicate in the warehouse or a ThoughtSpot SQL view |
| L2 | Set analysis (`{<Year={2024}>}`) | Only common patterns translate; complex set modifiers have no direct equivalent | `verify`/NEEDS REVIEW row in the report; translate by hand |
| L3 | `Mode()`, `Only()` | No built-in ThoughtSpot equivalent | Flagged; approximate or drop with a note |
| L4 | Charts not visible in the PDF | Static export can't reveal hidden/scrolled vizzes or drill states | Skill asks the user; missing vizzes are NEEDS REVIEW |
| L5 | Section access / RLS | Qlik section access is not read on this path | Configure ThoughtSpot RLS manually post-migration |
| L6 | Alternate states, bookmarks, stories | No ThoughtSpot equivalent | Not migrated; noted in the report |
| L7 | `verify`-tagged formulas (3 rows: `strpos`/`exp`/`date_trunc`) | Mapping unconfirmed against docs | Treat as NEEDS REVIEW until verified on a live cluster |

Nothing is silently dropped — every source object appears in the migration
report with a status of `Migrated` · `Approximated` · `NEEDS REVIEW` · `Skipped`.
