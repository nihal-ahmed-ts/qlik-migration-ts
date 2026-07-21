"""Unit tests for IR → TML emission (pure, no I/O)."""
from q2t import ir
from q2t.transform import to_tml


def _tiny_app():
    return ir.QlikApp(
        app_name="Demo",
        tables=[ir.Table(name="ORDERS", columns=[
            ir.Column(name="ID", data_type="INT"),
            ir.Column(name="AMOUNT", data_type="NUMBER"),
        ])],
    )


def test_transform_emits_table_and_model_docs():
    res = to_tml.transform(_tiny_app())
    assert isinstance(res.documents, dict)
    assert "table.ORDERS.tml" in res.documents
    assert "model.Demo.tml" in res.documents


def test_table_tml_has_db_column_name_invariant():
    res = to_tml.transform(_tiny_app())
    table_tml = res.documents["table.ORDERS.tml"]
    # Invariant: every column carries db_column_name (see TML invariants schema).
    assert "db_column_name" in table_tml
    assert "ORDERS" in table_tml


def test_type_override_is_applied():
    res = to_tml.transform(_tiny_app(), type_overrides={"ORDERS": {"AMOUNT": "DOUBLE"}})
    assert "DOUBLE" in res.documents["table.ORDERS.tml"]


def test_no_tables_records_a_note():
    res = to_tml.transform(ir.QlikApp(app_name="Empty"))
    assert any(area == "model" for _sev, area, _msg in res.notes)
