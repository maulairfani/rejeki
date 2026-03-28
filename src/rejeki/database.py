import os
import sqlite3
from pathlib import Path

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"

_TURSO_URL = os.getenv("TURSO_DATABASE_URL")
_TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN")
_USE_TURSO = bool(_TURSO_URL and _TURSO_TOKEN)

if _USE_TURSO:
    import libsql as _driver
else:
    _driver = sqlite3


def get_connection():
    if _USE_TURSO:
        conn = _driver.connect(_TURSO_URL, auth_token=_TURSO_TOKEN)
    else:
        conn = sqlite3.connect(
            os.getenv("DATABASE_URL", str(Path(__file__).parent.parent.parent / "rejeki.db"))
            .removeprefix("sqlite:///")
        )
        conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _row_to_dict(cursor, row) -> dict:
    return {col[0]: val for col, val in zip(cursor.description, row)}


def init_db() -> None:
    schema = _SCHEMA_PATH.read_text(encoding="utf-8")
    statements = [s.strip() for s in schema.split(";") if s.strip()]
    conn = get_connection()
    for stmt in statements:
        conn.execute(stmt)
    conn.commit()


def fetchone(query: str, params: tuple = ()) -> dict | None:
    conn = get_connection()
    cur = conn.execute(query, params)
    row = cur.fetchone()
    return _row_to_dict(cur, row) if row else None


def fetchall(query: str, params: tuple = ()) -> list[dict]:
    conn = get_connection()
    cur = conn.execute(query, params)
    rows = cur.fetchall()
    return [_row_to_dict(cur, r) for r in rows]


def execute(query: str, params: tuple = ()) -> int:
    """Execute INSERT/UPDATE/DELETE. Returns lastrowid."""
    conn = get_connection()
    cur = conn.execute(query, params)
    conn.commit()
    return cur.lastrowid
