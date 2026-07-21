"""Qlik Cloud (SaaS) extraction adapter -> IR.

The legitimate API path: for users who have Qlik Cloud access, pull an app's
definitions directly — no PDF, no guesswork, no engine bypass.

Uses two Qlik Cloud APIs:
  * REST (/api/v1)        — resolve the app, list data connections
  * Engine API (QIX/wss)  — the full layout (script, model, master items,
                            sheets, charts) via qlik_engine

Auth is a tenant API key sent as `Authorization: Bearer <key>`. The resulting
IR is SOURCE-grade (extraction_mode="engine").
"""

from __future__ import annotations

import os
from typing import Any, Optional

import requests

from ..ir import Connection, QlikApp


# -- pure helpers (unit-testable without a tenant) -------------------------

def _host(tenant: str) -> str:
    return tenant.replace("https://", "").replace("http://", "").rstrip("/")


def engine_url(tenant: str, app_id: str) -> str:
    """wss URL the Engine API expects for an app on Qlik Cloud."""
    return f"wss://{_host(tenant)}/app/{app_id}"


def rest_base(tenant: str) -> str:
    return f"https://{_host(tenant)}/api/v1"


def parse_data_connections(items: list[dict]) -> list[Connection]:
    """Map Qlik Cloud /data-connections items to IR Connections.

    Tolerant of field-name variation across tenant versions.
    """
    out: list[Connection] = []
    for c in items or []:
        name = c.get("qName") or c.get("name") or c.get("id", "")
        qtype = (c.get("qType") or c.get("type") or c.get("datasourceID") or "UNKNOWN")
        if not name:
            continue
        props = {k: c[k] for k in ("qConnectStatement", "datasourceID", "space", "id")
                 if k in c}
        out.append(Connection(name=name, qlik_type=str(qtype), properties=props))
    return out


# -- live calls ------------------------------------------------------------

def _auth(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}


def list_apps(tenant: str, api_key: str, *, timeout: int = 30) -> list[dict]:
    r = requests.get(f"{rest_base(tenant)}/items",
                     params={"resourceType": "app", "limit": 100},
                     headers=_auth(api_key), timeout=timeout)
    r.raise_for_status()
    return r.json().get("data", [])


def fetch_data_connections(tenant: str, api_key: str, *, timeout: int = 30) -> list[dict]:
    r = requests.get(f"{rest_base(tenant)}/data-connections",
                     headers=_auth(api_key), timeout=timeout)
    r.raise_for_status()
    return r.json().get("data", [])


def resolve_app_id(tenant: str, api_key: str, name_or_id: str) -> str:
    """Accept an app GUID or a name; return the GUID."""
    # If it already looks like a GUID, trust it.
    if name_or_id.count("-") >= 4 and len(name_or_id) >= 32:
        return name_or_id
    for app in list_apps(tenant, api_key):
        if app.get("name") == name_or_id or app.get("id") == name_or_id:
            return app.get("resourceId") or app.get("id")
    raise ValueError(f"App '{name_or_id}' not found in tenant {tenant}")


def extract(tenant: str, app_id: str, api_key: Optional[str] = None) -> QlikApp:
    """Pull an app from Qlik Cloud into the IR.

    `app_id` may be a GUID or an app name. `api_key` falls back to the
    QLIK_API_KEY env var.
    """
    api_key = api_key or os.environ.get("QLIK_API_KEY")
    if not api_key:
        raise ValueError("Qlik Cloud API key required (--api-key or QLIK_API_KEY)")

    try:
        app_id = resolve_app_id(tenant, api_key, app_id)
    except Exception:
        pass  # fall through with the given value; engine open will report if bad

    from . import qlik_engine
    app = qlik_engine.extract(engine_url(tenant, app_id), app_id,
                              headers={"Authorization": f"Bearer {api_key}"})
    app.source_file = f"{tenant} / app {app_id}"

    # Enrich connections from the Cloud REST data-connections endpoint.
    try:
        conns = parse_data_connections(fetch_data_connections(tenant, api_key))
        existing = {c.name for c in app.connections}
        for c in conns:
            if c.name not in existing:
                app.connections.append(c)
        if conns:
            app.note("info", "connection",
                     f"Loaded {len(conns)} data connection(s) from Qlik Cloud REST.")
    except Exception as e:
        app.note("warning", "connection",
                 f"Could not fetch data-connections via REST: {e}")
    return app
