"""SQLite database initialization and connection management."""

import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent / "autopilot.db"

_CREATE_RUNS = """
CREATE TABLE IF NOT EXISTS runs (
    run_id          TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    input_type      TEXT,          -- 'audio' or 'text'
    raw_input       TEXT,          -- base64 audio or text
    transcript      TEXT,
    extracted_json  TEXT,          -- JSON string
    evidence_json   TEXT,          -- JSON string
    reply_draft     TEXT,          -- JSON string
    actions_json    TEXT,          -- JSON string
    status          TEXT NOT NULL DEFAULT 'pending',  -- pending/extracted/drafted/confirmed/executed/error
    error           TEXT
);
"""

_CREATE_CACHE = """
CREATE TABLE IF NOT EXISTS cache (
    key         TEXT PRIMARY KEY,
    value_json  TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    ttl_seconds INTEGER NOT NULL DEFAULT 3600
);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_connection()
    try:
        conn.execute(_CREATE_RUNS)
        conn.execute(_CREATE_CACHE)
        conn.commit()
        logger.info("Database initialized at %s", DB_PATH)
    finally:
        conn.close()


# Auto-init on import
init_db()
