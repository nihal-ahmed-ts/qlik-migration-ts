"""ThoughtSpot REST API v2 client.

Authentication uses the cookie-session login flow
(`/api/rest/2.0/auth/session/login`), which is the flow verified to work
against the target cluster. A bearer token can be supplied instead if you
already have one.

Only the endpoints the migration needs are wrapped:
  * login / whoami
  * connection search + create
  * TML import
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional

import requests


class ThoughtSpotError(RuntimeError):
    pass


# Qlik connection type -> ThoughtSpot data_warehouse_type.
# Anything not here is reported and left for the operator to choose.
QLIK_TO_TS_WAREHOUSE = {
    "snowflake": "SNOWFLAKE",
    "redshift": "AMAZON_REDSHIFT",
    "bigquery": "GOOGLE_BIGQUERY",
    "google bigquery": "GOOGLE_BIGQUERY",
    "databricks": "DATABRICKS",
    "postgres": "POSTGRES",
    "postgresql": "POSTGRES",
    "sqlserver": "SQLSERVER",
    "sql server": "SQLSERVER",
    "microsoft sql server": "SQLSERVER",
    "mysql": "MYSQL",
    "oracle": "ORACLE_ADW",
    "teradata": "TERADATA",
    "synapse": "AZURE_SYNAPSE",
    "athena": "AMAZON_ATHENA",
}


class ThoughtSpotClient:
    def __init__(self, host: str, *, timeout: int = 60, verify_tls: bool = True):
        self.host = host.rstrip("/")
        self.base = f"{self.host}/api/rest/2.0"
        self.timeout = timeout
        self.session = requests.Session()
        self.session.verify = verify_tls
        self._bearer: Optional[str] = None

    # -- auth --------------------------------------------------------------

    def login(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        *,
        org_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """Cookie-session login. Falls back to TS_USER / TS_PASS env vars."""
        username = username or os.environ.get("TS_USER")
        password = password or os.environ.get("TS_PASS")
        if not username or not password:
            raise ThoughtSpotError("username/password required (or set TS_USER/TS_PASS)")
        body: dict[str, Any] = {"username": username, "password": password}
        if org_id is not None:
            body["org_identifier"] = org_id
        r = self.session.post(
            f"{self.base}/auth/session/login",
            json=body,
            headers={"Accept": "application/json"},
            timeout=self.timeout,
        )
        if r.status_code >= 400:
            raise ThoughtSpotError(f"login failed ({r.status_code}): {r.text}")
        return self.whoami()

    def use_bearer(self, token: str) -> None:
        self._bearer = token
        self.session.headers["Authorization"] = f"Bearer {token}"

    def whoami(self) -> dict[str, Any]:
        return self._get("/auth/session/user")

    # -- connections -------------------------------------------------------

    def search_connections(self, name: Optional[str] = None) -> list[dict[str, Any]]:
        body: dict[str, Any] = {"record_size": 100}
        if name:
            body["connections"] = [{"identifier": name}]
        return self._post("/connection/search", body)

    def create_connection(
        self,
        name: str,
        data_warehouse_type: str,
        config: dict[str, Any],
        *,
        validate: bool = False,
        description: str = "",
    ) -> dict[str, Any]:
        """Create a connection. `config` is the data_warehouse_config map
        (configuration + authenticationType + externalDatabases)."""
        body = {
            "name": name,
            "description": description,
            "data_warehouse_type": data_warehouse_type,
            "data_warehouse_config": config,
            "validate": validate,
        }
        return self._post("/connection/create", body)

    # -- TML ---------------------------------------------------------------

    def import_tml(
        self,
        tml_docs: list[str],
        *,
        create_new: bool = True,
        import_policy: str = "PARTIAL",
    ) -> list[dict[str, Any]]:
        """Import one or more TML documents (YAML strings).

        import_policy: PARTIAL | ALL_OR_NONE | VALIDATE_ONLY.
        VALIDATE_ONLY is a safe dry-run that checks TML without creating
        objects — use it to validate generated TML before a real import.
        """
        body = {
            "metadata_tmls": tml_docs,
            "import_policy": import_policy,
            "create_new": create_new,
        }
        return self._post("/metadata/tml/import", body)

    def validate_tml(self, tml_docs: list[str]) -> list[dict[str, Any]]:
        """Dry-run: validate TML without creating anything."""
        return self.import_tml(tml_docs, import_policy="VALIDATE_ONLY")

    # -- low level ---------------------------------------------------------

    def _get(self, path: str) -> Any:
        r = self.session.get(
            f"{self.base}{path}",
            headers={"Accept": "application/json"},
            timeout=self.timeout,
        )
        return self._unwrap(r)

    def _post(self, path: str, body: dict[str, Any]) -> Any:
        r = self.session.post(
            f"{self.base}{path}",
            json=body,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=self.timeout,
        )
        return self._unwrap(r)

    @staticmethod
    def _unwrap(r: requests.Response) -> Any:
        if r.status_code >= 400:
            raise ThoughtSpotError(f"{r.request.method} {r.url} -> {r.status_code}: {r.text}")
        if not r.content:
            return {}
        try:
            return r.json()
        except json.JSONDecodeError:
            return r.text
