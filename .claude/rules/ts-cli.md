# q2t CLI Rules

Rules for when to use the `q2t` CLI, when to extend it, and when direct HTTP is a
legitimate exception. Applies to both skill authoring and CLI development.

---

## The core rule: skills use `q2t`, never inline `requests`

Both skills (`agents/cli/*`) must drive every Qlik-extract and ThoughtSpot-API
operation through `q2t` CLI commands. Direct `import requests` / `requests.post()`
in a SKILL.md is an anti-pattern — it duplicates auth handling and breaks when the
client's auth model changes. Enforced by
`tools/validate/check_no_inline_requests.py`.

```bash
# Correct — the CLI handles login, session, import policy, error formatting
q2t load --tml build/tml/ --host <TS_HOST> --import-policy ALL_OR_NONE

# Wrong — inline API call in a SKILL.md
requests.post(f"{host}/api/rest/2.0/metadata/tml/import", ...)
```

**If a `q2t` command fails:** diagnose and fix the CLI code in `tools/q2t-cli/`,
then re-run. Do not work around it with a manual script — that hides the bug.

---

## Where direct HTTP is legitimate

Direct `requests` (and the Qlik `websocket` transport) belong **inside the CLI**,
not in a SKILL.md:

- `tools/q2t-cli/q2t/load/ts_client.py` — the ThoughtSpot REST v2 client.
- `tools/q2t-cli/q2t/extract/qlik_cloud.py` — the Qlik Cloud REST adapter.
- `tools/q2t-cli/q2t/extract/qlik_engine.py` — Qlik Engine over `websocket` (not HTTP).

These are the CLI's I/O layer — the correct home for network code. The validator
scans SKILL.md files only.

---

## When to add a new `q2t` command

Add one when a skill needs an operation no existing subcommand covers, or two
skills would otherwise duplicate the same raw call. Don't add speculatively.

When adding: put the module logic under `tools/q2t-cli/q2t/`, wire it into
`q2t/cli.py` (`build_parser` + a `cmd_*` handler), add a row to
`tools/q2t-cli/README.md`, update any SKILL.md that uses it, add unit tests in
`tools/q2t-cli/tests/`, and bump the version in `pyproject.toml` +
`q2t/__init__.py`.

---

## Output conventions

| Convention | Rule |
|---|---|
| Structured data | JSON / files to the `--out` path; machine-readable |
| Diagnostics / progress | stderr, never mixed into structured stdout |
| Credentials | via `--token` / `--user`/`--password` / env (`TS_USER`, `TS_PASS`, `QLIK_API_KEY`) — never hardcoded |
| Connection identifier | connection display **name**, never a GUID, inside table TML |

---

## Testing requirements

Every new command or modified pure function needs unit tests in
`tools/q2t-cli/tests/` that run without a live connection (test the pure
functions — `expr.translate`, `to_tml`, `formula_map`, `wh_types.map_snowflake_type`).

```bash
pytest tools/q2t-cli/tests/
```
