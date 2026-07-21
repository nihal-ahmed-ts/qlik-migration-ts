"""Build the live TML set for the Sales & inventory dashboard against the real
DB_CASESTUDY.SA_CASESTUDY star schema. Writes table/model/liveboard TML to
build/live_tml/. Kept as a script so we can iterate against VALIDATE_ONLY.
"""
import os, yaml

CONN = "QlikMig_CaseStudy_SF"
DB, SCHEMA = "DB_CASESTUDY", "SA_CASESTUDY"
OUT = "build/live_tml"
os.makedirs(OUT, exist_ok=True)

def col(name, dtype, ctype="ATTRIBUTE", agg=None):
    p = {"column_type": ctype}
    if agg:
        p["aggregation"] = agg
    return {"name": name, "db_column_name": name,
            "properties": p, "db_column_properties": {"data_type": dtype}}

# --- tables (prefixed names, real db_table) -------------------------------
TABLES = {
    "QlikMig_F_SALES": ("F_SALES", [
        col("DATE_ID", "INT64"), col("PRODUCT_ID", "INT64"),
        col("QUANTITY_SOLD", "INT64", "MEASURE", "SUM"), col("CUSTOMER_ID", "VARCHAR")]),
    "QlikMig_F_INVENTORY": ("F_INVENTORY", [
        col("DATE_ID", "INT64"), col("PRODUCT_ID", "INT64"),
        col("QUANTITY_PURCHASED", "INT64", "MEASURE", "SUM"), col("CUSTOMER_ID", "VARCHAR")]),
    "QlikMig_D_PRODUCT": ("D_PRODUCT", [
        col("PRODUCT_ID", "INT64"), col("PRODUCT_NAME", "VARCHAR"),
        col("PRODUCT_TYPE", "VARCHAR"), col("UNIT_COST_USD", "DOUBLE"),
        col("UNIT_RETAIL_PRICE_USD", "DOUBLE")]),
    "QlikMig_D_DATE": ("D_DATE", [
        col("DATE_ID", "INT64"), col("DATE", "DATE"), col("IS_HOLIDAY", "INT64")]),
}

def dump(doc, fname):
    with open(os.path.join(OUT, fname), "w") as f:
        yaml.safe_dump(doc, f, sort_keys=False, default_flow_style=False)

for tname, (db_table, cols) in TABLES.items():
    dump({"table": {"name": tname, "db": DB, "schema": SCHEMA, "db_table": db_table,
                    "connection": {"name": CONN}, "columns": cols}},
         f"table.{tname}.tml")

# --- model with joins + formulas ------------------------------------------
def join(with_tbl, left, right):
    return {"with": with_tbl,
            "on": f"[QlikMig_F_{left[0]}::{left[1]}] = [{with_tbl}::{right}]",
            "type": "INNER", "cardinality": "MANY_TO_ONE"}

