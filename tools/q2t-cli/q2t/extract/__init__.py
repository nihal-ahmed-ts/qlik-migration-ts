"""Qlik extraction dispatcher.

Offline extraction tries the reliable SQLite path first (if the .qvf really is
a SQLite database with a parseable layout) and falls back to the best-effort
byte scanner otherwise. Engine mode is handled separately by qlik_engine.
"""

from __future__ import annotations

from ..ir import QlikApp


def extract_offline(qvf_path: str) -> QlikApp:
    from . import qvf_sqlite, qvf_offline

    app = qvf_sqlite.extract(qvf_path)
    if app is not None:
        return app
    return qvf_offline.extract(qvf_path)
