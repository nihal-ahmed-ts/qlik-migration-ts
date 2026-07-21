"""Warehouse column-type introspection -> ThoughtSpot TML data types.

Why this exists: generating Table TML requires the correct `data_type` per
column, and guessing (e.g. DOUBLE for a column that's actually an integer) makes
the import fail with `DataType ... does not match CDW DataType`. The fix is to
read the REAL types from the warehouse instead of inferring.

`map_snowflake_type` is a pure, well-tested mapping. `fetch_snowflake_types`
pulls the live types from INFORMATION_SCHEMA (optional snowflake-connector
dependency). The result feeds `to_tml.transform(type_overrides=...)`.
"""

from __future__ import annotations

from typing import Optional


def map_snowflake_type(data_type: str, numeric_scale: Optional[int] = None) -> str:
    """Map a Snowflake column type to a ThoughtSpot TML data_type.

    The key rule (the one that bit us): NUMBER with scale 0 is an integer
    (INT64); NUMBER with scale > 0 is decimal (DOUBLE).
    """
    dt = (data_type or "").upper().strip()
    if dt in ("NUMBER", "DECIMAL", "NUMERIC"):
        return "INT64" if (numeric_scale or 0) == 0 else "DOUBLE"
    if dt in ("INT", "INTEGER", "BIGINT", "SMALLINT", "TINYINT", "BYTEINT"):
        return "INT64"
    if dt in ("FLOAT", "FLOAT4", "FLOAT8", "DOUBLE", "DOUBLE PRECISION", "REAL"):
        return "DOUBLE"
    if dt in ("VARCHAR", "CHAR", "CHARACTER", "STRING", "TEXT"):
        return "VARCHAR"
    if dt == "BOOLEAN":
        return "BOOL"
    if dt == "DATE":
        return "DATE"
    if dt.startswith("TIMESTAMP") or dt == "DATETIME":
        return "DATE_TIME"
    if dt == "TIME":
        return "TIME"
    return "VARCHAR"  # safe default; better to be a string than to mis-type a number


def fetch_snowflake_types(database: str, schema: str, *, account: str, user: str,
                          private_key_path: str, role: Optional[str] = None,
                          warehouse: Optional[str] = None) -> dict[str, dict[str, str]]:
    """Introspect INFORMATION_SCHEMA and return {TABLE: {COLUMN: ts_type}}.

    Requires snowflake-connector-python + cryptography (optional deps). Keys are
    upper-cased for case-insensitive lookup by the transformer.
    """
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.backends import default_backend
        import snowflake.connector as sf
    except ImportError as e:  # pragma: no cover - optional dependency
        raise RuntimeError("snowflake-connector-python + cryptography required: "
                           "pip install snowflake-connector-python cryptography") from e

    pem = open(private_key_path, "rb").read()
    der = serialization.load_pem_private_key(pem, None, default_backend()).private_bytes(
        serialization.Encoding.DER, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption())
    con = sf.connect(account=account, user=user, private_key=der,
                     role=role, warehouse=warehouse, database=database, schema=schema)
    try:
        cur = con.cursor()
        cur.execute(
            "SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, NUMERIC_SCALE "
            "FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = %s "
            "ORDER BY TABLE_NAME, ORDINAL_POSITION", (schema,))
        out: dict[str, dict[str, str]] = {}
        for tname, cname, dtype, scale in cur.fetchall():
            out.setdefault(tname.upper(), {})[cname.upper()] = map_snowflake_type(dtype, scale)
        return out
    finally:
        con.close()


def lookup(type_overrides: Optional[dict], table: str, column: str) -> Optional[str]:
    """Case-insensitive lookup into a {table: {column: ts_type}} map."""
    if not type_overrides:
        return None
    tbl = type_overrides.get(table) or type_overrides.get(table.upper()) \
        or type_overrides.get(table.lower())
    if not tbl:
        return None
    return tbl.get(column) or tbl.get(column.upper()) or tbl.get(column.lower())
