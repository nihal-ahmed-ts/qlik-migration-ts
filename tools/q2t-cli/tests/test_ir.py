"""Unit tests for the IR (de)serialization contract."""
import json

from q2t import ir


def _app():
    return ir.QlikApp(
        app_name="Sales",
        source_file="Sales.qvf",
        extraction_mode="engine",
        connections=[ir.Connection(name="SF", qlik_type="Snowflake")],
        tables=[ir.Table(name="ORDERS", columns=[ir.Column(name="ID", data_type="INT")])],
        measures=[ir.MasterMeasure(id="m1", label="Revenue", expression="Sum(Amount)")],
        sheets=[ir.Sheet(id="s1", title="Overview",
                         charts=[ir.Chart(id="c1", title="Sales", viz_type="barchart")])],
    )


def test_json_round_trip_preserves_structure():
    app = _app()
    restored = ir.QlikApp.from_dict(json.loads(app.to_json()))
    assert restored.app_name == "Sales"
    assert restored.extraction_mode == "engine"
    assert restored.tables[0].name == "ORDERS"
    assert restored.tables[0].columns[0].name == "ID"
    assert restored.measures[0].expression == "Sum(Amount)"
    assert restored.sheets[0].charts[0].viz_type == "barchart"


def test_from_dict_tolerates_unknown_and_missing_keys():
    app = ir.QlikApp.from_dict({"app_name": "X", "tables": [{"name": "T", "bogus": 1}]})
    assert app.app_name == "X"
    assert app.tables[0].name == "T"      # unknown key ignored, no crash
    assert app.extraction_mode == "offline"  # default filled in


def test_note_appends_extraction_note():
    app = ir.QlikApp(app_name="X")
    app.note("warning", "chart", "could not recover viz")
    assert app.notes[0].severity == "warning"
    assert app.notes[0].area == "chart"
