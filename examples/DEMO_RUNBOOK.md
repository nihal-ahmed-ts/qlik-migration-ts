# Demo runbook — `ts-convert-from-qlik` (no-API path)

Migrating a Qlik dashboard to ThoughtSpot when the customer has **no Qlik API
access** — just a `.qvf`, a dashboard PDF, and the data model.

## The story (30 sec)

"A customer is moving from Qlik to ThoughtSpot. They can't give us Qlik API
access — all we have is the `.qvf` file, a PDF of the dashboard, and the data
model. Watch us turn that into a live, working ThoughtSpot Liveboard — and we'll
be honest about exactly what's faithful vs. inferred."

## Pre-demo checklist

- [ ] Start a **fresh Claude Code session in the repo** so `/ts-convert-from-qlik` loads.
- [ ] Credentials available: `export TS_USER=… TS_PASS=…` (ThoughtSpot); Snowflake key at its path.
- [ ] Inputs ready in `examples/`: `Retail_Analytics_Dashboard.pdf`, `Retail_Analytics_data_model.md` (the `.qvf` placeholder is in `build/demo_artifacts/`).
- [ ] (For a clean LIVE rebuild) run the reset script first: `python examples/reset_retail_demo.py` — deletes the prior Retail Analytics objects, keeps the connection.
- [ ] Warm fallback ready: the pre-built Liveboard URL (below) in case live import hiccups.

## Live flow (3–5 min)

1. **Show the source.** Open `examples/Retail_Analytics_Dashboard.pdf` — point out the KPIs ($72.4M sales, $25.9M profit, 330K units), the regional/category/channel charts, the country map, the pivot.
2. **Invoke the skill.** Type `/ts-convert-from-qlik` (or "migrate this Qlik dashboard, I have the PDF and data model"). It **asks for the inputs** — hand it the `.qvf`, PDF, data model, ThoughtSpot host, connection + `DB_CASESTUDY.QLIKMIG_DEMO`.
3. **Narrate what it does:**
   - offline `.qvf` scan → recovers ~nothing ("the binary won't give it up — that's expected")
   - introspects Snowflake → exact tables, columns, **and types** (no guessing)
   - reads the PDF → the charts/measures
   - builds TML → `VALIDATE_ONLY` → import
4. **Reveal the result.** Open the new Liveboard — 14 vizzes, Region/Date/Channel filters, the country map.

## The "wow" moments to land

- **Numbers match the source to the dollar** — Total Sales `$72,396,375` = the PDF's $72.4M.
- **Conformed joins across 2 fact tables** (Sales + Returns) + 6 dims, built automatically.
- **Honest provenance** — the report marks the **data model as SOURCE** and **charts as INFERRED (verify)**: the tool never silently guesses.
- **Two paths** — this is the no-API fallback; the `ts-convert-from-qlik-api` skill does the same faithfully from the Qlik Cloud API (built; runs on an API-enabled tenant).

## Showpiece / fallback Liveboard

https://ps-internal.thoughtspot.cloud/#/pinboard/4b70fc4d-eeef-4f3f-bbdb-df6f8d03d288

## Reset (make the demo repeatable)

```bash
export TS_USER=… TS_PASS=…
python examples/reset_retail_demo.py        # deletes liveboard + model + QM_ tables, keeps connection
# then re-run the skill, or the scripts:
python build_demo.py && python build_demo_liveboard.py
```

## Likely questions

- *"Is the `.qvf` really parsed?"* — No; the binary is proprietary. The dashboard
  comes from the PDF, the model from the warehouse. That's the honest limit of
  the no-API path — and why the API path exists.
- *"What needs manual review?"* — Whatever the report flags: inferred chart
  mappings, ambiguous measures (e.g. a custom Profit Margin definition),
  filters/formatting not visible in a static PDF.
