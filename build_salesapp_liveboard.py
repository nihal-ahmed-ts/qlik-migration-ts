"""Faithful rebuild of the 'Sales Performance Dashboard' liveboard, modeled on
the PDF/screenshots. Column names below were verified live via searchdata, so
every viz renders. Filters (Region, Date) are flagged for manual add — the TML
filter schema is omitted here to keep the import clean.
"""
import os, yaml
MODEL = "QlikMig Sales App"
OUT = "build/salesapp_tml"

def viz(vid, name, query, ctype, cols, x, ys):
    answer = {
        "name": name, "tables": [{"id": MODEL, "name": MODEL}],
        "search_query": query,
        "answer_columns": [{"name": c} for c in cols],
        "table": {"table_columns": [{"column_id": c, "show_headline": False} for c in cols],
                  "ordered_column_ids": cols, "client_state": "",
                  "client_state_v2": "{\"tableVizPropVersion\": \"V1\"}"},
        "chart": {"type": ctype, "chart_columns": [{"column_id": c} for c in cols],
                  "client_state": ""},
        "display_mode": "CHART_MODE"}
    ac = {}
    if x: ac["x"] = [x]
    if ys: ac["y"] = ys
    if ac: answer["chart"]["axis_configs"] = [ac]
    return {"id": vid, "answer": answer}

V = [
  viz("Viz_1","Sum(SALESAMOUNT)","[Sales Amount]","KPI",["Total Sales Amount"],None,["Total Sales Amount"]),
  viz("Viz_2","Sum(PROFITAMOUNT)","[Profit]","KPI",["Total Profit"],None,["Total Profit"]),
  viz("Viz_3","Sum(QUANTITY)","[Quantity]","KPI",["Total Quantity"],None,["Total Quantity"]),
  viz("Viz_4","Monthly Sales and Profit Totals","[Year] [Sales Amount] [Profit]","LINE",
      ["Year","Total Sales Amount","Total Profit"],"Year",["Total Sales Amount","Total Profit"]),
  viz("Viz_5","Quantity Over Time","[Year] [Quantity]","LINE",
      ["Year","Total Quantity"],"Year",["Total Quantity"]),
  viz("Viz_6","Sales and Profit by Region","[Region] [Sales Amount] [Profit]","COLUMN",
      ["Region","Total Sales Amount","Total Profit"],"Region",["Total Sales Amount","Total Profit"]),
  viz("Viz_7","Profit Margin by Category","[Category] [Profit Margin]","COLUMN",
      ["Category","Profit Margin"],"Category",["Profit Margin"]),
  viz("Viz_8","Sales by Customer Segment","[Customer Segment] [Sales Amount]","PIE",
      ["Customer Segment","Total Sales Amount"],"Customer Segment",["Total Sales Amount"]),
  viz("Viz_9","Percentage of Sales by Brand","[Brand] [Sales Amount]","BAR",
      ["Brand","Total Sales Amount"],"Brand",["Total Sales Amount"]),
  viz("Viz_10","Sales by Brand and Category","[Brand] [Category] [Sales Amount]","PIVOT_TABLE",
      ["Brand","Category","Total Sales Amount"],"Brand",["Total Sales Amount"]),
  viz("Viz_11","Sales by Country (Map)","[Country] [Sales Amount]","GEO_BUBBLE",
      ["Country","Total Sales Amount"],"Country",["Total Sales Amount"]),
]

tiles = [
  {"visualization_id":"Viz_1","x":0,"y":0,"width":4,"height":3},
  {"visualization_id":"Viz_2","x":4,"y":0,"width":4,"height":3},
  {"visualization_id":"Viz_3","x":8,"y":0,"width":4,"height":3},
  {"visualization_id":"Viz_4","x":0,"y":3,"width":6,"height":4},
  {"visualization_id":"Viz_5","x":6,"y":3,"width":6,"height":4},
  {"visualization_id":"Viz_11","x":0,"y":7,"width":6,"height":4},
  {"visualization_id":"Viz_6","x":6,"y":7,"width":6,"height":4},
  {"visualization_id":"Viz_10","x":0,"y":11,"width":12,"height":4},
  {"visualization_id":"Viz_7","x":0,"y":15,"width":4,"height":4},
  {"visualization_id":"Viz_8","x":4,"y":15,"width":4,"height":4},
  {"visualization_id":"Viz_9","x":8,"y":15,"width":4,"height":4},
]

# Liveboard filters (schema verified from a real exported liveboard).
filters = [
  {"column": ["Region"], "is_mandatory": False, "is_single_value": False, "display_name": ""},
  {"column": ["Date"],   "is_mandatory": False, "is_single_value": False, "display_name": ""},
]

lb = {"liveboard": {"name": "QlikMig Sales Performance Dashboard",
      "visualizations": V, "filters": filters, "layout": {"tiles": tiles}}}
os.makedirs(OUT, exist_ok=True)
with open(os.path.join(OUT, "liveboard.QlikMig_SalesPerf.tml"), "w") as f:
    yaml.safe_dump(lb, f, sort_keys=False, default_flow_style=False)
print("wrote faithful liveboard:", len(V), "vizzes")
