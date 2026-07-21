# Credential and Secret Handling

This tool touches two credentialed systems: **Qlik Cloud** (API key) and
**ThoughtSpot** (user/password or bearer token). Neither credential is ever
committed, echoed, or written into the repo.

## Where credentials go

| Credential | Supplied via | Never in |
|---|---|---|
| Qlik Cloud API key | `QLIK_API_KEY` env var (or `--api-key`) | Files, git, the `.qvf`, conversation logs |
| ThoughtSpot user/password | `TS_USER` / `TS_PASS` env vars (or `--user`/`--password`) | Files, git |
| ThoughtSpot bearer token | `--token` | Files, git |
| Snowflake key-pair files (`.p8`, `.pem`, `.key`) | Referenced by path, outside the repo | Git — `.gitignore` covers `*.p8`, `*.pem`, `*.key` |

## Rules for skill authors

- **Never accept a credential in the Claude Code conversation.** Direct the user
  to `export QLIK_API_KEY=…` / set `TS_USER`/`TS_PASS` in their own terminal. The
  value must not appear in any message.
- **Never write credentials to files inside the repo** — including build output.
  A `.qvf` never contains warehouse secrets; they are supplied only at load time.
- **Never `print()` or `echo` a credential value** for debugging. Use a
  presence-check (`"set" if os.environ.get("QLIK_API_KEY") else "missing"`).
- **Tell the user to revoke** a Qlik Cloud API key after the migration.
- `.qvf` files, IR JSON, and generated TML can contain schema names but **no
  secrets** — safe to keep under `build/` (gitignored) but review before sharing.

## No secrets in the repo

`tools/validate/check_secrets.py` scans the tree for committed tokens, keys, and
password-like assignments and fails the commit/PR if any are found. `.gitignore`
covers `.env`, `*.pem`, `*.p8`, `*.key`, `*_cookies.txt`, and `build/`.

## Adding a new external service

Follow the same env-var + `.gitignore` pattern, use a distinct env-var prefix, and
document the credential type + platform commands in the skill's SKILL.md.
