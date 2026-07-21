"""Build live TML for 'Sales App' against SALES_DW.STAR_SCHEMA (FACTSALES star
schema), reusing the existing Snowflake connection QlikMig_CaseStudy_SF.

Data model = SOURCE (read from the warehouse). The dashboard charts could NOT
be read from the binary .qvf, so the liveboard vizzes here are clearly-labeled
STARTER content (sensible defaults over the model), not the source dashboard.
"""
import os, yaml

CONN = "QlikMig_CaseStudy_SF"          # reused, account-level connection
DB, SCHEMA = "SALES_DW", "STAR_SCHEMA"
PFX = "QlikMig_SA_"
MODEL_NAME = "QlikMig Sales App"
OUT = "build/salesapp_tml"
os.makedirs(OUT, exist_ok=True)

def col(name, dtype, ctype="ATTRIBUTE", agg=None):
    p = {"column_type": ctype}
    if agg: p["aggregation"] = agg
    return {"name": name, "db_column_name": name,
            "properties": p, "db_column_properties": {"data_type": dtype}}

I, D, V = "INT64", "DOUBLE", "VARCHAR"
TABLES = {
  "FACTSALES": [col("SALESKEY",I),col("DATEKEY",I),col("CUSTOMERKEY",I),col("PRODUCTKEY",I),
     col("STOREKEY",I),col("SALESPERSONKEY",I),col("ORDERNUMBER",V),
     col("QUANTITY",I,"MEASURE","SUM"),col("UNITPRICE",D),col("DISCOUNTAMOUNT",D),
     col("SALESAMOUNT",D,"MEASURE","SUM"),col("COSTAMOUNT",D),col("PROFITAMOUNT",D,"MEASURE","SUM")],
  "DIMDATE": [col("DATEKEY",I),col("FULLDATE","DATE"),col("DAY",I),col("MONTH",I),
     col("MONTHNAME",V),col("QUARTER",V),col("YEAR",I),col("WEEKOFYEAR",I),col("ISWEEKEND","BOOL")],
  "DIMPRODUCT": [col("PRODUCTKEY",I),col("PRODUCTID",V),col("PRODUCTNAME",V),col("CATEGORY",V),
     col("SUBCATEGORY",V),col("BRAND",V),col("STANDARDCOST",D),col("LISTPRICE",D)],
  "DIMCUSTOMER": [col("CUSTOMERKEY",I),col("CUSTOMERID",V),col("FIRSTNAME",V),col("LASTNAME",V),
     col("GENDER",V),col("DATEOFBIRTH","DATE"),col("CITY",V),col("STATE",V),col("COUNTRY",V),
     col("CUSTOMERSEGMENT",V)],
  "DIMSTORE": [col("STOREKEY",I),col("STOREID",V),col("STORENAME",V),col("CITY",V),
     col("STATE",V),col("COUNTRY",V),col("REGION",V)],
  "DIMSALESPERSON": [col("SALESPERSONKEY",I),col("EMPLOYEEID",V),col("FIRSTNAME",V),
     col("LASTNAME",V),col("HIREDATE","DATE"),col("STOREKEY",I)],
}

def dump(doc, fname):
    with open(os.path.join(OUT, fname), "w") as f:
        yaml.safe_dump(doc, f, sort_keys=False, default_flow_style=False)

for t, cols in TABLES.items():
    dump({"table": {"name": PFX+t, "db": DB, "schema": SCHEMA, "db_table": t,
                    "connection": {"name": CONN}, "columns": cols}}, f"table.{PFX}{t}.tml")

def join(dim, key):
    return {"with": PFX+dim,
            "on": f"[{PFX}FACTSALES::{key}] = [{PFX}{dim}::{key}]",
            "type": "INNER", "cardinality": "MANY_TO_ONE"}

