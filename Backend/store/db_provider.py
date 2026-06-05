import sqlite3
from typing import Generator

from store.db import get_connection


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Yield a SQLite connection for use in FastAPI Depends(). Not yet wired to any handler — establishes the pattern for future use."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()
