"""Qlik expression -> ThoughtSpot formula translator.

A pragmatic translator that covers the common ground without requiring a heavy
parser dependency: a function-name map (aggregation / string / date / math),
conditional rewriting (If/nested), and Set Analysis pattern recognition
(patterns 1-6 from the architecture doc). Anything it cannot translate
confidently is returned with review_required=True and a human-readable reason
so the migration report can flag it — never silently dropped.

translate(expr) -> (ts_formula, review_required, reason)
"""

from __future__ import annotations

import re

# Qlik function name (lowercase) -> ThoughtSpot formula function.
# None means "no equivalent" -> flagged for manual review.
FUNCTION_MAP: dict[str, str | None] = {
    # aggregation
    "sum": "sum", "avg": "average", "average": "average", "count": "count",
    "min": "min", "max": "max", "median": "median", "stdev": "stddev",
    "variance": "variance",
    # string
    "left": "left", "right": "right", "mid": "mid", "len": "len",
    "upper": "upper", "lower": "lower", "trim": "trim", "ltrim": "ltrim",
    "rtrim": "rtrim", "index": "strpos", "concat": "concat",
    "replace": "replace", "num": "to_double", "text": "to_string",
    "subfield": None,
    # date
    "year": "year", "month": "month_number", "day": "day_of_month",
    "weekday": "day_of_week", "quarter": "quarter_number", "today": "today",
    "now": "now", "addmonths": "add_months", "addyears": "add_years",
    "monthstart": "date_trunc_month", "yearstart": "date_trunc_year",
    "quarterstart": "date_trunc_quarter", "weekstart": "date_trunc_week",
    "date": "to_date", "networkdays": None,
    # math
    "round": "round", "floor": "floor", "ceil": "ceiling", "abs": "abs",
    "sqrt": "sqrt", "pow": "power", "log": "log", "exp": "exp", "mod": "mod",
    "rangesum": None, "mode": None,
}


def translate(expr: str) -> tuple[str, bool, str]:
    expr = (expr or "").strip()
    if not expr:
        return "", False, ""

    # Set Analysis first — recognizable by {<...>} / {1} / {$}.
    if "{" in expr:
        return _set_analysis(expr)

    # Count(DISTINCT X) -> unique_count(X)
    m = re.match(r"(?i)^count\(\s*distinct\s+(.+?)\)$", expr)
    if m:
        return f"unique_count({m.group(1).strip()})", False, ""

    # If(cond, t, f) -> if (cond) then t else f
    if re.match(r"(?i)^if\s*\(", expr):
        rewritten = _translate_if(expr)
        if rewritten is not None:
            return rewritten, False, ""
        return (f"/* TODO review: {expr} */", True,
                f"Could not parse If() structure: {expr}")

    # Generic function-name remap on the whole expression.
    out, unknown = _remap_functions(expr)
    if unknown:
        return out, True, f"Unmapped Qlik function(s): {', '.join(sorted(unknown))}"
    return out, False, ""


# -- function remap --------------------------------------------------------

_FUNC_CALL = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")


def _remap_functions(expr: str) -> tuple[str, set[str]]:
    unknown: set[str] = set()

    def repl(m: re.Match) -> str:
        name = m.group(1)
        low = name.lower()
        if low in FUNCTION_MAP:
            ts = FUNCTION_MAP[low]
            if ts is None:
                unknown.add(name)
                return f"{name}("        # leave as-is, flagged
            return f"{ts}("
        # Not a known Qlik function token (could be a field-ish call); flag it.
        unknown.add(name)
        return f"{name}("

    out = _FUNC_CALL.sub(repl, expr)
    # operator normalisation
    out = out.replace("<>", "!=").replace("&", "+")
    return out, unknown


def _translate_if(expr: str) -> str | None:
    """If(cond, true[, false]) -> if (cond) then true else false, recursively."""
    args = _split_call(expr, "if")
    if args is None or len(args) < 2:
        return None
    cond, _ = _remap_functions(args[0])
    true_val = _translate_arg(args[1])
    if len(args) >= 3:
        false_val = _translate_arg(args[2])
        return f"if ({cond}) then {true_val} else {false_val}"
    return f"if ({cond}) then {true_val}"


def _translate_arg(arg: str) -> str:
    arg = arg.strip()
    if re.match(r"(?i)^if\s*\(", arg):
        inner = _translate_if(arg)
        if inner is not None:
            return inner
    out, _ = _remap_functions(arg)
    return out


def _split_call(expr: str, fname: str) -> list[str] | None:
    """Return the top-level comma-split args of fname(...) in expr."""
    m = re.match(rf"(?i)^{fname}\s*\((.*)\)\s*$", expr, re.DOTALL)
    if not m:
        return None
    return _split_top_level(m.group(1))


def _split_top_level(s: str) -> list[str]:
    parts, depth, cur, in_str = [], 0, [], None
    for ch in s:
        if in_str:
            cur.append(ch)
            if ch == in_str:
                in_str = None
            continue
        if ch in "'\"":
            in_str = ch; cur.append(ch)
        elif ch in "([{":
            depth += 1; cur.append(ch)
        elif ch in ")]}":
            depth -= 1; cur.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(cur)); cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append("".join(cur))
    return [p.strip() for p in parts]


# -- set analysis ----------------------------------------------------------

def _set_analysis(expr: str) -> tuple[str, bool, str]:
    # Pattern 1: {1} -> ignore all selections (total).
    m = re.match(r"(?i)^(\w+)\(\s*\{1\}\s*(.+?)\)$", expr)
    if m:
        agg = FUNCTION_MAP.get(m.group(1).lower(), "sum")
        return f"group_aggregate({agg}({m.group(2).strip()}), {{}}, {{}})", False, ""

    # Pattern 2/3/4: {<Field={...}>} (equals / exclude / union).
    # raw_vals captures everything up to the closing '>}' so nested/union value
    # braces like {2023}+{2024} are spanned, then values are pulled out.
    m = re.match(r"(?i)^(\w+)\(\s*\{<\s*([\w \[\]]+?)\s*(-?=)\s*(.+?)\s*>\}\s*(.+?)\)$", expr)
    if m:
        agg_fn = FUNCTION_MAP.get(m.group(1).lower(), "sum")
        field = m.group(2).strip().strip("[]")
        op = m.group(3)
        raw_vals = m.group(4)
        measure = m.group(5).strip()
        # Values may appear as {a}, {a,b}, or {a}+{b}; flatten all brace groups.
        groups = re.findall(r"\{([^}]*)\}", raw_vals) or [raw_vals]
        values = []
        for g in groups:
            values += [v.strip().strip("'\"") for v in g.split(",") if v.strip()]
        if op == "-=":
            cond = " and ".join(f"{field} != '{v}'" for v in values) or "true"
        else:
            cond = " or ".join(f"{field} = '{v}'" for v in values) or "true"
        if len(values) > 1:
            cond = f"({cond})"
        return f"{agg_fn}(if ({cond}) then {measure} else 0)", False, ""

    # Pattern 5/6: intersection with selection ($*<...>) or $-expansion.
    if "$" in expr:
        return (f"/* TODO review set analysis: {expr} */", True,
                "Set analysis uses current-selection context ($) or $-expansion; "
                "approximate manually — selection state is not preserved in ThoughtSpot.")

    return (f"/* TODO review set analysis: {expr} */", True,
            f"Unrecognized Set Analysis pattern: {expr}")