model = {
  "name": "QlikMig Sales and inventory dashboard",
  "description": "Migrated from Qlik Sense app 'Sales and inventory dashboard'.",
  "model_tables": [
     {"name": "QlikMig_F_SALES", "joins": [
        {"with": "QlikMig_D_PRODUCT",
         "on": "[QlikMig_F_SALES::PRODUCT_ID] = [QlikMig_D_PRODUCT::PRODUCT_ID]",
         "type": "INNER", "cardinality": "MANY_TO_ONE"},
        {"with": "QlikMig_D_DATE",
         "on": "[QlikMig_F_SALES::DATE_ID] = [QlikMig_D_DATE::DATE_ID]",
         "type": "INNER", "cardinality": "MANY_TO_ONE"}]},
     {"name": "QlikMig_F_INVENTORY", "joins": [
        {"with": "QlikMig_D_PRODUCT",
         "on": "[QlikMig_F_INVENTORY::PRODUCT_ID] = [QlikMig_D_PRODUCT::PRODUCT_ID]",
         "type": "INNER", "cardinality": "MANY_TO_ONE"},
        {"with": "QlikMig_D_DATE",
         "on": "[QlikMig_F_INVENTORY::DATE_ID] = [QlikMig_D_DATE::DATE_ID]",
         "type": "INNER", "cardinality": "MANY_TO_ONE"}]},
     {"name": "QlikMig_D_PRODUCT"},
     {"name": "QlikMig_D_DATE"},
  ],
  "formulas": [
     {"id": "formula_revenue_line", "name": "Revenue Line",
      "expr": "[QlikMig_F_SALES::QUANTITY_SOLD] * [QlikMig_D_PRODUCT::UNIT_RETAIL_PRICE_USD]"},
  ],
  "columns": [
     {"name": "Date", "column_id": "QlikMig_D_DATE::DATE", "properties": {"column_type": "ATTRIBUTE"}},
     {"name": "Product Name", "column_id": "QlikMig_D_PRODUCT::PRODUCT_NAME", "properties": {"column_type": "ATTRIBUTE"}},
     {"name": "Product Type", "column_id": "QlikMig_D_PRODUCT::PRODUCT_TYPE", "properties": {"column_type": "ATTRIBUTE"}},
     {"name": "Quantity Sold", "column_id": "QlikMig_F_SALES::QUANTITY_SOLD",
      "properties": {"column_type": "MEASURE", "aggregation": "SUM"}},
     {"name": "Inventory Level", "column_id": "QlikMig_F_INVENTORY::QUANTITY_PURCHASED",
      "properties": {"column_type": "MEASURE", "aggregation": "SUM"}},
     {"name": "Sales Revenue", "formula_id": "formula_revenue_line",
      "properties": {"column_type": "MEASURE", "aggregation": "SUM"}},
  ],
}
dump({"model": model}, "model.QlikMig_dashboard.tml")

# --- liveboard ------------------------------------------------------------
MODEL_NAME = "QlikMig Sales and inventory dashboard"
def viz(vid, name, query, ctype, cols, x, ys):
    """cols = exact output column names; x = dimension; ys = measure column(s)."""
    return {"id": vid, "answer": {
        "name": name,
        "tables": [{"id": MODEL_NAME, "name": MODEL_NAME}],
        "search_query": query,
        "answer_columns": [{"name": c} for c in cols],
        "table": {
            "table_columns": [{"column_id": c, "show_headline": False} for c in cols],
            "ordered_column_ids": cols,
            "client_state": "",
            "client_state_v2": "{\"tableVizPropVersion\": \"V1\"}",
        },
        "chart": {
            "type": ctype,
            "chart_columns": [{"column_id": c} for c in cols],
            "axis_configs": [{"x": [x], "y": ys}],
            "client_state": "",
        },
        "display_mode": "CHART_MODE"}}

lb = {"liveboard": {
   "name": "QlikMig Sales and inventory dashboard",
   "visualizations": [
      viz("Viz_1", "Daily Sales Revenue", "[Date] [Sales Revenue]", "LINE",
          ["Month(Date)", "Total Sales Revenue"], "Month(Date)", ["Total Sales Revenue"]),
      viz("Viz_2", "Inventory Levels by Product Type", "[Product Type] [Inventory Level]", "COLUMN",
          ["Product Type", "Total Inventory Level"], "Product Type", ["Total Inventory Level"]),
      viz("Viz_3", "Product Sales Performance", "[Product Name] [Quantity Sold] [Sales Revenue]", "LINE_COLUMN",
          ["Product Name", "Total Quantity Sold", "Total Sales Revenue"], "Product Name",
          ["Total Quantity Sold", "Total Sales Revenue"]),
   ],
   "layout": {"tiles": [
      {"visualization_id": "Viz_1", "x": 0, "y": 0, "width": 6, "height": 4},
      {"visualization_id": "Viz_2", "x": 6, "y": 0, "width": 6, "height": 4},
      {"visualization_id": "Viz_3", "x": 0, "y": 4, "width": 6, "height": 4},
   ]},
}}
dump(lb, "liveboard.QlikMig_dashboard.tml")
print("wrote", len(os.listdir(OUT)), "TML files to", OUT)
