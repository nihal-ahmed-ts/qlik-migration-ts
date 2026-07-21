# Coverage Matrix: Qlik Sense → ThoughtSpot (Qlik Cloud API path)

What the `ts-convert-from-qlik-api` skill maps and what it does not.

This path shares the **construct-level** mapping (structure, semantics, formula
translation, TML rules) with the manual path — see
[../../ts-convert-from-qlik/references/coverage-matrix.md](../../ts-convert-from-qlik/references/coverage-matrix.md),
[../../../shared/mappings/qlik/qlik-thoughtspot-formula-translation.md](../../../shared/mappings/qlik/qlik-thoughtspot-formula-translation.md),
and [../../../shared/schemas/thoughtspot-tml-invariants.md](../../../shared/schemas/thoughtspot-tml-invariants.md).

The difference is **extraction fidelity**: definitions come straight from the
Qlik engine, so the whole app — including charts — is **SOURCE** provenance, not
inferred. No PDF, no guessing about the dashboard.

---

## Extraction coverage (Qlik Cloud API)

| # | Qlik source | Recovered | How |
|---|---|---|---|
| 1 | App resolution (id or name) | GUID + metadata | Cloud REST `GET /items` |
| 2 | Data connections | Name + type + properties | Cloud REST `GET /data-connections` (→ `QLIK_TO_TS_WAREHOUSE`) |
| 3 | Load script | Full text | Engine API (`wss`) `getScript` |
| 4 | Data model tables + fields | Tables, columns, associations | Engine API layout |
| 5 | Master dimensions | Label + fields + expression | Engine API `qDimensionList` |
| 6 | Master measures | Label + expression + format | Engine API `qMeasureList` |
| 7 | Variables | Name + definition | Engine API `qVariableList` |
| 8 | Sheets | Tabs | Engine API `qAppObjectList` |
| 9 | Charts / visualizations | Type + dims + measures + **inline expressions** | Engine API `getLayout` per object |

Because charts carry their real inline expressions, chart-to-answer mapping is
exact; the only judgment left is the ThoughtSpot **translation** (expression →
formula, chart-type fallbacks), which the formula map + report flag rather than
guess.

---

## Unmapped / limitations

Inherits the construct-level limitations from the manual path (L1 load-script
ETL, L2 set analysis, L3 `Mode`/`Only`, L5 section access, L6 alternate
states/bookmarks/stories, L7 `verify`-tagged formulas). API-path-specific:

| # | Item | Limitation | Workaround |
|---|---|---|---|
| A1 | Trial tenants | Often cannot generate an API key (no Developer role) | Fall back to `ts-convert-from-qlik` (manual path) |
| A2 | Physical warehouse mapping | The Qlik data connection names the source, but the ThoughtSpot connection + `db.schema` of the physical tables may still need confirming | Skill asks the user; introspect the target warehouse to confirm |
| A3 | Engine API dependency | Requires the `engine` extra (`websocket-client`) and a reachable Qlik Engine over `wss` | `pip install -e "tools/q2t-cli[engine]"` |

Nothing is silently dropped — every source object appears in the migration
report with a status of `Migrated` · `Approximated` · `NEEDS REVIEW` · `Skipped`.
Provenance on this path is **SOURCE**, so the review checklist focuses on
ThoughtSpot-side translation and import failures, not inference.
