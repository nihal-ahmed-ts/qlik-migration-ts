# Skill Naming Convention

Every skill directory under `agents/cli/` must match one of the documented family
patterns below. Enforced by `tools/validate/check_skill_naming.py` (runs in the
pre-commit hook and CI).

This repo mirrors the naming families of the sibling `thoughtspot-agent-skills`
repo. Skill names are the user's primary discovery surface — the `/<skill-name>`
slash command and the directory name — so consistent shapes let users build
correct expectations from the prefix alone.

## Families used in this repo

| Family | Pattern | Semantic | Members |
|---|---|---|---|
| `ts-convert-*` | `ts-convert-{to\|from}-{format}` | Cross-platform schema/dashboard conversion. Third token is `to` or `from`; fourth is the source/target format. A `-api` (or similar) suffix distinguishes multiple front-ends for the same format. | `ts-convert-from-qlik`, `ts-convert-from-qlik-api` |

The two Qlik skills are the same conversion (`from qlik`) via two extraction
front-ends: `ts-convert-from-qlik` (no-API / PDF + data model) and
`ts-convert-from-qlik-api` (Qlik Cloud API). Both share the `q2t` engine.

## Adding a new family

If a future skill doesn't fit `ts-convert-*`, add a new family in the same PR:

1. Add a row to the table above (pattern, semantic, ≥1 example).
2. Add the family to `FAMILY_PATTERNS` in `tools/validate/check_skill_naming.py`
   with a regex and one-line description.
3. Explain in the PR **why** an existing family doesn't fit.

Consult the sibling repo's `.claude/rules/skill-naming.md` for the full catalog of
families (`ts-object-*`, `ts-profile-*`, `ts-dependency-*`, `ts-recipe-*`, …) if a
new skill here maps onto one of those shapes — reuse the same pattern rather than
inventing a variant.

## Allowlist

`ALLOWLIST` in the validator is for skills that legitimately don't fit any family.
It should be empty under normal circumstances; each entry needs a justification
comment.

## What this rule does NOT cover

- **Inside-skill file naming** — `references/*` names are the skill author's choice.
- **`q2t` command names** — `q2t extract`, `q2t transform`, etc. follow the CLI's
  own `q2t <verb>` convention (see `tools/q2t-cli/README.md`).
- **Slash commands** — always match the skill directory name 1:1.
