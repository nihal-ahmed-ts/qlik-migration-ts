"""Unit tests for the formula-map lookup / classify / audit / stats layer."""
from q2t.transform import formula_map


def test_lookup_finds_sum():
    hits = formula_map.lookup("Sum")
    assert hits, "expected at least one mapping for 'Sum'"
    m = hits[0]
    for attr in ("id", "category", "qlik", "ts", "status"):
        assert hasattr(m, attr)


def test_stats_row_count():
    s = formula_map.stats()
    assert s["rows"] == 199
    # every row carries a status bucket that sums back to the total
    assert s["status_ok"] + s["status_corrected"] + s["status_verify"] == s["rows"]


def test_classify_returns_pairs():
    out = formula_map.classify("Sum(Revenue)")
    assert isinstance(out, list)
    assert all(isinstance(pair, tuple) and len(pair) == 2 for pair in out)


def test_audit_runs_over_expressions():
    result = formula_map.audit(["Sum(Revenue)", "Count(DISTINCT Customer)"])
    assert isinstance(result, dict)
