# QVF Extractor (headless Qlik engine)

Extracts the load script, data model, master items, sheets, and chart
definitions from a `.qvf` file by loading it into a Qlik **engine** and
querying it with the Engine API (QIX) via `enigma.js`. Its `output/` folder
feeds straight into `q2t`.

> ## ⚠️ Read first: the Qlik Core Docker images no longer work
>
> The original design targeted **Qlik Core** (`qlikcore/engine` on Docker Hub).
> **Qlik Core is end-of-life.** Every public image hard-expires on a built-in
> date and now fails at startup with `This engine has expired` (QIX error
> `12001`, License error) — `AcceptEULA=yes` is not enough, and Qlik no longer
> issues the license that would unblock it. **Do not spend time on the Docker
> path; it cannot run today.**
>
> **Use a real engine instead** — this same extractor works against either,
> just point `ENGINE_HOST`/`ENGINE_PORT` (and the ws path) at it:
>
> | Engine | How | Notes |
> |--------|-----|-------|
> | **Qlik Cloud** (paid tenant, Developer role) | `q2t extract --mode engine` (no Node needed) | best fit; API key required — trial tenants block this |
> | **Qlik Sense Desktop** (free, **Windows only**) | run this extractor at `ENGINE_PORT=4848` (`ws://localhost:4848/app/<name>`) | open the app in Desktop first |
> | Qlik Core (licensed) | the Docker steps below | only if you have a valid, unexpired Qlik Core license |
>
> The `q2t` ingest side (`--mode engine-artifacts`) is fully working and is
> validated against sample artifacts — so the instant *any* live engine
> produces `output/`, the rest of the migration runs end-to-end.

This produces no-account extraction **only if you have a licensed engine**.
Its `output/` folder feeds straight into `q2t`:

```bash
python -m q2t extract --mode engine-artifacts --artifacts output/ --out app.ir.json
```

## Prerequisites

- Docker + Docker Compose
- Node.js 18+ (ESM, `fs/promises`)
- Your `.qvf` files

## Step 1 — Place your QVF files

```bash
mkdir -p apps
cp /path/to/MyApp.qvf apps/
```

The `apps/` folder is mounted into the engine at `/apps`.

## Step 2 — Start the headless engine

```bash
docker compose up -d
docker compose logs -f qix-engine   # wait for the engine to report started
```

Runs Qlik Core's engine on `ws://localhost:9076`. The image requires accepting
Qlik's EULA (set in the compose `command`). Review Qlik Core licensing first.

## Step 3 — Install Node dependencies

```bash
npm install
```

## Step 4 — Match the QIX schema version (important)

`enigma.js` needs a schema compatible with the engine's QIX version, or calls
silently misbehave. The schema is selectable via the `QIX_SCHEMA` env var
(default `12.1306.0`). Check what's bundled and what the engine reports:

```bash
ls node_modules/enigma.js/schemas/            # available schemas
docker compose logs qix-engine | grep -i version   # engine QIX version
```

If the default doesn't match, set it:

```bash
QIX_SCHEMA=12.XXXX.0 APP_ID=MyApp.qvf npm run extract
```

Mismatches are the #1 cause of "method not found" errors. (`src/session.js`
now throws a clear error listing the fix if the schema file is missing.)

## Step 5 — Run the extraction

```bash
APP_ID=MyApp.qvf npm run extract
```

| Var          | Default        | Purpose                          |
|--------------|----------------|----------------------------------|
| `APP_ID`     | `MyApp.qvf`    | filename under `/apps`           |
| `OUT_DIR`    | `./output`     | where artifacts are written      |
| `QIX_SCHEMA` | `12.1306.0`    | enigma.js schema version         |
| `ENGINE_HOST`| `localhost`    | engine host                      |
| `ENGINE_PORT`| `9076`         | engine port                      |

## Output → q2t

```
output/
  script.qvs        # full load script (raw)
  data-model.json   # tables, fields, keys, associations (getTablesAndKeys)
  master-items.json # master measures + dimensions with expressions
  sheets.json       # sheets and their child charts/tables/KPIs
  manifest.json     # summary + counts
```

Then:

```bash
python -m q2t extract --mode engine-artifacts --artifacts output/ --out build/app.ir.json
python -m q2t transform --ir build/app.ir.json --out build/tml/ --report build/report.md
```

## How it works

1. `openDoc(appId)` opens the app in the engine (an "app" = the QVF).
2. `getScript()` returns the load script verbatim — source of truth for
   connections and transforms.
3. `getTablesAndKeys()` returns the engine's resolved data model (associated
   fields), more reliable than parsing the script.
4. Object lists (`sheet`, `measure`, `dimension`) are enumerated via session
   `ObjectList` objects; each handle's property tree is serialized. Sheet
   children are read from the property tree, with a `getChildInfos()` backstop.

## Notes & gotchas

- **Definitions vs data values:** extracts *definitions* (expressions, field
  names, model). For cell data, add `getHyperCubeData` per chart hypercube.
- **Reload:** `getScript()` and object defs work without reloading.
  `getTablesAndKeys()` reflects data saved in the QVF; if empty, `doReload()`
  needs reachable sources (Qlik Core handles connections differently than
  Sense Enterprise).
- **Section access / data-less exports** restrict what the engine exposes.
- **Version drift:** keep the engine image tag and `QIX_SCHEMA` aligned.
