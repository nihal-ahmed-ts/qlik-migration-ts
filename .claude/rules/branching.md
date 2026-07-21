# Branching Protocol

## Session-start check — before any file edits

```bash
git branch && git status
```

| Current branch | Intended work | Action |
|---|---|---|
| `main` | Any change | Create a branch first — **never commit or push directly to main** |
| `feat/*` / `wip/*` (correct branch) | Continuing the work | Proceed |
| `feat/*` / `wip/*` (wrong branch) | Work belongs elsewhere | Switch branches first |

**All changes to `main` go through a pull request — no exceptions**, including
hotfixes, docs-only edits, and single-line changes.

## Branch naming

- `feat/<slug>` — changes ready to PR immediately (e.g. `feat/align-repo-structure`).
- `wip/<slug>` — in-progress work that needs live-instance testing before shipping.

## Merge criteria (all true before opening a PR)

1. All `references/open-items.md` items in changed skills are VERIFIED, or
   explicitly deferred to a follow-up open item.
2. All validators pass: `python3 tools/validate/check_*.py --root .`
3. Unit tests pass: `pytest tools/q2t-cli/tests/`.
4. A smoke test exists for every new/modified skill in `tools/smoke-tests/`, or
   the skill is allowlisted with a justification.

## Steps

```bash
git push -u origin feat/<slug>
# Open a PR against main on GitHub — do not merge locally
# After merge:
git branch -d feat/<slug> && git push origin --delete feat/<slug>
```
