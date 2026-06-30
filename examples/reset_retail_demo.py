"""Reset the Retail Analytics demo so it can be re-run live cleanly.

Deletes the Liveboard, the Model, and the QM_ tables from ThoughtSpot.
KEEPS the connection (QlikMig_CaseStudy_SF) and the Snowflake data — so a
fresh `build_demo.py` + `build_demo_liveboard.py` recreates everything.

Usage:  TS_USER=... TS_PASS=... python examples/reset_retail_demo.py [--host URL]
"""
import os, sys, requests

HOST = "https://ps-internal.thoughtspot.cloud"
if "--host" in sys.argv:
    HOST = sys.argv[sys.argv.index("--host") + 1]

TABLES = [f"QM_{t}" for t in (
    "FACT_SALES", "FACT_RETURNS", "DIM_DATE", "DIM_CUSTOMER",
    "DIM_PRODUCT", "DIM_STORE", "DIM_CHANNEL", "DIM_PROMOTION")]


def main() -> int:
    user, pwd = os.environ.get("TS_USER"), os.environ.get("TS_PASS")
    if not (user and pwd):
        print("set TS_USER and TS_PASS"); return 2
    s = requests.Session()
    s.post(f"{HOST}/api/rest/2.0/auth/session/login",
           json={"username": user, "password": pwd}, headers={"Accept": "application/json"})

    def find(mtype, name):
        r = s.post(f"{HOST}/api/rest/2.0/metadata/search",
                   json={"metadata": [{"type": mtype, "name_pattern": name}], "record_size": 50},
                   headers={"Accept": "application/json", "Content-Type": "application/json"})
        return [it for it in (r.json() if r.status_code == 200 else [])
                if it.get("metadata_name") == name]

    def delete(mtype, gid):
        s.post(f"{HOST}/api/rest/2.0/metadata/delete",
               json={"metadata": [{"identifier": gid, "type": mtype}]},
               headers={"Accept": "application/json", "Content-Type": "application/json"})

    # Order matters: liveboard -> model -> tables.
    for mtype, name in ([("LIVEBOARD", "QlikMig Retail Analytics Dashboard"),
                         ("LOGICAL_TABLE", "QlikMig Retail Analytics")]
                        + [("LOGICAL_TABLE", t) for t in TABLES]):
        for it in find(mtype, name):
            delete(mtype, it["metadata_id"])
            print(f"deleted {mtype}: {name} ({it['metadata_id']})")
    print("reset complete — connection QlikMig_CaseStudy_SF kept.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
