"""
Synchronous SQLite helpers for the Streamlit frontend.
"""

import sqlite3
import os
from contextlib import contextmanager

# Path to the shared SQLite database.
# Strategy: walk up from this file's location looking for server/healthcare.db,
# then fall back to an environment variable override.

def _find_db_path() -> str:
    """Search parent directories for server/healthcare.db."""
    current = os.path.dirname(os.path.abspath(__file__))
    for _ in range(5):  # search up to 5 levels up
        candidate = os.path.join(current, "server", "healthcare.db")
        if os.path.exists(candidate):
            return candidate
        current = os.path.dirname(current)
    # Not found yet - return the expected path anyway (will error clearly on first use)
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "server", "healthcare.db")

DB_PATH = os.environ.get("SQLITE_DB_PATH", _find_db_path())


@contextmanager
def get_conn():
    """Yield a sqlite3 connection with row_factory set to dict-like rows."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row      # rows accessible as dicts
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetchall(query: str, params: tuple = ()) -> list[dict]:
    with get_conn() as conn:
        cur = conn.execute(query, params)
        return [dict(row) for row in cur.fetchall()]


def fetchone(query: str, params: tuple = ()) -> dict | None:
    with get_conn() as conn:
        cur = conn.execute(query, params)
        row = cur.fetchone()
        return dict(row) if row else None


def execute(query: str, params: tuple = ()) -> None:
    with get_conn() as conn:
        conn.execute(query, params)


def db_ok() -> tuple[bool, str]:
    """Check that the database file exists and is reachable. Used on startup."""
    if not os.path.exists(DB_PATH):
        return False, (
            f"Database not found at: `{DB_PATH}`\n\n"
            "**Fix:** Start the FastAPI backend first (`uvicorn main:app --reload`) "
            "so it creates `healthcare.db`, then refresh this page.\n\n"
            "Or set the `SQLITE_DB_PATH` environment variable to the correct path."
        )
    try:
        fetchone("SELECT 1")
        return True, ""
    except Exception as e:
        return False, f"Database connection failed: {e}"