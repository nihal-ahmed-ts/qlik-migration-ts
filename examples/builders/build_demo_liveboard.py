"""Faithful Retail Analytics liveboard (matches the dashboard PDF). Column
names verified live via searchdata. Filters: Region, Date, Channel."""
import os, yaml
MODEL="QlikMig Retail Analytics"; OUT="build/demo_tml"
def viz(vid,name,query,ctype,cols,x,ys):
    a={"name":name,"tables":[{"id":MODEL,"name":MODEL}],"search_query":query,
       "answer_columns":[{"name":c} for c in cols],
       "table":{"table_columns":[{"column_id":c,"show_headline":False} for c in cols],
                "ordered_column_ids":cols,"client_state":"",
                "client_state_v2":"{\"tableVizPropVersion\": \"V1\"}"},
       "chart":{"type":ctype,"chart_columns":[{"column_id":c} for c in cols],"client_state":""},
       "display_mode":"CHART_MODE"}
    ac={}
    if x: ac["x"]=[x]
    if ys: ac["y"]=ys
    if ac: a["chart"]["axis_configs"]=[ac]
    return {"id":vid,"answer":a}
V=[
 viz("Viz_1","Total Sales","[Sales]","KPI",["Total Sales"],None,["Total Sales"]),
 viz("Viz_2","Total Profit","[Profit]","KPI",["Total Profit"],None,["Total Profit"]),
 viz("Viz_3","Units Sold","[Units Sold]","KPI",["Total Units Sold"],None,["Total Units Sold"]),
 viz("Viz_4","Total Refunds","[Refunds]","KPI",["Total Refunds"],None,["Total Refunds"]),
 viz("Viz_5","Sales by Category","[Category] [Sales]","COLUMN",["Category","Total Sales"],"Category",["Total Sales"]),
 viz("Viz_6","Sales and Profit by Region","[Region] [Sales] [Profit]","COLUMN",["Region","Total Sales","Total Profit"],"Region",["Total Sales","Total Profit"]),
 viz("Viz_7","Sales by Channel","[Channel] [Sales]","PIE",["Channel","Total Sales"],"Channel",["Total Sales"]),
 viz("Viz_8","Annual Sales and Profit Trend","[Year] [Sales] [Profit]","LINE",["Year","Total Sales","Total Profit"],"Year",["Total Sales","Total Profit"]),
 viz("Viz_9","Sales by Customer Segment","[Segment] [Sales]","COLUMN",["Segment","Total Sales"],"Segment",["Total Sales"]),
 viz("Viz_10","Profit Margin % by Category","[Category] [Profit Margin]","COLUMN",["Category","Profit Margin"],"Category",["Profit Margin"]),
 viz("Viz_11","Sales by Country (Map)","[Country] [Sales]","GEO_BUBBLE",["Country","Total Sales"],"Country",["Total Sales"]),
 viz("Viz_12","Top Brands by Sales","[Brand] [Sales]","BAR",["Brand","Total Sales"],"Brand",["Total Sales"]),
 viz("Viz_13","Returns by Reason","[Return Reason] [Refunds]","COLUMN",["Return Reason","Total Refunds"],"Return Reason",["Total Refunds"]),
 viz("Viz_14","Sales by Category and Region","[Category] [Region] [Sales]","PIVOT_TABLE",["Category","Region","Total Sales"],"Category",["Total Sales"]),
]
tiles=[
 {"visualization_id":"Viz_1","x":0,"y":0,"width":3,"height":3},
 {"visualization_id":"Viz_2","x":3,"y":0,"width":3,"height":3},
 {"visualization_id":"Viz_3","x":6,"y":0,"width":3,"height":3},
 {"visualization_id":"Viz_4","x":9,"y":0,"width":3,"height":3},
 {"visualization_id":"Viz_5","x":0,"y":3,"width":6,"height":4},
 {"visualization_id":"Viz_6","x":6,"y":3,"width":6,"height":4},
 {"visualization_id":"Viz_8","x":0,"y":7,"width":6,"height":4},
 {"visualization_id":"Viz_7","x":6,"y":7,"width":6,"height":4},
 {"visualization_id":"Viz_9","x":0,"y":11,"width":4,"height":4},
 {"visualization_id":"Viz_10","x":4,"y":11,"width":4,"height":4},
 {"visualization_id":"Viz_13","x":8,"y":11,"width":4,"height":4},
 {"visualization_id":"Viz_11","x":0,"y":15,"width":6,"height":4},
 {"visualization_id":"Viz_12","x":6,"y":15,"width":6,"height":4},
 {"visualization_id":"Viz_14","x":0,"y":19,"width":12,"height":4},
]
filters=[{"column":[c],"is_mandatory":False,"is_single_value":False,"display_name":""} for c in ("Region","Date","Channel")]
lb={"liveboard":{"name":"QlikMig Retail Analytics Dashboard","visualizations":V,"filters":filters,"layout":{"tiles":tiles}}}
os.makedirs(OUT,exist_ok=True)
with open(os.path.join(OUT,"liveboard.QM_dashboard.tml"),"w") as f: yaml.safe_dump(lb,f,sort_keys=False,default_flow_style=False)
print("wrote liveboard:",len(V),"vizzes,",len(filters),"filters")
