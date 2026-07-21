"""Unit tests for the Qlik → ThoughtSpot expression translator (pure, no I/O)."""
from q2t.transform import expr


def test_translate_returns_triple():
    result = expr.translate("Sum(Revenue)")
    assert isinstance(result, tuple) and len(result) == 3
    formula, review, reason = result
    assert isinstance(formula, str)
    assert isinstance(review, bool)
    assert isinstance(reason, str)


def test_translate_simple_aggregation():
    formula, review, _ = expr.translate("Sum(Revenue)")
    assert formula == "sum(Revenue)"
    assert review is False


def test_translate_count_distinct():
    formula, review, _ = expr.translate("Count(DISTINCT Customer)")
    assert formula == "unique_count(Customer)"
    assert review is False


def test_translate_empty_is_noop():
    assert expr.translate("") == ("", False, "")


def test_function_map_is_populated():
    assert isinstance(expr.FUNCTION_MAP, dict)
    assert expr.FUNCTION_MAP  # non-empty
