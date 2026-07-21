# Content Structure Rules

Where new content belongs. Work through these in order; stop at the first match.

### 1. Is it a lookup table, schema reference, or mapping used by 2+ skills?
**→ `agents/shared/`**

Both Qlik skills read the same formula translation, TML invariants, and IR
contract. Putting that content in one skill's `references/` means the other gets a
stale copy. Shared homes:

- `agents/shared/mappings/qlik/` — Qlik ↔ ThoughtSpot translation rules (formula map).
- `agents/shared/schemas/` — structural references (TML invariants, the `q2t` IR contract).

The machine-readable formula map (`*.json`/`*.csv`) stays inside the CLI package
(`tools/q2t-cli/q2t/data/`) because code loads it; the human-readable rendering
lives in `agents/shared/mappings/qlik/`.

### 2. Is it skill-specific but too large for SKILL.md?
**→ `agents/cli/<skill>/references/`**

Skill-local files: coverage matrix, open-items tracking, report format/example.
Used by one skill only. SKILL.md links to them. The `references/open-items.md` and
`references/coverage-matrix.md` patterns are the canonical examples.

### 3. Everything else
**→ inline in SKILL.md**

Step-by-step procedure, decision trees, runtime-specific instructions — anything
used only in that one skill and small enough to read in context.

---

## When to split a file

Split when the section is a lookup table in an otherwise-prose file, another file
links to a section inside it, it changes at a different cadence than the rest, or
it exceeds ~250 lines with separable concerns. Keep a single coherent procedure
together even when long.

---

## Currency anchors

Every file under `agents/shared/mappings/` and `agents/shared/schemas/` carries a
header anchor recording what product state it was last validated against:

```markdown
<!-- currency: <platform> — <YYYY-MM> (<context>) -->
```

When a mapping/schema materially changes, update the anchor. This keeps
"is this still true against current Qlik / ThoughtSpot?" answerable without
re-reviewing everything.
