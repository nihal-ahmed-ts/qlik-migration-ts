"""Ingest the 199-row Qlik→ThoughtSpot formula CSV, apply the corrections we
verified against ThoughtSpot's formula reference, tag each row with a status,
and emit the canonical map into q2t/data/ (CSV + JSON).

Corrections applied (verified against docs):
  * date_diff(...)        -> diff_days(...)            [ThoughtSpot uses diff_days]
  * D22 AddYears workaround -> add_years (exists natively)
  * sql_string/int/float/date/bool -> sql_*_op family  [matches TML op enum]

Flagged "verify" (could NOT confirm against the truncated docs page):
  * S12 strpos, N09 exp, D27 date_trunc
"""
import csv, json, os, re

SRC = "/Users/nihal.ahmed/Downloads/complete-qlik-sense-thoughtspot-formula-mapping-199-formulas-.csv"
OUT_DIR = "q2t/data"
os.makedirs(OUT_DIR, exist_ok=True)

TS_EQUIV = "ThoughtSpot Equivalent"
TS_EX = "ThoughtSpot Example"

# Confirmed token corrections applied to the ThoughtSpot columns.
SQL_OPS = {
    "sql_string(": "sql_string_op(", "sql_int(": "sql_int_op(",
    "sql_float(": "sql_double_op(", "sql_date(": "sql_date_op(",
    "sql_bool(": "sql_bool_op(",
}
VERIFY_ROWS = {"S12", "N09", "D27"}


def correct(row: dict) -> str:
    """Mutate the ThoughtSpot columns in place; return status."""
    rid = row["#"]
    status = "ok"

    for col in (TS_EQUIV, TS_EX):
        val = row.get(col, "") or ""
        orig = val
        # date_diff -> diff_days (native function only; SQL DATEDIFF left alone)
        val = re.sub(r"\bdate_diff\(", "diff_days(", val)
        # sql_* -> sql_*_op
        for old, new in SQL_OPS.items():
            val = val.replace(old, new)
        if val != orig:
            status = "corrected"
        row[col] = val

    # D22: AddYears has a native equivalent
    if rid == "D22":
        row[TS_EQUIV] = "add_years(date_col, n)"
        row[TS_EX] = "add_years(order_date, 1)"
        row["Comments / Context"] = ("ThoughtSpot has a native add_years(). "
                                     "No add_months(date,12) workaround needed.")
        status = "corrected"

    if rid in VERIFY_ROWS:
        status = "verify"
    return status


def main():
    with open(SRC, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))

    counts = {"ok": 0, "corrected": 0, "verify": 0}
    for r in rows:
        r["status"] = correct(r)
        counts[r["status"]] += 1

    fields = list(rows[0].keys())
    with open(f"{OUT_DIR}/qlik_ts_formula_map.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader(); w.writerows(rows)
    with open(f"{OUT_DIR}/qlik_ts_formula_map.json", "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2, ensure_ascii=False)

    print(f"wrote {len(rows)} rows to {OUT_DIR}/qlik_ts_formula_map.(csv|json)")
    print(f"status: {counts}")


if __name__ == "__main__":
    main()