model = {"name": MODEL_NAME,
  "description": "Migrated from 'Sales App' (Qlik). Data model from SALES_DW.STAR_SCHEMA.",
  "model_tables": [
     {"name": PFX+"FACTSALES", "joins": [
        join("DIMDATE","DATEKEY"), join("DIMPRODUCT","PRODUCTKEY"),
        join("DIMCUSTOMER","CUSTOMERKEY"), join("DIMSTORE","STOREKEY"),
        join("DIMSALESPERSON","SALESPERSONKEY")]},
     {"name": PFX+"DIMDATE"}, {"name": PFX+"DIMPRODUCT"}, {"name": PFX+"DIMCUSTOMER"},
     {"name": PFX+"DIMSTORE"}, {"name": PFX+"DIMSALESPERSON"},
  ],
  "formulas": [
     {"id": "f_profit_margin", "name": "Profit Margin",
      "expr": f"sum ([{PFX}FACTSALES::SALESAMOUNT]) / sum ([{PFX}FACTSALES::PROFITAMOUNT])"},
  ],
  "columns": [
     {"name":"Category","column_id":f"{PFX}DIMPRODUCT::CATEGORY","properties":{"column_type":"ATTRIBUTE"}},
     {"name":"Sub Category","column_id":f"{PFX}DIMPRODUCT::SUBCATEGORY","properties":{"column_type":"ATTRIBUTE"}},
     {"name":"Brand","column_id":f"{PFX}DIMPRODUCT::BRAND","properties":{"column_type":"ATTRIBUTE"}},
     {"name":"Product Name","column_id":f"{PFX}DIMPRODUCT::PRODUCTNAME","properties":{"column_type":"ATTRIBUTE"}},
     {"name":"Region","column_id":f"{PFX}DIMSTORE::REGION","properties":{"column_type":"ATTRIBUTE"}},
     {"name":"Country","column_id":f"{PFX}DIMSTORE::COUNTRY",
      "properties":{"column_type":"ATTRIBUTE","geo_config":{"country":True}}},
     {"name":"Date","column_id":f"{PFX}DIMDATE::FULLDATE","properties":{"column_type":"ATTRIBUTE"}},
     {"name":"Customer Segment","column_id":f"{PFX}DIMCUSTOMER::CUSTOMERSEGMENT","properties":{"column_type":"ATTRIBUTE"}},
     {"name":"Year","column_id":f"{PFX}DIMDATE::YEAR","properties":{"column_type":"ATTRIBUTE"}},
     {"name":"Month Name","column_id":f"{PFX}DIMDATE::MONTHNAME","properties":{"column_type":"ATTRIBUTE"}},
     {"name":"Quarter","column_id":f"{PFX}DIMDATE::QUARTER","properties":{"column_type":"ATTRIBUTE"}},
     {"name":"Sales Amount","column_id":f"{PFX}FACTSALES::SALESAMOUNT","properties":{"column_type":"MEASURE","aggregation":"SUM"}},
     {"name":"Profit","column_id":f"{PFX}FACTSALES::PROFITAMOUNT","properties":{"column_type":"MEASURE","aggregation":"SUM"}},
     {"name":"Quantity","column_id":f"{PFX}FACTSALES::QUANTITY","properties":{"column_type":"MEASURE","aggregation":"SUM"}},
     {"name":"Profit Margin","formula_id":"f_profit_margin","properties":{"column_type":"MEASURE"}},
  ],
}
dump({"model": model}, f"model.{PFX}model.tml")

def viz(vid, name, query, ctype, cols, x, ys):
    return {"id": vid, "answer": {
        "name": name, "tables": [{"id": MODEL_NAME, "name": MODEL_NAME}],
        "search_query": query,
        "answer_columns": [{"name": c} for c in cols],
        "table": {"table_columns": [{"column_id": c, "show_headline": False} for c in cols],
                  "ordered_column_ids": cols, "client_state": "",
                  "client_state_v2": "{\"tableVizPropVersion\": \"V1\"}"},
        "chart": {"type": ctype, "chart_columns": [{"column_id": c} for c in cols],
                  "axis_configs": [{"x": [x], "y": ys}], "client_state": ""},
        "display_mode": "CHART_MODE"}}

lb = {"liveboard": {
   "name": "QlikMig Sales App",
   "visualizations": [
     viz("Viz_1","Sales Amount by Category","[Category] [Sales Amount]","COLUMN",
         ["Category","Total Sales Amount"],"Category",["Total Sales Amount"]),
     viz("Viz_2","Profit by Region","[Region] [Profit]","COLUMN",
         ["Region","Total Profit"],"Region",["Total Profit"]),
     viz("Viz_3","Sales Amount by Month","[Month Name] [Sales Amount]","LINE",
         ["Month Name","Total Sales Amount"],"Month Name",["Total Sales Amount"]),
     viz("Viz_4","Sales by Customer Segment","[Customer Segment] [Sales Amount]","PIE",
         ["Customer Segment","Total Sales Amount"],"Customer Segment",["Total Sales Amount"]),
     viz("Viz_5","Top Products by Sales","[Product Name] [Sales Amount]","COLUMN",
         ["Product Name","Total Sales Amount"],"Product Name",["Total Sales Amount"]),
   ],
   "layout": {"tiles": [
     {"visualization_id":"Viz_1","x":0,"y":0,"width":6,"height":4},
     {"visualization_id":"Viz_2","x":6,"y":0,"width":6,"height":4},
     {"visualization_id":"Viz_3","x":0,"y":4,"width":6,"height":4},
     {"visualization_id":"Viz_4","x":6,"y":4,"width":6,"height":4},
     {"visualization_id":"Viz_5","x":0,"y":8,"width":12,"height":4},
   ]},
}}
dump(lb, f"liveboard.{PFX}model.tml")
print("wrote", len(os.listdir(OUT)), "TML files to", OUT)
