# Versioning

## Per-skill changelog

Every skill's `SKILL.md` ends with a `## Changelog` section. Enforced by
`tools/validate/check_skill_versions.py` (pre-commit + CI).

Format:

```markdown
---

## Changelog

| Version | Date | Summary |
|---|---|---|
| 1.1.0 | 2026-08-01 | Add set-analysis translation for P()/E() modifiers |
| 1.0.0 | 2026-07-21 | Initial release |
```

- Semver `MAJOR.MINOR.PATCH`; ISO dates `YYYY-MM-DD`; newest entry on top.
- Bump at **PR time**, not during wip development.

| Change | Bump |
|---|---|
| Breaking — removed step, changed command interface, incompatible output | MAJOR |
| New capability — new mode, new option, new output field | MINOR |
| Fix / clarification — corrected instructions, typo, example fix | PATCH |

Renaming a skill is a MAJOR change (the slash command changes).

## CLI version

`tools/q2t-cli/pyproject.toml` `version` and `q2t/__init__.py __version__` must
match — bump both together on any `q2t` interface change.

## Repo changelog (CHANGELOG.md)

`CHANGELOG.md` at the repo root tracks repo-level events — new skills, `q2t`
version bumps, new shared references, significant infrastructure. Individual skill
fixes go in the skill's own `## Changelog`, not here.

Format (dated, newest on top):

```markdown
## 2026-07-21
- feat: align repo structure with thoughtspot-agent-skills conventions
```
