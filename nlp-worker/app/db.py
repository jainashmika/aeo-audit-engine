"""PostgreSQL + pgvector access layer."""
from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import numpy as np
import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from .config import settings

_pool: ConnectionPool | None = None
SCHEMA_CANDIDATES = [
    Path(__file__).resolve().parent.parent / "db" / "init.sql",          # inside Docker image
    Path(__file__).resolve().parent.parent.parent / "db" / "init.sql",   # repo checkout
]


def _configure(conn: psycopg.Connection) -> None:
    register_vector(conn)


def init_pool() -> None:
    global _pool
    # Make sure the extension exists before pgvector type registration runs
    with psycopg.connect(settings.database_url, autocommit=True) as c:
        c.execute("CREATE EXTENSION IF NOT EXISTS vector")
    _pool = ConnectionPool(settings.database_url, min_size=1, max_size=10,
                           configure=_configure, kwargs={"row_factory": dict_row, "options": "-c TimeZone=UTC"}, open=True)
    ensure_schema()


def close_pool() -> None:
    if _pool:
        _pool.close()


@contextmanager
def conn() -> Iterator[psycopg.Connection]:
    assert _pool is not None, "pool not initialised"
    with _pool.connection() as c:
        yield c


def ensure_schema() -> None:
    for p in SCHEMA_CANDIDATES:
        if p.exists():
            with conn() as c:
                c.execute(p.read_text())
            return
    raise FileNotFoundError("db/init.sql not found")


def fetchall(sql: str, params: Any = None) -> list[dict]:
    with conn() as c:
        return list(c.execute(sql, params).fetchall())


def fetchone(sql: str, params: Any = None) -> dict | None:
    with conn() as c:
        return c.execute(sql, params).fetchone()


def execute(sql: str, params: Any = None) -> None:
    with conn() as c:
        c.execute(sql, params)


def jsonb(v: Any) -> Jsonb:
    return Jsonb(json.loads(json.dumps(v, default=str)))


def vec(v: np.ndarray) -> np.ndarray:
    return np.asarray(v, dtype=np.float32)
