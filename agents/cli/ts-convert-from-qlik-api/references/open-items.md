# Open Items: ts-convert-from-qlik-api

For a full mapping of what IS supported, see [coverage-matrix.md](coverage-matrix.md).

---

## #1 — Trial tenants cannot generate API keys — KNOWN (external)

Qlik Cloud **trial** tenants often lack the Developer role required to generate a
tenant API key, so this path can't be used on them.

**Workaround:** fall back to `ts-convert-from-qlik` (PDF + data model, no API).

Status: KNOWN — external Qlik limitation, not a bug.

---

## #2 — Physical warehouse mapping still needs confirmation — PARTIAL (MEDIUM)

The Qlik data connection tells us the source *type* and name, but not always the
exact ThoughtSpot connection and `db.schema` where the physical tables live.

**Workaround:** the skill prompts for the target connection + database/schema
(Step 1/3) and can introspect the target warehouse to confirm exact
tables/columns before emitting Table TML.

Status: PARTIAL — resolved interactively per migration; no code gap.

---

## #3 — Engine API transport unverified across all Qlik editions — NEEDS VERIFICATION (LOW)

`extract/qlik_engine.py` opens the Engine API over `wss` with a pinned QIX schema
version. It's verified against Qlik Cloud SaaS; Qlik Enterprise on Windows /
Qlik Core (Docker) may pin a different schema version.

**Workaround:** the `qvf-engine-extract` Node sidecar (Docker Qlik Core) is the
tested alternative for non-SaaS engines — its JSON dump feeds
`q2t extract --mode engine-artifacts`.

Status: NEEDS VERIFICATION — LOW (SaaS path is verified; enterprise/core covered
by the sidecar).
