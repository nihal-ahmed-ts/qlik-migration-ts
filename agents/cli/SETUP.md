# Setup Guide — CLI Skills

The Qlik → ThoughtSpot migration skills work in **Claude Code** and **Cortex Code
CLI**. Both have full shell access and drive the migration through the `q2t` CLI.

---

## Prerequisites

- Python 3.10–3.14 (the `q2t` CLI supports `>=3.10,<3.15`)
- Git

---

## Step 1 — Clone

```bash
git clone https://github.com/nihal-ahmed-ts/qlik-migration-ts.git ~/qlik-migration-ts
```

## Step 2 — Install the `q2t` CLI

```bash
pip install -e ~/qlik-migration-ts/tools/q2t-cli                 # base
pip install -e "~/qlik-migration-ts/tools/q2t-cli[engine]"       # + Qlik Engine (websocket)
pip install -e "~/qlik-migration-ts/tools/q2t-cli[snowflake]"    # + warehouse type introspection
```

Verify:

```bash
q2t --help
```

## Step 3 — Install the skills

Skills are the same in both runtimes — only the install location differs. The
canonical source is `agents/cli/<skill>`; symlink it so edits take effect
immediately (no copy step).

### Claude Code

```bash
mkdir -p ~/.claude/skills

ln -s ~/qlik-migration-ts/agents/cli/ts-convert-from-qlik \
      ~/.claude/skills/ts-convert-from-qlik

ln -s ~/qlik-migration-ts/agents/cli/ts-convert-from-qlik-api \
      ~/.claude/skills/ts-convert-from-qlik-api

# Shared reference library (formula map, TML invariants, IR contract)
ln -s ~/qlik-migration-ts/agents/shared ~/.claude/shared
```

### Cortex Code CLI

```bash
mkdir -p ~/.snowflake/cortex/skills

ln -s ~/qlik-migration-ts/agents/cli/ts-convert-from-qlik \
      ~/.snowflake/cortex/skills/ts-convert-from-qlik

ln -s ~/qlik-migration-ts/agents/cli/ts-convert-from-qlik-api \
      ~/.snowflake/cortex/skills/ts-convert-from-qlik-api

ln -s ~/qlik-migration-ts/agents/shared ~/.snowflake/cortex/shared
```

Skills reference shared files via `../../shared/…`, which resolves correctly from
`~/.claude/skills/<skill>/` and `~/.snowflake/cortex/skills/<skill>/` because both
have a `shared/` directory at the same relative location.

## Step 4 — Credentials

Set these in your **own terminal** (never in the Claude Code conversation):

```bash
export QLIK_API_KEY=...            # Qlik Cloud API path only; revoke after migration
export TS_USER=... TS_PASS=...     # ThoughtSpot (or use a bearer token via --token)
```

See `.claude/rules/security.md`.

## Step 5 — Verify

Run `/ts-convert-from-qlik` (or `/ts-convert-from-qlik-api`) in your agent — the
skill should appear and prompt for its inputs.

---

## For contributors

Install the pre-commit hook so validators run before every commit:

```bash
cd ~/qlik-migration-ts
ln -s ../../scripts/pre-commit.sh .git/hooks/pre-commit
chmod +x scripts/pre-commit.sh
```

Run validators and tests manually:

```bash
python3 tools/validate/check_all.py --root .   # or run each check_*.py
pytest tools/q2t-cli/tests/
```

## Keeping updated

```bash
cd ~/qlik-migration-ts && git pull
pip install -e tools/q2t-cli   # if the q2t version changed
```

Symlinks update automatically.
