"""Command-line orchestrator for the Qlik -> ThoughtSpot pipeline.

    python -m q2t extract   --qvf App.qvf --out build/app.ir.json [--mode offline|engine ...]
    python -m q2t transform --ir build/app.ir.json --out build/tml/ --report build/report.md
    python -m q2t load      --tml build/tml/ --host https://... [--validate-only]
    python -m q2t migrate   --qvf App.qvf --host https://...   (all three)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .ir import QlikApp
from .transform import report as report_mod
from .transform.to_tml import transform


# -- extract ---------------------------------------------------------------

def cmd_extract(args: argparse.Namespace) -> int:
    if args.mode == "offline":
        if not args.qvf:
            print("error: --qvf is required for offline mode", file=sys.stderr)
            return 2
        from .extract import extract_offline
        app = extract_offline(args.qvf)
    elif args.mode == "engine-artifacts":
        if not args.artifacts:
            print("error: --artifacts <dir> is required for engine-artifacts mode",
                  file=sys.stderr)
            return 2
        from .extract import engine_artifacts
        app = engine_artifacts.extract(args.artifacts)
    elif args.mode == "qlik-cloud":
        if not (args.tenant and args.app_id):
            print("error: --tenant and --app-id are required for qlik-cloud mode",
                  file=sys.stderr)
            return 2
        from .extract import qlik_cloud
        app = qlik_cloud.extract(args.tenant, args.app_id, args.api_key)
    else:
        if not (args.engine and args.app_id):
            print("error: --engine and --app-id are required for engine mode", file=sys.stderr)
            return 2
        from .extract import qlik_engine
        headers = dict(h.split("=", 1) for h in (args.header or []))
        if getattr(args, "probe", False):
            summary = qlik_engine.probe(args.engine, args.app_id, headers=headers)
            print("✓ engine probe:")
            print(f"  ws_url:    {summary['ws_url']}")
            print(f"  connected: {summary['connected']}  opened: {summary['opened']}")
            print(f"  objects:   {summary.get('total_objects', 0)} total")
            for t, n in summary.get("objects", {}).items():
                print(f"    - {t}: {n}")
            return 0
        app = qlik_engine.extract(args.engine, args.app_id, headers=headers)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    app.save(args.out)
    print(f"✓ IR written to {args.out}")
    _print_extract_summary(app)
    return 0


def _print_extract_summary(app: QlikApp) -> None:
    print(f"  app={app.app_name} mode={app.extraction_mode}")
    print(f"  connections={len(app.connections)} tables={len(app.tables)} "
          f"measures={len(app.measures)} sheets={len(app.sheets)} "
          f"charts={sum(len(s.charts) for s in app.sheets)}")
    manual = [n for n in app.notes if n.severity == "manual"]
    if manual:
        print(f"  ⚠ {len(manual)} item(s) need manual work (see report after transform)")


# -- transform -------------------------------------------------------------

def cmd_transform(args: argparse.Namespace) -> int:
    app = QlikApp.load(args.ir)
    result = transform(app, model_kind=args.model_kind)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for fname, doc in result.documents.items():
        (out / fname).write_text(doc, encoding="utf-8")
    print(f"✓ {len(result.documents)} TML file(s) written to {out}/")

    from .transform import formula_map
    audit = formula_map.audit([m.expression for m in app.measures if m.expression])
    md, js = report_mod.build(app, result, formula_audit=audit)
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(md, encoding="utf-8")
    report_path.with_suffix(".json").write_text(js, encoding="utf-8")
    print(f"✓ report written to {report_path} (+ .json)")

    manual = sum(1 for s, _, _ in result.notes if s == "manual")
    if manual:
        print(f"  ⚠ {manual} item(s) flagged for manual work — review before load")
    return 0


# -- load ------------------------------------------------------------------

def cmd_load(args: argparse.Namespace) -> int:
    from .load.ts_client import ThoughtSpotClient

    tml_dir = Path(args.tml)
    docs = [p.read_text(encoding="utf-8") for p in sorted(tml_dir.glob("*.tml"))]
    if not docs:
        print(f"error: no .tml files in {tml_dir}", file=sys.stderr)
        return 2

    client = ThoughtSpotClient(args.host, verify_tls=not args.insecure)
    if args.token:
        client.use_bearer(args.token)
        who = client.whoami()
    else:
        who = client.login(args.user, args.password)
    print(f"✓ connected to {args.host} as {who.get('name')}")

    if args.validate_only:
        res = client.validate_tml(docs)
        print("✓ VALIDATE_ONLY result:")
        _print_import_result(res)
        return 0

    res = client.import_tml(docs, import_policy=args.import_policy)
    print(f"✓ imported {len(docs)} TML doc(s) with policy {args.import_policy}")
    _print_import_result(res)
    return 0


def _print_import_result(res) -> None:
    if isinstance(res, list):
        for item in res:
            status = (item.get("response", {}) or item).get("status", item.get("status"))
            print(f"  - {item.get('type', '?')}: {status}")
    else:
        print(f"  {res}")


# -- formulas (mapping reference + audit) ----------------------------------

def cmd_formulas(args: argparse.Namespace) -> int:
    from .transform import formula_map

    if args.lookup:
        hits = formula_map.lookup(args.lookup)
        if not hits:
            print(f"no mapping found for '{args.lookup}'")
            return 0
        for m in hits:
            print(f"[{m.id}] {m.category}  ({m.tier})")
            print(f"  Qlik:        {m.qlik}   e.g. {m.qlik_example}")
            print(f"  ThoughtSpot: {m.ts}   e.g. {m.ts_example}")
            if m.status != "ok":
                print(f"  status:      {m.status}")
            print()
        return 0

    # audit: collect expressions from a file (one per line) and/or an IR's measures
    exprs: list[str] = []
    if args.audit:
        exprs += [ln.strip() for ln in Path(args.audit).read_text(encoding="utf-8").splitlines()
                  if ln.strip()]
    if args.ir:
        app = QlikApp.load(args.ir)
        exprs += [m.expression for m in app.measures if m.expression]
    if not exprs:
        s = formula_map.stats()
        print("formula map:", s)
        print("use --lookup <fn> or --audit <file>/--ir <ir.json>")
        return 0

    rep = formula_map.audit(exprs)
    print(f"audited {rep['expressions']} expression(s), "
          f"{rep['distinct_functions']} distinct function(s)")
    print(f"  ✓ translatable: {len(rep['translatable'])}  {rep['translatable']}")
    print(f"  ⚠ manual:       {len(rep['manual'])}  {rep['manual']}")
    print(f"  ? verify:       {len(rep['verify'])}  {rep['verify']}")
    print(f"  ✗ unknown:      {len(rep['unknown'])}  {rep['unknown']}")
    print(f"  coverage: {rep['coverage_pct']}% translatable")
    return 0


# -- migrate (all three) ---------------------------------------------------

def cmd_migrate(args: argparse.Namespace) -> int:
    workdir = Path(args.workdir)
    args.out = str(workdir / "app.ir.json")
    if cmd_extract(args) != 0:
        return 1
    args.ir = args.out
    args.out = str(workdir / "tml")
    args.report = str(workdir / "report.md")
    if cmd_transform(args) != 0:
        return 1
    if args.no_load:
        print("→ stopping before load (--no-load). Review the report, then run `load`.")
        return 0
    args.tml = str(workdir / "tml")
    return cmd_load(args)


# -- arg parsing -----------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="q2t", description="Qlik Sense -> ThoughtSpot migration")
    sub = p.add_subparsers(dest="command", required=True)

    def add_extract_opts(sp):
        sp.add_argument("--qvf", help="path to .qvf (offline mode)")
        sp.add_argument("--mode", choices=["offline", "engine", "engine-artifacts", "qlik-cloud"],
                        default="offline")
        sp.add_argument("--artifacts", help="output/ dir from qvf-engine-extract (engine-artifacts mode)")
        sp.add_argument("--engine", help="Qlik engine ws(s):// URL (engine mode)")
        sp.add_argument("--tenant", help="Qlik Cloud tenant URL (qlik-cloud mode)")
        sp.add_argument("--api-key", default=os.environ.get("QLIK_API_KEY"),
                        help="Qlik Cloud API key (qlik-cloud mode; or QLIK_API_KEY)")
        sp.add_argument("--app-id", help="Qlik app GUID (engine mode)")
        sp.add_argument("--header", action="append", help="extra ws header k=v (repeatable)")
        sp.add_argument("--probe", action="store_true",
                        help="engine mode: connect + list objects only (safe first-run check)")

    def add_transform_opts(sp):
        sp.add_argument("--model-kind", choices=["model", "worksheet"], default="model")

    def add_load_opts(sp):
        sp.add_argument("--host", required=True)
        sp.add_argument("--user", default=os.environ.get("TS_USER"))
        sp.add_argument("--password", default=os.environ.get("TS_PASS"))
        sp.add_argument("--token", help="bearer token instead of user/pass")
        sp.add_argument("--import-policy", default="PARTIAL",
                        choices=["PARTIAL", "ALL_OR_NONE", "VALIDATE_ONLY"])
        sp.add_argument("--validate-only", action="store_true",
                        help="dry-run: validate TML without creating objects")
        sp.add_argument("--insecure", action="store_true", help="skip TLS verify")

    sp = sub.add_parser("extract"); add_extract_opts(sp)
    sp.add_argument("--out", required=True)
    sp.set_defaults(func=cmd_extract)

    sp = sub.add_parser("transform"); add_transform_opts(sp)
    sp.add_argument("--ir", required=True)
    sp.add_argument("--out", required=True)
    sp.add_argument("--report", default="report.md")
    sp.set_defaults(func=cmd_transform)

    sp = sub.add_parser("load"); add_load_opts(sp)
    sp.add_argument("--tml", required=True)
    sp.set_defaults(func=cmd_load)

    sp = sub.add_parser("formulas", help="Qlik->TS formula mapping reference + coverage audit")
    sp.add_argument("--lookup", help="look up a Qlik function name or substring")
    sp.add_argument("--audit", help="file of Qlik expressions (one per line) to audit")
    sp.add_argument("--ir", help="audit measure expressions from an IR JSON")
    sp.set_defaults(func=cmd_formulas)

    sp = sub.add_parser("migrate")
    add_extract_opts(sp); add_transform_opts(sp); add_load_opts(sp)
    sp.add_argument("--workdir", default="build")
    sp.add_argument("--no-load", action="store_true",
                    help="extract + transform only; stop before loading")
    sp.set_defaults(func=cmd_migrate)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
