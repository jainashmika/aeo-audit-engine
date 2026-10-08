"""Structured log stream that feeds the dashboard's bottom 'Wire' terminal."""
from __future__ import annotations

import logging
from typing import Any

from . import db

log = logging.getLogger("aeo")


def emit(source: str, message: str, level: str = "INFO", **data: Any) -> None:
    log.log(getattr(logging, level, logging.INFO), "[%s] %s %s", source, message, data or "")
    try:
        db.execute("INSERT INTO audit_log(level, source, message, data) VALUES (%s,%s,%s,%s)",
                   (level, source, message, db.jsonb(data) if data else None))
    except Exception:  # logging must never break a pipeline
        pass


def since(after_id: int = 0, limit: int = 200) -> list[dict]:
    rows = db.fetchall(
        "SELECT id, ts, level, source, message, data FROM audit_log WHERE id > %s ORDER BY id DESC LIMIT %s",
        (after_id, limit))
    return list(reversed(rows))
