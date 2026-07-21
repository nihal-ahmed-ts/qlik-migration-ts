"""Unit tests for warehouse type mapping (pure function)."""
import pytest

from q2t.transform import wh_types


@pytest.mark.parametrize("data_type,scale,expected", [
    ("NUMBER", 0, "INT64"),
    ("NUMBER", 2, "DOUBLE"),
    ("NUMBER", None, "INT64"),
    ("INT", None, "INT64"),
    ("FLOAT", None, "DOUBLE"),
    ("TEXT", None, "VARCHAR"),
    ("VARCHAR", None, "VARCHAR"),
    ("BOOLEAN", None, "BOOL"),
    ("DATE", None, "DATE"),
    ("TIMESTAMP_NTZ", None, "DATE_TIME"),
    ("TIME", None, "TIME"),
])
def test_map_snowflake_type(data_type, scale, expected):
    assert wh_types.map_snowflake_type(data_type, scale) == expected


def test_unknown_type_defaults_to_varchar():
    assert wh_types.map_snowflake_type("SOMETHING_WEIRD") == "VARCHAR"
